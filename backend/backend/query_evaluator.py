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
    query:          expr (BOOLEAN_OP query)?
    expr:           not_expr | term | "(" query ")"
    not_expr:       "NOT" term | "NOT" "(" query ")"
    term:           KEYWORD_OP "(" keywordterm ")" | COLUMN_OP "(" column_query ")"

    keywordterm:    lucene_query
    lucene_query:   lucene_clause+
    lucene_clause:  [LUCENE_OP] [field_prefix] (LUCENE_TERM | "(" lucene_query ")")
    field_prefix:   IDENTIFIER ":"

    column_query:   col_expr (BOOLEAN_OP column_query)?
    col_expr:       not_col_expr | columnterm | "(" column_query ")"
    not_col_expr:   "NOT" columnterm | "NOT" "(" column_query ")"

    columnterm:     NAME_OP "(" nameterm ")" | PERCENTILE_OP "(" percentileterm ")"
    percentileterm: FLOAT ";" COMPARISON_OP ";" SIGNED_NUMBER
    nameterm:       IDENTIFIER ";" INT

    KEYWORD_OP:     ("kw"i | "keyword"i)
    COLUMN_OP:      ("col"i | "column"i)
    NAME_OP:        ("name"i)
    PERCENTILE_OP:  ("pp"i | "percentile"i)
    BOOLEAN_OP:     "AND" | "OR" | "XOR"
    COMPARISON_OP:  "ge" | "gt" | "le" | "lt"
    LUCENE_OP:      "+" | "-"

    IDENTIFIER:     /[a-zA-Z0-9_ ]+/
    LUCENE_TERM:    /[^():+-;]+/

    %ignore _WS
    %ignore COMMENT
    %import common.INT
    %import common.FLOAT
    %import common.SIGNED_NUMBER
    %import common.WS -> _WS
    %import common.SH_COMMENT -> COMMENT
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
    ):
        self.lucene_connector = lucene_connector
        self.grammar = Lark(GRAMMAR, start="query")
        self.annotator = QueryAnnotator()
        self.executor = QueryExecutor(self.lucene_connector, fainder_index, hnsw_index, metadata)
        self.merge_keywords = MergeKeywords()

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
        enable_filtering: bool = True,
        enable_kw_merge: bool = True,
    ) -> tuple[list[int], Highlights]:
        # Reset state for new query
        self.annotator.reset()
        self.executor.reset(fainder_mode, enable_highlighting, enable_filtering)

        # Parse query
        parse_tree = self.parse(query)
        logger.trace(f"Parse tree: {parse_tree.pretty()}")

        # Merge keywords
        self.merge_keywords.merge = enable_kw_merge
        parse_tree = self.merge_keywords.transform(parse_tree)
        logger.trace(f"Parse tree after merging keywords: {parse_tree.pretty()}")

        # Annotate parse tree
        if enable_filtering:
            # TODO: Do we need visit_topdown here?
            self.annotator.visit(parse_tree)
        logger.trace(f"Parse tree: {parse_tree.pretty()}")

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


def get_keyword_term(tree: ParseTree) -> str | bool:
    """Determine the keyword term from a keywordterm tree."""

    # query -> expr -> query -> expr -> term -> keywordterm  or
    # expr -> term -> keywordterm or
    # query -> expr -> term -> keywordterm
    logger.trace("get_keyword_term: ", tree)
    expr: Tree
    if tree.data == "query" and len(tree.children) == 1:
        query = tree.children[0]
        assert isinstance(query, Tree)
        if query.data != "expr":
            return False
        assert isinstance(query.children[0], Tree)
        expr = query.children[0]
        assert isinstance(expr, Tree)
        if expr.data == "term":
            term = expr.children[1]
            assert isinstance(term, Tree)
            if term.data == "keywordterm":
                keywordterm = term.children[0]
                assert isinstance(keywordterm, str)
                return keywordterm
            return False
        if expr.data != "query" or len(expr.children) != 1:
            return False
        query = expr.children[0]
        assert isinstance(query, Tree)
        if query.data != "expr":
            return False
        assert isinstance(query.children[0], Tree)
        expr = query.children[0]
    elif tree.data == "expr":
        assert isinstance(tree.children[0], Tree)
        expr = tree.children[0]
    else:
        return False

    if expr.data == "term":
        assert len(expr.children) == 2
        term = expr.children[1]
        assert isinstance(term, Tree)
        if term.data == "keywordterm":
            keywordterm = term.children[0]
            assert isinstance(keywordterm, str)
            return keywordterm
        return False

    return False


class MergeKeywords(Transformer[Token, ParseTree]):
    """
    This transformer merges lucene queries into a single query string.
    And optionally merges keyword terms into a single keyword term.
    When on the same level.
    """

    def __init__(self, merge: bool = True):
        self.merge = merge

    def field_prefix(self, items: list[Token]) -> str:
        """Process a field prefix into the format field:"""
        return f"{items[0].value}:"

    def lucene_clause(self, items: list[Token | str | None]) -> str:
        """Process a single Lucene clause including optional required operator and field prefix."""
        result = ""

        for item in items:
            if isinstance(item, Token):
                result += item.value
            elif isinstance(item, str):
                result += item

        return result.strip()

    def lucene_query(self, items: list[str]) -> str:
        """Merge Lucene query clauses into a single query string."""

        return "(" + " ".join(items).strip() + ")"

    def query(self, items: list[ParseTree | Token]) -> ParseTree:
        if not self.merge:
            return Tree(Token("RULE", "query"), items)

        if len(items) == 1:
            return Tree(Token("RULE", "query"), items)

        left: Tree = items[0]  # type: ignore
        operator: str = items[1].value.strip()  # type: ignore
        right: Tree = items[2]  # type: ignore

        logger.trace("left", left)
        logger.trace("right", right)

        # if the left and right are lucene queries, merge them
        keyword_left = get_keyword_term(left)
        keyword_right = get_keyword_term(right)

        if keyword_left and keyword_right:
            combined = f"{keyword_left} {operator} {keyword_right}"
            return Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "expr"),
                        [
                            Tree(
                                Token("RULE", "term"),
                                [
                                    Token("KEYWORD_OP", "kw"),
                                    Tree(Token("RULE", "keywordterm"), [combined]),
                                ],
                            )
                        ],
                    )
                ],
            )  # type: ignore

        return Tree(Token("RULE", "query"), items)


class QueryAnnotator(Visitor[Token]):
    """
    This visitor goes top-down through the parse tree and annotates each percentile and keyword
    term with its parent operator and side (i.e., evaluation order) in the parent expression.
    """

    def __init__(self) -> None:
        self.parent_operator_docs: str | None = None
        self.current_side_docs: str | None = None
        self.parent_operator_cols: str | None = None
        self.current_side_cols: str | None = None

    def reset(self) -> None:
        self.parent_operator_docs = None
        self.current_side_docs = None
        self.parent_operator_cols = None
        self.current_side_cols = None

    def query(self, tree: ParseTree):
        # TODO: We need to investigate this class because nodes are annotated too often
        # NOTE: Calling visit again in this method will annotate the tree nodes multiple times
        if len(tree.children) == 3:  # Has operator
            if not isinstance(tree.children[1], Token):
                logger.error(f"Expected operator, got: {tree.children[1]}. Aborting annotation.")
                return
            old_parent = self.parent_operator_docs
            old_side = self.current_side_cols

            self.parent_operator_docs = tree.children[1].value

            if isinstance(tree.children[0], Tree):
                logger.trace(f"Visiting left side of query: {tree.children[0]}")
                self.current_side_docs = "left"
                self.visit(tree.children[0])

            # Visit right side
            if isinstance(tree.children[2], Tree):
                logger.trace(f"Visiting right side of query: {tree.children[2]}")
                self.current_side_docs = "right"
                self.visit(tree.children[2])

            self.parent_operator_docs = old_parent
            self.current_side_docs = old_side
        else:
            if isinstance(tree.children[0], Tree):
                self.visit(tree.children[0])

    def column_query(self, tree: ParseTree):
        # TODO: We need to investigate this class because nodes are annotated too often
        # NOTE: Calling visit again in this method will annotate the tree nodes multiple times
        if len(tree.children) == 3:  # Has operator
            if not isinstance(tree.children[1], Token):
                logger.error(f"Expected operator, got: {tree.children[1]}. Aborting annotation.")
                return
            old_parent = self.parent_operator_cols
            old_side = self.current_side_cols

            self.parent_operator_docs = tree.children[1].value

            if isinstance(tree.children[0], Tree):
                self.current_side_cols = "left"
                self.visit(tree.children[0])

            # Visit right side
            if isinstance(tree.children[2], Tree):
                self.current_side_cols = "right"
                self.visit(tree.children[2])

            self.parent_operator_cols = old_parent
            self.current_side_cols = old_side
        else:
            if isinstance(tree.children[0], Tree):
                self.visit(tree.children[0])

    def percentileterm(self, tree: ParseTree) -> None:
        if self.parent_operator_cols:
            tree.children.append(Token("parent_op", self.parent_operator_cols))
            tree.children.append(Token("side", self.current_side_cols))

    def keywordterm(self, tree: ParseTree) -> None:
        if self.parent_operator_docs:
            tree.children.append(Token("parent_op", self.parent_operator_docs))
            tree.children.append(Token("side", self.current_side_docs))

    def columnterm(self, tree: ParseTree) -> None:
        if self.parent_operator_cols:
            tree.children.append(Token("parent_op", self.parent_operator_cols))
            tree.children.append(Token("side", self.current_side_docs))


class QueryExecutor(Transformer[Token, tuple[set[int], Highlights]]):
    """This transformer evaluates the parse tree bottom-up and compute the query result."""

    fainder_mode: FainderMode
    scores: dict[int, float]
    last_result_docs: set[int] | None
    last_result_cols: set[uint32] | None
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
    ):
        self.lucene_connector = lucene_connector
        self.fainder_index = fainder_index
        self.hnsw_index = hnsw_index
        self.metadata = metadata

        self.reset(fainder_mode, enable_highlighting, enable_filtering)

    def _get_doc_filter(self, operator: str | None, side: str | None) -> set[int] | None:
        """Create a document filter for AND operators based on previous results."""
        if (
            not self.enable_filtering
            or not self.last_result_docs
            or operator != "AND"
            or side != "right"
        ):
            return None

        # Only apply filters to the right side of AND operations
        logger.trace(f"Applying filter from previous result: {self.last_result_docs}")
        return self.last_result_docs

    def _get_col_filter(self, operator: str | None, side: str | None) -> set[uint32] | None:
        """Create a column filter for AND operators based on previous results."""
        if (
            not self.enable_filtering
            or not self.last_result_cols
            or operator != "AND"
            or side != "right"
        ):
            return None

        # Only apply filters to the right side of AND operations
        logger.trace(f"Applying filter from previous result: {self.last_result_cols}")
        return self.last_result_cols

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
        enable_filtering: bool = False,
    ) -> None:
        self.scores = defaultdict(float)
        self.last_result_docs = None
        self.last_result_cols = None
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

        hist_filter = None
        if len(items) >= 5 and self.enable_filtering:
            operator = items[-2]
            side = items[-1]
            col_filter = self._get_col_filter(operator, side)
            if col_filter is not None:
                hist_filter = col_to_hist_ids(col_filter, self.metadata.col_to_hist)

        result_hists = self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode, hist_filter
        )

        col_ids = hist_to_col_ids(result_hists, self.metadata.hist_to_col)
        self.last_result_cols = col_ids

        return col_ids

    def keywordterm(self, items: list[Token]) -> tuple[set[int], Highlights]:
        """Evaluate keyword term using merged Lucene query."""
        logger.trace(f"Evaluating keyword term: {items}")
        # Extract the lucene query from items
        query = str(items[0]).strip() if items else ""
        doc_filter = None
        if len(items) >= 3 and self.enable_filtering:
            operator = items[-2]
            side = items[-1]
            logger.trace(f"Operator: {operator}, side: {side}")
            doc_filter = self._get_doc_filter(operator, side)

        result_docs, scores, highlights = self.lucene_connector.evaluate_query(
            query, doc_filter, self.enable_highlighting
        )
        self.updates_scores(result_docs, scores)

        results_docs_set = set(result_docs)
        self.last_result_docs = results_docs_set

        return results_docs_set, (highlights, set())  # Return empty set for column highlights

    def nameterm(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating column term: {items}")
        column = items[0].value.strip()
        k = int(items[1].value.strip())

        column_filter = None
        if len(items) >= 4 and self.enable_filtering:
            operator = items[-2]
            side = items[-1]
            column_filter = self._get_col_filter(operator, side)

        result = self.hnsw_index.search(column, k, column_filter)
        logger.trace(f"Result of column search with column:{column} k:{k}r: {result}")
        self.last_result_cols = result

        return result

    def column_query(self, items: list[set[uint32] | Token]) -> set[uint32]:
        logger.trace(f"Evaluating column expression with {len(items)} items")
        if len(items) == 1 and isinstance(items[0], set):
            return items[0]

        left: set[uint32] = items[0]  # type: ignore
        operator: str = items[1].value.strip()  # type: ignore
        right: set[uint32] = items[2]  # type: ignore

        result: set[uint32]

        match operator:
            case "AND":
                result = left & right
            case "OR":
                result = left | right
            case "XOR":
                result = left ^ right
            case _:  # pyright: ignore[reportUnknownVariableType]
                raise ValueError(f"Unknown operator: {operator}")

        self.last_result_cols = result
        return result

    def col_expr(self, items: list[set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating column expression with {len(items)} items")
        return items[0]

    def not_col_expr(self, items: list[set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating NOT column expression with {len(items)} items")
        to_negate = items[0]
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in self.metadata.col_to_doc}
        result_cols = all_columns - to_negate
        self.last_result_cols = result_cols
        return result_cols

    def columnterm(self, items: tuple[Token, set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating column term with {items} items")
        return items[1]

    def term(
        self, items: tuple[Token, set[uint32] | tuple[set[int], Highlights]]
    ) -> tuple[set[int], Highlights]:
        """Process a term, which can be either a keyword or column operation."""
        # logger.trace(f"Evaluating term with items: {items}")
        operator: str = items[0].value
        doc_ids: set[int]
        if operator.strip().lower() in ["column", "col"]:
            col_ids: set[uint32] = items[1]  # type: ignore
            doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
            self.last_result_docs = doc_ids
            return doc_ids, ({}, col_ids)
        if operator.strip().lower() in ["keyword", "kw"]:
            highlights: Highlights
            doc_ids, highlights = items[1]  # type: ignore
            self.last_result_docs = doc_ids
            return doc_ids, highlights
        raise ValueError(f"Unknown term: {items[0].value}")

    def not_expr(self, items: list[tuple[set[int], Highlights]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating NOT expression with {len(items)} items")
        to_negate, _ = items[0]
        all_docs = set(self.metadata.doc_to_cols.keys())
        result_docs = all_docs - to_negate
        self.last_result_docs = result_docs
        return result_docs, ({}, set())

    def expr(self, items: list[tuple[set[int], Highlights]]) -> tuple[set[int], Highlights]:
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
            case _:  # pyright: ignore[reportUnknownVariableType]
                raise ValueError(f"Unknown operator: {operator}")

        if self.enable_highlighting:
            result_highlights = self._merge_highlights(
                left_highlights, right_highlights, result_set
            )
            return result_set, result_highlights
        return result_set, ({}, set())

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
