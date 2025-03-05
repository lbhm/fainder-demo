import re
from collections import defaultdict
from collections.abc import Callable, Sequence
from functools import lru_cache, reduce
from operator import and_, or_
from typing import Any, TypeGuard, TypeVar

from lark import ParseTree, Token, Transformer, Tree, Visitor
from loguru import logger
from numpy import uint32

from backend.column_index import ColumnIndex
from backend.config import CacheInfo, FainderMode, Metadata
from backend.engine.parser import DQLParser
from backend.fainder_index import FainderIndex
from backend.lucene_connector import LuceneConnector

DocumentHighlights = dict[int, dict[str, str]]
ColumnHighlights = set[uint32]
Highlights = tuple[DocumentHighlights, ColumnHighlights]

T = TypeVar("T", tuple[set[int], Highlights], set[uint32])


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
        self.parser = DQLParser()
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
        return self.parser.parse(query)

    def _execute(
        self,
        query: str,
        fainder_mode: FainderMode = FainderMode.low_memory,
        enable_highlighting: bool = False,
        enable_filtering: bool = False,
    ) -> tuple[list[int], Highlights]:
        # Reset state for new query
        self.annotator.reset()
        self.executor.reset(fainder_mode, enable_highlighting, enable_filtering)

        # Parse query
        parse_tree = self.parse(query)
        logger.trace(f"Parsed query: {parse_tree}")

        # Optimze query
        # TODO: Add optimizer class
        # TODO: Do we need visit_topdown here?
        self.annotator.visit(parse_tree)
        logger.trace(f"Optimized query: {parse_tree}")

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

    TODO: This class needs to be completely reworked. It is currently not used in query execution.
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
            self.parent_operator = tree.children[1]

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
    last_result: set[int] | set[uint32] | None  # Maybe rename this to intermediate_result
    current_side: str | None

    def __init__(
        self,
        lucene_connector: LuceneConnector,
        fainder_index: FainderIndex,
        hnsw_index: ColumnIndex,
        metadata: Metadata,
        fainder_mode: FainderMode = FainderMode.low_memory,
        enable_highlighting: bool = False,
        enable_filtering: bool = False,
    ) -> None:
        self.lucene_connector = lucene_connector
        self.fainder_index = fainder_index
        self.hnsw_index = hnsw_index
        self.metadata = metadata

        self.reset(fainder_mode, enable_highlighting, enable_filtering)

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

    ### Operator implementations ###

    def keyword_op(self, items: list[Token]) -> tuple[set[int], Highlights]:
        """Evaluate keyword term using merged Lucene query."""
        logger.trace(f"Evaluating keyword term: {items}")

        # Extract the Lucene query and remove quotes
        # NOTE: Our grammar ensures that the string is always quoted so it should not remove
        # legitimate quotes from the query
        query = str(items[0])[1:-1]

        # NOTE: Currently unused
        doc_filter = None

        result_docs, scores, highlights = self.lucene_connector.evaluate_query(
            query, doc_filter, self.enable_highlighting
        )
        self.updates_scores(result_docs, scores)

        # TODO: update last_result
        return set(result_docs), (highlights, set())  # Return empty set for column highlights

    def col_op(self, items: list[set[uint32]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating column term: {items}")

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        col_ids = items[0]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        if self.enable_highlighting:
            return doc_ids, ({}, col_ids)

        return doc_ids, ({}, set())

    def name_op(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating column term: {items}")

        # Remove quotes (see keyword_op for reference)
        column = str(items[0])[1:-1]
        k = int(items[1])

        # NOTE: Currently unused
        column_filter = None

        result = self.hnsw_index.search(column, k, column_filter)

        # TODO: update last_result
        return result  # noqa: RET504

    def percentile_op(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating percentile term: {items}")

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])

        # NOTE: Currently unused
        hist_filter = None

        result_hists = self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode, hist_filter
        )

        # TODO: update last_result
        return hist_to_col_ids(result_hists, self.metadata.hist_to_col)

    def conjunction(
        self, items: list[tuple[set[int], Highlights]] | list[set[uint32]]
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating conjunction with items: {items}")

        return self._junction(items, and_)

    def disjunction(
        self, items: list[tuple[set[int], Highlights]] | list[set[uint32]]
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating disjunction with items: {items}")

        return self._junction(items, or_)

    def negation(self, items: list[T]) -> T:
        logger.trace(f"Evaluating negation with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")
        if isinstance(items[0], tuple):
            to_negate, _ = items[0]
            all_docs = set(self.metadata.doc_to_cols.keys())
            # Result highlights are reset for negated results
            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = set()
            return all_docs - to_negate, (doc_highlights, col_highlights)

        to_negate_cols = items[0]
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in self.metadata.col_to_doc}
        return all_columns - to_negate_cols

    def query(self, items: list[tuple[set[int], Highlights]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating query with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return items[0]

    def _junction(
        self,
        items: list[tuple[set[int], Highlights]] | list[set[uint32]],
        operator: Callable[[Any, Any], Any],
    ) -> tuple[set[int], Highlights] | set[uint32]:
        if len(items) < 2:
            raise ValueError("Junction must have at least two items")

        # Items contains table results (i.e., tuple[set[int], Highlights])
        if self._is_table_result(items):
            if self.enable_highlighting:
                # Initialize result with first item
                doc_ids: set[int] = items[0][0]
                highlights: Highlights = items[0][1]

                # Merge all other items
                for item in items[1:]:
                    doc_ids = operator(doc_ids, item[0])
                    highlights = self._merge_highlights(highlights, item[1], doc_ids)

                return doc_ids, highlights

            return reduce(operator, [item[0] for item in items]), ({}, set())

        # Items contains column results (i.e., set[uint32])
        return reduce(operator, items)

    def _is_table_result(self, val: list[Any]) -> TypeGuard[list[tuple[set[int], Highlights]]]:
        return all(isinstance(item, tuple) for item in val)

    def _merge_highlights(
        self, left: Highlights, right: Highlights, doc_ids: set[int]
    ) -> Highlights:
        """Merge highlights for documents that are in the result set."""
        pattern = r"<mark>(.*?)</mark>"
        regex = re.compile(pattern, re.DOTALL)

        # Merge document highlights
        doc_highlights: DocumentHighlights = {}
        left_doc_highlights = left[0]
        right_doc_highlights = right[0]
        for doc_id in doc_ids:
            left_highlights = left_doc_highlights.get(doc_id, {})
            right_highlights = right_doc_highlights.get(doc_id, {})

            # Only process if either side has highlights
            if left_highlights or right_highlights:
                merged_highlights = {}

                # Process each field that appears in either highlight set
                all_keys = set(left_highlights.keys()) | set(right_highlights.keys())
                for key in all_keys:
                    left_text = left_highlights.get(key, "")
                    right_text = right_highlights.get(key, "")

                    # If either text is empty, use the non-empty one
                    if not left_text:
                        merged_highlights[key] = right_text
                        continue
                    if not right_text:
                        merged_highlights[key] = left_text
                        continue

                    # Both texts have content, merge their marks
                    # Extract all marked words from right text
                    right_marks = set(regex.findall(right_text))

                    # Add marks from right text to left text
                    for word in right_marks:
                        if f"<mark>{word}</mark>" not in left_text:
                            # Word isn't marked yet
                            left_text = left_text.replace(word, f"<mark>{word}</mark>")

                    merged_highlights[key] = left_text

                doc_highlights[doc_id] = merged_highlights

        # Merge column highlights
        col_highlights = left[1] | right[1]
        col_highlights &= doc_to_col_ids(doc_ids, self.metadata.doc_to_cols)

        return doc_highlights, col_highlights

    def _get_column_filter(
        self, operator: str | None, side: str | None
    ) -> set[int] | set[uint32] | None:
        """Create a document filter for AND operators based on previous results.
        NOTE: Currently unused
        """
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
