import re
from collections import defaultdict
from collections.abc import Sequence
from functools import lru_cache

from lark import Lark, ParseTree, Token, Transformer, Tree, Visitor
from loguru import logger
from numpy import uint32

from backend.column_index import ColumnIndex
from backend.config import CacheInfo, FainderMode, Metadata
from backend.fainder_index import FainderIndex
from backend.lucene_connector import LuceneConnector

GRAMMAR = """
    query:          tbl_expr

    ?tbl_expr:      tbl_term
                    | tbl_term ("OR" tbl_term)+ -> disjunction
    ?tbl_term:      tbl_factor
                    | tbl_factor ("AND" tbl_factor)+ -> conjunction
    ?tbl_factor:    tbl_operator
                    | "NOT" tbl_factor -> negation
                    | "(" tbl_expr ")"
    ?tbl_operator:  _KEYWORD_KW "(" keyword_op ")"
                    | _COLUMN_KW "(" col_op ")"

    ?col_expr:      col_term
                    | col_term ("OR" col_term)+ -> disjunction
    ?col_term:      col_factor
                    | col_factor ("AND" col_factor)+ -> conjunction
    ?col_factor:    col_operator
                    | "NOT" col_factor -> negation
                    | "(" col_expr ")"
    ?col_operator:  _NAME_KW "(" name_op ")"
                    | _PERCENTILE_KW "(" percentile_op ")"

    col_op:         col_expr
    keyword_op:     STRING
    percentile_op:  FLOAT ";" COMPARISON ";" SIGNED_NUMBER
    name_op:        STRING ";" INT

    _KEYWORD_KW:    "kw"i | "keyword"i
    _COLUMN_KW:     "col"i | "column"i
    _NAME_KW:       "name"i
    _PERCENTILE_KW: "pp"i | "percentile"i
    COMPARISON:     "ge" | "gt" | "le" | "lt"

    %import common.FLOAT
    %import common.INT
    %import common.SIGNED_NUMBER
    %import common.WS
    %import common.SH_COMMENT
    %import python.STRING

    %ignore WS
    %ignore SH_COMMENT
"""

# Type alias for highlights
DocumentHighlights = dict[int, dict[str, str]]
ColumnHighlights = set[uint32]  # set of column ids that should be highlighted
Highlights = tuple[DocumentHighlights, ColumnHighlights]


class QueryEvaluator:
    def __init__(
        self,
        lucene_connector: LuceneConnector,
        fainder_index: FainderIndex,
        hnsw_index: ColumnIndex,
        metadata: Metadata,
        cache_size: int = 128,
    ) -> None:
        self.lucene_connector = lucene_connector
        self.grammar = Lark(GRAMMAR, parser="lalr", lexer="contextual", start="query", strict=True)
        self.annotator = QueryAnnotator()
        self.executor = QueryExecutor(self.lucene_connector, fainder_index, hnsw_index, metadata)

        # NOTE: Don't use lru_cache on methods
        # See https://docs.astral.sh/ruff/rules/cached-instance-method/ for details
        self.execute = lru_cache(maxsize=cache_size)(self._execute)

    def update_indices(
        self,
        fainder_index: FainderIndex,
        hnsw_index: ColumnIndex,
        metadata: Metadata,
    ) -> None:
        self.executor = QueryExecutor(self.lucene_connector, fainder_index, hnsw_index, metadata)
        self.clear_cache()

    def parse(self, query: str) -> ParseTree:
        return self.grammar.parse(query)

    def _execute(
        self,
        query: str,
        fainder_mode: FainderMode = "low_memory",
        enable_highlighting: bool = False,
        enable_filtering: bool = False,
    ) -> tuple[list[int], Highlights]:
        # Reset state for new query
        self.annotator.reset()
        self.executor.reset(fainder_mode, enable_highlighting, enable_filtering)

        # Parse query
        parse_tree = self.parse(query)
        logger.trace(f"Parse tree: {parse_tree.pretty()}")
        logger.trace(f"Parse tree data: {parse_tree}")
        # TODO: Do we need visit_topdown here?
        self.annotator.visit(parse_tree)

        # Execute query
        result, highlights = self.executor.transform(parse_tree)

        # Sort by score
        list_result = list(result)
        list_result.sort(key=lambda x: self.executor.scores.get(x, -1), reverse=True)
        return list_result, highlights

    def clear_cache(self) -> None:
        self.execute.cache_clear()

    def cache_info(self) -> CacheInfo:
        hits, misses, max_size, curr_size = self.execute.cache_info()
        return CacheInfo(hits=hits, misses=misses, max_size=max_size, curr_size=curr_size)


class QueryAnnotator(Visitor[Token]):
    """
    This visitor goes top-down through the parse tree and annotates each percentile and keyword
    term with its parent operator and side (i.e., evaluation order) in the parent expression.
    """

    def __init__(self) -> None:
        self.parent_operator: str | None = None
        self.current_side: str | None = None

    def reset(self) -> None:
        self.parent_operator = None
        self.current_side = None

    def query(self, tree: ParseTree) -> None:
        # TODO: We need to investigate this class because nodes are annotated too often
        # NOTE: Calling visit again in this method will annotate the tree nodes multiple times
        if len(tree.children) == 3:  # Has operator
            if not isinstance(tree.children[1], Token):
                logger.error(f"Expected operator, got: {tree.children[1]}. Aborting annotation.")
                return

            old_parent = self.parent_operator
            old_side = self.current_side
            self.parent_operator = tree.children[1].value

            # Visit left side
            if isinstance(tree.children[0], Tree):
                self.current_side = "left"
                self.visit(tree.children[0])

            # Visit right side
            if isinstance(tree.children[2], Tree):
                self.current_side = "right"
                self.visit(tree.children[2])

            self.parent_operator = old_parent
            self.current_side = old_side
        else:
            if isinstance(tree.children[0], Tree):
                self.visit(tree.children[0])

    def percentileterm(self, tree: ParseTree) -> None:
        if self.parent_operator:
            tree.children.append(Token("parent_op", self.parent_operator))
            tree.children.append(Token("side", self.current_side))

    def keywordterm(self, tree: ParseTree) -> None:
        if self.parent_operator:
            tree.children.append(Token("parent_op", self.parent_operator))
            tree.children.append(Token("side", self.current_side))

    def columnterm(self, tree: ParseTree) -> None:
        if self.parent_operator:
            tree.children.append(Token("parent_op", self.parent_operator))
            tree.children.append(Token("side", self.current_side))


class QueryExecutor(Transformer[Token, tuple[set[int], Highlights]]):
    """This transformer evaluates the parse tree bottom-up and compute the query result."""

    fainder_mode: FainderMode
    scores: dict[int, float]
    last_result: set[int] | set[uint32] | None
    current_side: str | None

    def __init__(
        self,
        lucene_connector: LuceneConnector,
        fainder_index: FainderIndex,
        hnsw_index: ColumnIndex,
        metadata: Metadata,
        fainder_mode: FainderMode = "low_memory",
        enable_highlighting: bool = False,
        enable_filtering: bool = False,
    ) -> None:
        self.lucene_connector = lucene_connector
        self.fainder_index = fainder_index
        self.hnsw_index = hnsw_index
        self.metadata = metadata

        self.reset(fainder_mode, enable_highlighting, enable_filtering)

    def _get_column_filter(
        self, operator: str | None, side: str | None
    ) -> set[int] | set[uint32] | None:
        """Create a document filter for AND operators based on previous results."""
        if (
            not self.enable_filtering
            or not self.last_result
            or operator != "AND"
            or side != "right"
        ):
            return None

        # Only apply filters to the right side of AND operations
        logger.trace(f"Applying filter from previous result: {self.last_result}")
        return self.last_result

    def _has_keyword_result(self, items: list[tuple[set[int], Highlights] | set[uint32]]) -> bool:
        """Check if any of the items is a keyword result."""
        return any(isinstance(item, tuple) for item in items)

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
        enable_filtering: bool = False,
    ) -> None:
        self.scores = defaultdict(float)
        self.last_result = None
        self.current_side = None

        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting
        self.enable_filtering = enable_filtering

    def updates_scores(self, doc_ids: Sequence[int], scores: Sequence[float]) -> None:
        logger.trace(f"Updating scores for {len(doc_ids)} documents")
        for doc_id, score in zip(doc_ids, scores, strict=True):
            self.scores[doc_id] += score

        for i, doc_id in enumerate(doc_ids):
            self.scores[doc_id] += scores[i]

    def percentile_op(self, items: list[Token]) -> set[uint32]:
        # TODO: Investigate length of items and annotations
        logger.trace(f"Evaluating percentile term: {items}")
        percentile = float(items[0].value)
        comparison: str = items[1].value
        reference = float(items[2].value)
        # operator = None
        # side = None
        # if len(items) >= 5:
        # operator = items[-2]
        # side = items[-1]

        # TODO: add filter
        hist_filter = None

        result_hists = self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode, hist_filter
        )
        # TODO: update last_result
        return hist_to_col_ids(result_hists, self.metadata.hist_to_col)

    def keyword_op(self, items: list[Token]) -> tuple[set[int], Highlights]:
        """Evaluate keyword term using merged Lucene query."""
        logger.trace(f"Evaluating keyword term: {items}")
        # Extract the lucene query from items
        query = str(items[0]).strip() if items else ""
        query = query[1:-1] if query[0] == "'" and query[-1] == "'" else query
        doc_filter = None

        result_docs, scores, highlights = self.lucene_connector.evaluate_query(
            query, doc_filter, self.enable_highlighting
        )
        self.updates_scores(result_docs, scores)

        return set(result_docs), (highlights, set())  # Return empty set for column highlights

    def name_op(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating column term: {items}")
        column = items[0].value.strip()
        # remove ' ' from the first and last character
        column = column[1:-1] if column[0] == "'" and column[-1] == "'" else column
        k = int(items[1].value.strip())
        # operator = items[-2] if len(items) > 2 else None
        # side = items[-1] if len(items) > 2 else None

        # TODO: fix this
        column_filter = None

        result = self.hnsw_index.search(column, k, column_filter)
        logger.trace(f"Result of column search with column: {column} k: {k} r: {result}")
        # TODO: update results

        return result

    def col_op(self, items: list[set[uint32]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating column term: {items}")
        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        col_ids = items[0]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        return doc_ids, ({}, col_ids)

    def conjunction(
        self, items: list[tuple[set[int], Highlights] | set[uint32]]
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating conjunction with items: {items}")
        if len(items) < 2:
            raise ValueError("Conjunction must have at least two items")
        terms = items
        has_keyword_result = self._has_keyword_result(terms)
        if has_keyword_result:
            # initialize kw_result with first keyword result
            kw_result: tuple[set[int], Highlights] | None = None
            for item in terms:
                if isinstance(item, tuple):
                    kw_result = item
                    terms.remove(item)
                    break
            if kw_result is None:
                raise ValueError("No keyword result found in conjunction")
            # merge all other keyword results
            result_doc_ids: set[int] = kw_result[0]
            highlights: Highlights = kw_result[1]
            for item in terms:
                if isinstance(item, tuple):
                    # merge keyword results
                    result_doc_ids &= item[0]
                    highlights = self._merge_highlights(highlights, item[1], result_doc_ids)
                else:
                    # column result
                    col_ids: set[uint32] = item
                    doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
                    helper_highlights: Highlights = ({}, col_ids)
                    highlights = self._merge_highlights(highlights, helper_highlights, doc_ids)

            return result_doc_ids, highlights
        # all items are column results
        logger.trace(f"Conjunction column terms: {terms}")
        result_col_items = terms[0]
        assert isinstance(result_col_items, set)
        for item in terms[1:]:
            logger.trace(f"Anding column terms: {item} with {result_col_items}")
            if isinstance(item, tuple):
                raise ValueError("Keyword result found in conjunction")
            result_col_items &= item
        return result_col_items

    def disjunction(
        self, items: list[tuple[set[int], Highlights] | set[uint32]]
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating disjunction with items: {items}")
        if len(items) < 2:
            raise ValueError("Disjunction must have at least two items")
        has_keyword_result = self._has_keyword_result(items)
        if has_keyword_result:
            # initialize kw_result with first keyword result
            kw_result: tuple[set[int], Highlights] | None = None
            for item in items:
                if isinstance(item, tuple):
                    kw_result = item
                    items.remove(item)
                    break
            if kw_result is None:
                raise ValueError("No keyword result found in disjunction")
            # merge all other keyword results
            result_doc_ids: set[int] = kw_result[0]
            highlights: Highlights = kw_result[1]
            for item in items:
                if isinstance(item, tuple):
                    # merge keyword results
                    result_doc_ids |= item[0]
                    highlights = self._merge_highlights(highlights, item[1], result_doc_ids)
                else:
                    # column result
                    col_ids: set[uint32] = item
                    doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
                    helper_highlights: Highlights = ({}, col_ids)
                    highlights = self._merge_highlights(highlights, helper_highlights, doc_ids)

            return result_doc_ids, highlights
        # all items are column results
        result_col_items = items[0]
        assert isinstance(result_col_items, set)
        for item in items[1:]:
            if isinstance(item, tuple):
                raise ValueError("Keyword result found in disjunction")
            result_col_items |= item
        return result_col_items

    def negation(
        self, items: list[tuple[set[int], Highlights] | set[uint32]]
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating negation with {len(items)} items")
        if isinstance(items[0], tuple):
            to_negate, _ = items[0]
            all_docs = set(self.metadata.doc_to_cols.keys())
            return all_docs - to_negate, ({}, set())  # Negate all documents
        to_negate_cols = items[0]
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in self.metadata.col_to_doc}
        return all_columns - to_negate_cols

    def query(
        self, items: list[tuple[set[int], Highlights] | set[uint32]]
    ) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating query with {len(items)} items")
        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        if isinstance(items[0], tuple):
            return items[0]
        col_ids = items[0]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        return doc_ids, ({}, col_ids)

    def _merge_highlights(
        self, left_highlights: Highlights, right_highlights: Highlights, doc_ids: set[int]
    ) -> Highlights:
        """Merge highlights for documents that are in the result set."""
        pattern = r"<mark>(.*?)</mark>"
        regex = re.compile(pattern, re.DOTALL)

        result_document_highlights: DocumentHighlights = {}

        left_document_highlights = left_highlights[0]
        right_document_highlights = right_highlights[0]
        for doc_id in doc_ids:
            left_doc_highlights = left_document_highlights.get(doc_id, {})
            right_doc_highlights = right_document_highlights.get(doc_id, {})

            # Only process if either side has highlights
            if left_doc_highlights or right_doc_highlights:
                merged_highlights = {}

                # Process each field that appears in either highlight set
                all_keys = set(left_doc_highlights.keys()) | set(right_doc_highlights.keys())
                for key in all_keys:
                    left_text = left_doc_highlights.get(key, "")
                    right_text = right_doc_highlights.get(key, "")

                    # If either text is empty, use the non-empty one
                    if not left_text:
                        merged_highlights[key] = right_text
                        continue
                    if not right_text:
                        merged_highlights[key] = left_text
                        continue

                    # Both texts have content, merge their marks
                    base_text = left_text
                    other_text = right_text

                    # Extract all marked words from other text
                    other_marks = set(regex.findall(other_text))

                    # Add marks from other text to base text
                    for word in other_marks:
                        if word not in base_text:
                            # Word doesn't exist in base text at all
                            base_text += f" <mark>{word}</mark>"
                        elif f"<mark>{word}</mark>" not in base_text:
                            # Word exists but isn't marked
                            base_text = base_text.replace(word, f"<mark>{word}</mark>")

                    merged_highlights[key] = base_text

                result_document_highlights[doc_id] = merged_highlights

        # Merge column highlights
        result_columns = left_highlights[1] | right_highlights[1]
        filtered_col_highlights = col_ids_in_docs(
            result_columns, doc_ids, self.metadata.doc_to_cols
        )

        return result_document_highlights, filtered_col_highlights


def col_ids_in_docs(
    col_ids: set[uint32], doc_ids: set[int], doc_to_cols: dict[int, set[int]]
) -> set[uint32]:
    col_ids_in_doc = doc_to_col_ids(doc_ids, doc_to_cols)
    return col_ids_in_doc & col_ids


def doc_to_col_ids(doc_ids: set[int], doc_to_cols: dict[int, set[int]]) -> set[uint32]:
    return {
        uint32(col_id)
        for doc_id in doc_ids
        if doc_id in doc_to_cols
        for col_id in doc_to_cols[doc_id]
    }


def col_to_doc_ids(col_ids: set[uint32], col_to_doc: dict[int, int]) -> set[int]:
    return {col_to_doc[int(col_id)] for col_id in col_ids if int(col_id) in col_to_doc}


def col_to_hist_ids(col_ids: set[uint32], col_to_hist: dict[int, int]) -> set[uint32]:
    return {uint32(col_to_hist[int(col_id)]) for col_id in col_ids if int(col_id) in col_to_hist}


def hist_to_col_ids(hist_ids: set[uint32], hist_to_col: dict[int, int]) -> set[uint32]:
    return {
        uint32(hist_to_col[int(hist_id)]) for hist_id in hist_ids if int(hist_id) in hist_to_col
    }
