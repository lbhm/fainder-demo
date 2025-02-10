import re
from collections import defaultdict
from collections.abc import Sequence
from functools import lru_cache

from lark import Lark, Token, Transformer, Tree, Visitor
from loguru import logger
from numpy import uint32

from backend.column_index import ColumnIndex
from backend.config import CacheInfo, FainderMode, Metadata
from backend.fainder_index import FainderIndex
from backend.lucene_connector import LuceneConnector

GRAMMAR = """
    start: query
    query: expression (OPERATOR query)?
    expression: not_expr | term | "(" query ")"
    not_expr: "NOT" term | "NOT" "(" query ")"
    term: KEYWORD_OPERATOR "(" keywordterm ")"
        | COLUMN_OPERATOR "(" column_query ")"
    column_query: col_expr (OPERATOR column_query)?
    col_expr: not_col_expr | columnterm | "(" column_query ")"
    not_col_expr: "NOT" columnterm | "NOT" "(" column_query ")"
    columnterm: NAME_OPERATOR "(" nameterm ")" | PERCENTILE_OPERATOR "(" percentileterm ")"
    percentileterm: FLOAT ";" COMPARISON ";" SIGNED_FLOAT
    keywordterm: LUCENE_QUERY
    nameterm: IDENTIFIER ";" INT
    OPERATOR: "AND" | "OR" | "XOR"
    COMPARISON: "ge" | "gt" | "le" | "lt"
    PERCENTILE_OPERATOR: ("pp"i | "percentile"i) _WSI?
    KEYWORD_OPERATOR: ("kw"i | "keyword"i) _WSI?
    COLUMN_OPERATOR: ("col"i | "column"i) _WSI?
    NAME_OPERATOR: ("name"i) _WSI?
    IDENTIFIER: /[a-zA-Z0-9_ ]+/
    LUCENE_QUERY: /([^()]|\\([^()]*\\))+/
    %ignore _WS
    %ignore COMMENT
    %import common.INT
    %import common.FLOAT
    %import common.SIGNED_FLOAT
    %import common.WS -> _WS
    %import common.WS_INLINE -> _WSI
    %import common.SH_COMMENT -> COMMENT
"""

# Lucene query regex matches:
# 1. [^()] - Any single character that is NOT a parenthesis (not ( or )) OR
# 2. \([^()]*\\) - A sequence that:
#    - \\( matches an opening parenthesis
#    - [^()]* matches zero or more characters that are not parentheses
#    - \\) matches a closing parenthesis

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
    ):
        self.lucene_connector = lucene_connector
        self.grammar = Lark(GRAMMAR, start="start")
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

    def parse(self, query: str) -> Tree:
        return self.grammar.parse(query)

    def _execute(
        self,
        query: str,
        fainder_mode: FainderMode = "low_memory",
        enable_highlighting: bool = True,
        enable_filtering: bool = False,
    ) -> tuple[list[int], Highlights]:
        # Reset state for new query
        self.annotator.reset()
        self.executor.reset(fainder_mode, enable_highlighting, enable_filtering)

        # Parse query
        parse_tree = self.parse(query)
        self.annotator.visit(parse_tree)
        logger.trace(f"Parse tree: {parse_tree.pretty()}")

        # Execute query
        result: set[int]
        highlights: Highlights
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


class QueryAnnotator(Visitor):
    """
    This visitor goes top-down through the parse tree and annotates each percentile and keyword
    term with its parent operator and side (i.e., evaluation order) in the parent expression.
    """

    # TODO: We need to investigate this class because nodes are annotated too often

    def __init__(self) -> None:
        self.current_operator: str | None = None
        self.current_side: str | None = None

    def reset(self) -> None:
        self.current_operator = None
        self.current_side = None

    def query(self, tree: Tree):
        if len(tree.children) == 3:  # Has operator
            old_operator = self.current_operator
            old_side = self.current_side

            assert isinstance(tree.children[1], Token)
            self.current_operator = tree.children[1].value

            # Visit left side
            self.current_side = "left"
            self.visit(tree.children[0])

            # Visit right side
            self.current_side = "right"
            self.visit(tree.children[2])

            self.current_operator = old_operator
            self.current_side = old_side
        else:
            self.visit(tree.children[0])

    def percentileterm(self, tree: Tree) -> None:
        if self.current_operator:
            tree.children.append(self.current_operator)
            tree.children.append(self.current_side)

    def keywordterm(self, tree: Tree) -> None:
        if self.current_operator:
            tree.children.append(self.current_operator)
            tree.children.append(self.current_side)

    def columnterm(self, tree: Tree) -> None:
        if self.current_operator:
            tree.children.append(self.current_operator)
            tree.children.append(self.current_side)


class QueryExecutor(Transformer):
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
        enable_highlighting: bool = True,
        enable_filtering: bool = False,
    ):
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

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = True,
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

    def percentileterm(self, items: list[Token]) -> set[uint32]:
        # TODO: Investigate length of items and annotations
        logger.trace(f"Evaluating percentile term: {items}")
        percentile = float(items[0].value)
        comparison = items[1].value
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

    def keywordterm(self, items: list[Token]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating keyword term: {items}")
        query = items[0].value.strip()
        doc_filter = None

        result_docs, scores, highlights = self.lucene_connector.evaluate_query(
            query, doc_filter, self.enable_highlighting
        )
        self.updates_scores(result_docs, scores)

        return set(result_docs), (highlights, set())  # Return empty set for column highlights

    def nameterm(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating column term: {items}")
        column = items[0].value.strip()
        k = int(items[1].value.strip())
        # operator = items[-2] if len(items) > 2 else None
        # side = items[-1] if len(items) > 2 else None

        # TODO: fix this
        column_filter = None

        result = self.hnsw_index.search(column, k, column_filter)
        logger.trace(f"Result of column search with column:{column} k:{k}r: {result}")
        # TODO: update results

        return result

    def column_query(self, items: list[set[uint32] | Token]) -> set[uint32]:
        logger.trace(f"Evaluating column expression with {len(items)} items")
        if len(items) == 1 and isinstance(items[0], set):
            return items[0]

        left: set[uint32] = items[0]  # type: ignore
        operator: str = items[1].value.strip()  # type: ignore
        right: set[uint32] = items[2]  # type: ignore

        match operator:
            case "AND":
                return left & right
            case "OR":
                return left | right
            case "XOR":
                return left ^ right
            case _:
                raise ValueError(f"Unknown operator: {operator}")

    def col_expr(self, items: list[set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating column expression with {len(items)} items")
        return items[0]

    def not_col_expr(self, items: list[set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating NOT column expression with {len(items)} items")
        to_negate = items[0]
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in self.metadata.col_to_doc}
        return all_columns - to_negate

    def columnterm(self, items: tuple[Token, set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating column term with {items} items")
        return items[1]

    def term(
        self, items: tuple[Token, set[uint32] | tuple[set[int], Highlights]]
    ) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating term with items: {items}")
        if items[0].value.strip().lower() in ["column", "col"]:
            col_ids: set[uint32] = items[1]  # type: ignore
            return col_to_doc_ids(col_ids, self.metadata.col_to_doc), ({}, col_ids)
        doc_ids: set[int]
        highlights: Highlights
        doc_ids, highlights = items[1]  # type: ignore
        return doc_ids, highlights

    def not_expr(self, items: list[tuple[set[int], Highlights]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating NOT expression with {len(items)} items")
        to_negate, _ = items[0]
        all_docs = set(self.metadata.doc_to_cols.keys())
        return all_docs - to_negate, ({}, set())  # Negate all documents

    def expression(self, items: list[tuple[set[int], Highlights]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating expression with {len(items[0])} items")
        return items[0]

    def query(
        self, items: list[tuple[set[int], Highlights] | Token]
    ) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating query with {len(items)} items")
        if len(items) == 1 and isinstance(items[0], tuple):
            return items[0]

        left_set: set[int]
        left_highlights: Highlights
        left_set, left_highlights = items[0]  # type: ignore
        operator: str = items[1].value.strip()  # type: ignore
        right_set: set[int]
        right_highlights: Highlights
        right_set, right_highlights = items[2]  # type: ignore

        match operator:
            case "AND":
                result_set = left_set & right_set
            case "OR":
                result_set = left_set | right_set
            case "XOR":
                result_set = left_set ^ right_set

            case _:
                raise ValueError(f"Unknown operator: {operator}")

        result_highlights = self._merge_highlights(left_highlights, right_highlights, result_set)
        return result_set, result_highlights

    def start(self, items: list[tuple[set[int], Highlights]]) -> tuple[set[int], Highlights]:
        doc_set, (doc_highlights, col_highlights) = items[0]

        if self.enable_highlighting:
            # Only return the column highlights that are in the document set
            filtered_col_highlights = col_ids_in_docs(
                col_highlights, doc_set, self.metadata.doc_to_cols
            )
            return doc_set, (doc_highlights, filtered_col_highlights)

        return items[0]

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

        return result_document_highlights, result_columns


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
    return {uint32(hist_to_col[int(hist_id)]) for hist_id in hist_ids if hist_id in hist_to_col}
