from collections import defaultdict
from collections.abc import Sequence
from operator import and_, or_

from lark import ParseTree, Token, Transformer
from loguru import logger
from numpy import uint32
from numpy.typing import NDArray

from backend.config import ColumnHighlights, DocumentHighlights, FainderMode, Metadata
from backend.engine.conversion import col_to_doc_ids, doc_to_col_ids
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .common import (
    ColResult,
    DocResult,
    ResultGroupAnnotator,
    TResult,
    exceeds_filtering_limit,
    junction,
)
from .executor import Executor


class IntermediateResult:
    """Intermediate results for prefiltering.

    Only one of doc_ids or col_ids should be set. If multiple are set, this should result in an
    error.
    """

    def __init__(
        self,
        fainder_mode: FainderMode,
        doc_ids: set[int] | None = None,
        col_ids: set[uint32] | None = None,
    ) -> None:
        self.fainder_mode = fainder_mode
        if doc_ids is None and col_ids is None:
            raise ValueError("doc_ids and col_ids cannot both be None")
        if doc_ids is not None and col_ids is not None:
            raise ValueError("doc_ids and col_ids cannot both be set")

        self._doc_ids: set[int] | None = (
            None
            if doc_ids is not None
            and exceeds_filtering_limit(doc_ids, "num_doc_ids", fainder_mode)
            else doc_ids
        )
        self._col_ids: set[uint32] | None = (
            None
            if col_ids is not None
            and exceeds_filtering_limit(col_ids, "num_col_ids", fainder_mode)
            else col_ids
        )

    def add_col_ids(self, col_ids: set[uint32], doc_to_cols: dict[int, set[int]]) -> None:
        if self._doc_ids is not None:
            helper_col_ids = doc_to_col_ids(self._doc_ids, doc_to_cols)
            col_ids = col_ids.intersection(helper_col_ids)
        if self._col_ids is not None:
            col_ids = col_ids.intersection(self._col_ids)
        self._col_ids = col_ids
        self._doc_ids = None

    def add_doc_ids(self, doc_ids: set[int], col_to_doc: NDArray[uint32]) -> None:
        if self._col_ids is not None:
            helper_doc_ids = col_to_doc_ids(self._col_ids, col_to_doc)
            doc_ids = doc_ids.intersection(helper_doc_ids)
        if self._doc_ids is not None:
            doc_ids = doc_ids.intersection(self._doc_ids)
        self._doc_ids = doc_ids
        self._col_ids = None

    def build_hist_filter(self, metadata: Metadata) -> set[uint32] | None:
        """Build a histogram filter from the intermediate results."""
        if self._col_ids is not None:
            if exceeds_filtering_limit(self._col_ids, "num_col_ids", self.fainder_mode):
                return None
            return self._col_ids
        if self._doc_ids is not None:
            if exceeds_filtering_limit(self._doc_ids, "num_doc_ids", self.fainder_mode):
                return None
            return doc_to_col_ids(self._doc_ids, metadata.doc_to_cols)
        return None

    def is_empty(self) -> bool:
        """Check if the intermediate result is empty."""
        return self._col_ids is None and self._doc_ids is None

    def __str__(self) -> str:
        """String representation of the intermediate result."""
        return f"IntermediateResult(\n\tdoc_ids={self._doc_ids},\n\tcol_ids={self._col_ids}\n)"


class IntermediateResultStore:
    """Store intermediate results for prefiltering per group."""

    def __init__(self, fainder_mode: FainderMode, write_groups_used: dict[int, int]) -> None:
        self.results: dict[int, IntermediateResult] = {}
        self.fainder_mode = fainder_mode
        self.write_groups_used = write_groups_used
        self.write_groups_actually_used: dict[int, int] = {}

    def add_col_id_results(
        self, write_group: int, col_ids: set[uint32], doc_to_cols: dict[int, set[int]]
    ) -> None:
        logger.trace(
            "Adding column IDs to write group {} length of col_ids: {}", write_group, len(col_ids)
        )
        if write_group not in self.write_groups_used:
            raise ValueError("Write group {} is not used", write_group)

        if write_group in self.write_groups_used and self.write_groups_used[write_group] < 1:
            logger.trace("Write group {} is not used, skipping adding column IDs", write_group)
            return

        if exceeds_filtering_limit(col_ids, "num_col_ids", self.fainder_mode):
            logger.trace("Column IDs exceed filtering limit, skipping adding column IDs")
            return

        logger.trace("Write group {} is used, adding column IDs", write_group)
        if write_group in self.results:
            self.results[write_group].add_col_ids(col_ids=col_ids, doc_to_cols=doc_to_cols)
        else:
            self.results[write_group] = IntermediateResult(
                col_ids=col_ids, fainder_mode=self.fainder_mode
            )

    def add_doc_id_results(
        self, write_group: int, doc_ids: set[int], col_to_doc: NDArray[uint32]
    ) -> None:
        logger.trace(
            "Adding document IDs to write group {} length of doc_ids: {}",
            write_group,
            len(doc_ids),
        )
        if write_group not in self.write_groups_used:
            raise ValueError("Write group {} is not used", write_group)

        if write_group in self.write_groups_used and self.write_groups_used[write_group] < 1:
            logger.trace("Write group {} is not used, skipping adding document IDs", write_group)
            return

        if exceeds_filtering_limit(doc_ids, "num_doc_ids", self.fainder_mode):
            logger.trace("Document IDs exceed filtering limit, skipping adding document IDs")
            return

        logger.trace("Write group {} is used, adding document IDs", write_group)
        if write_group in self.results:
            self.results[write_group].add_doc_ids(doc_ids=doc_ids, col_to_doc=col_to_doc)
        else:
            self.results[write_group] = IntermediateResult(
                doc_ids=doc_ids, fainder_mode=self.fainder_mode
            )

    def build_hist_filter(self, read_groups: list[int], metadata: Metadata) -> set[uint32] | None:
        """Build a histogram filter from the intermediate results."""
        hist_filter: set[uint32] | None = None
        if len(read_groups) == 0:
            raise ValueError("Cannot build a hist filter without read groups")

        for read_group in read_groups:
            if read_group not in self.results or self.results[read_group].is_empty():
                # This means this group does not have an intermediate result yet this happens alot
                logger.trace(
                    "Read group {} does not have an intermediate result, skipping", read_group
                )
                continue

            logger.trace(
                "Processing read group {} with results {}", read_group, self.results[read_group]
            )
            intermediate = self.results[read_group].build_hist_filter(metadata)

            logger.trace(
                "Intermediate result size: {}", len(intermediate) if intermediate else "None"
            )
            self.write_groups_actually_used[read_group] = (
                self.write_groups_actually_used.get(read_group, 0) + 1
            )

            if intermediate is None:
                continue

            if len(intermediate) == 0:
                return set()

            if hist_filter is None:
                hist_filter = intermediate
            else:
                hist_filter &= intermediate

        return hist_filter


class PrefilteringExecutor(Transformer[Token, DocResult], Executor):
    """Uses prefiltering to reduce the number of documents before executing the query."""

    def __init__(
        self,
        tantivy_index: TantivyIndex,
        fainder_index: FainderIndex,
        hnsw_index: HnswIndex,
        metadata: Metadata,
        fainder_mode: FainderMode = FainderMode.LOW_MEMORY,
        enable_highlighting: bool = False,
        min_usability_score: float = 0.0,
        rank_by_usability: bool = True,
    ) -> None:
        self.tantivy_index = tantivy_index
        self.fainder_index = fainder_index
        self.hnsw_index = hnsw_index
        self.metadata = metadata
        self.min_usability_score = min_usability_score
        self.rank_by_usability = rank_by_usability

        self.reset(fainder_mode, enable_highlighting)

    def reset(self, fainder_mode: FainderMode, enable_highlighting: bool = False) -> None:
        logger.trace("Resetting executor")
        self.scores: dict[int, float] = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting
        self.intermediate_results = IntermediateResultStore(fainder_mode, {})
        self.write_groups: dict[int, int] = {}
        self.read_groups: dict[int, list[int]] = {}
        self.parent_write_group: dict[int, int] = {}

    def _get_write_group(self, node: ParseTree | Token) -> int:
        """Get the write group for a node."""
        node_id = id(node)
        if node_id in self.write_groups:
            return self.write_groups[node_id]
        logger.warning("Node {} does not have a write group with id {}", node, node_id)
        logger.warning("Write groups: {}", self.write_groups)
        raise ValueError("Node does not have a write group")

    def _get_read_groups(self, node: ParseTree | Token) -> list[int]:
        """Get the read groups for a node."""
        node_id = id(node)
        if node_id in self.read_groups:
            return self.read_groups[node_id]
        logger.warning("Node {} does not have read groups", node)
        logger.warning("Read groups: {}", self.read_groups)
        raise ValueError("Node does not have read groups")

    def _get_parent_write_group(self, write_group: int) -> int:
        """Get the parent write group for a write group."""
        if write_group in self.parent_write_group:
            return self.parent_write_group[write_group]
        logger.warning("Write group {} does not have a parent write group", write_group)
        logger.warning("Parent write groups: {}", self.parent_write_group)
        raise ValueError("Write group does not have a parent write group")

    def _clean_items(self, items: Sequence[tuple[TResult, int]]) -> tuple[Sequence[TResult], int]:
        """Helper function to clean items for conjunction and disjunction."""
        clean_times: list[TResult] = []
        write_group = 0
        for item in items:
            clean_times.append(item[0])
            # NOTE: The write group is the same for all items in the input sequence
            write_group = item[1]

        return clean_times, write_group

    def execute(self, tree: ParseTree) -> DocResult:
        """Start processing the parse tree."""
        self.write_groups = {}
        self.read_groups = {}
        logger.trace(tree.pretty())
        groups = ResultGroupAnnotator()
        groups.apply(tree, parallel=True)
        self.write_groups = groups.write_groups
        self.read_groups = groups.read_groups
        self.parent_write_group = groups.parent_write_group
        self.intermediate_results.write_groups_used = groups.write_groups_used
        logger.trace("Write groups: {}", self.write_groups)
        logger.trace("Read groups: {}", self.read_groups)
        logger.trace("Parent write groups: {}", self.parent_write_group)
        logger.trace("Write groups used: {}", self.intermediate_results.write_groups_used)

        result = self.transform(tree)

        self.write_groups_actually_used = self.intermediate_results.write_groups_actually_used
        self.write_groups_used = self.intermediate_results.write_groups_used
        logger.trace("Write groups actually used: {}", self.write_groups_actually_used)
        logger.trace("Write groups used: {}", self.write_groups_used)

        return result

    ##########################
    # Operator implementations
    ##########################

    def keyword_op(self, items: list[Token]) -> tuple[DocResult, int]:
        logger.trace("Evaluating keyword term: {}", items)

        result_docs, scores, highlights = self.tantivy_index.search(
            items[0], self.enable_highlighting, self.min_usability_score, self.rank_by_usability
        )
        self.updates_scores(result_docs, scores)

        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_doc_id_results(
            write_group, set(result_docs), self.metadata.col_to_doc
        )

        parent_write_group = self._get_parent_write_group(write_group)

        return (set(result_docs), (highlights, set())), parent_write_group

    def col_op(self, items: list[tuple[ColResult, int]]) -> tuple[DocResult, int]:
        logger.trace("Evaluating column term")

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        col_ids = items[0][0]
        write_group = items[0][1]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        self.intermediate_results.add_doc_id_results(
            write_group, doc_ids, self.metadata.col_to_doc
        )
        parent_write_group = self._get_parent_write_group(write_group)
        if self.enable_highlighting:
            return (doc_ids, ({}, col_ids)), parent_write_group

        return (doc_ids, ({}, set())), parent_write_group

    def name_op(self, items: list[Token]) -> tuple[ColResult, int]:
        logger.trace("Evaluating column term: {}", items)

        column = items[0]
        k = int(items[1])

        result = self.hnsw_index.search(column, k, None)

        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_col_id_results(
            write_group, result, self.metadata.doc_to_cols
        )
        parent_write_group = self._get_parent_write_group(write_group)
        return result, parent_write_group

    def percentile_op(self, items: list[Token]) -> tuple[ColResult, int]:
        logger.trace("Evaluating percentile term: {}", items)

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])
        hist_filter = self.intermediate_results.build_hist_filter(
            self._get_read_groups(items[0]), self.metadata
        )

        write_group = self._get_write_group(items[0])
        if hist_filter is not None and len(hist_filter) == 0:
            logger.trace("Empty histogram filter, returning empty result")
            return set(), write_group

        logger.trace(
            "Length of histogram filter: {}",
            len(hist_filter) if hist_filter is not None else "None",
        )
        result = self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode, hist_filter
        )
        self.intermediate_results.add_col_id_results(
            write_group, result, self.metadata.doc_to_cols
        )
        parent_write_group = self._get_parent_write_group(write_group)
        return result, parent_write_group

    def conjunction(self, items: Sequence[tuple[TResult, int]]) -> tuple[TResult, int]:
        logger.trace("Evaluating conjunction with items: {}", len(items))

        clean_items, write_group = self._clean_items(items)
        result = junction(clean_items, and_, self.enable_highlighting, self.metadata.doc_to_cols)
        if isinstance(result, tuple):
            self.intermediate_results.add_doc_id_results(
                write_group, result[0], self.metadata.col_to_doc
            )
        else:
            self.intermediate_results.add_col_id_results(
                write_group, result, self.metadata.doc_to_cols
            )

        return result, self._get_parent_write_group(write_group)

    def disjunction(self, items: Sequence[tuple[TResult, int]]) -> tuple[TResult, int]:
        logger.trace("Evaluating disjunction with items: {}", len(items))

        clean_items, write_group = self._clean_items(items)
        result = junction(clean_items, or_, self.enable_highlighting, self.metadata.doc_to_cols)

        if isinstance(result, tuple):
            self.intermediate_results.add_doc_id_results(
                write_group, result[0], self.metadata.col_to_doc
            )
        else:
            self.intermediate_results.add_col_id_results(
                write_group, result, self.metadata.doc_to_cols
            )

        return result, self._get_parent_write_group(write_group)

    def negation(self, items: Sequence[tuple[TResult, int]]) -> tuple[TResult, int]:
        logger.trace("Evaluating negation with {} items", len(items))

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")

        clean_items, write_group = self._clean_items(items)
        if isinstance(clean_items[0], tuple):
            to_negate, _ = clean_items[0]
            all_docs = set(self.metadata.doc_to_cols.keys())
            # Result highlights are reset for negated results
            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = set()
            doc_result = all_docs.difference(to_negate)
            self.intermediate_results.add_doc_id_results(
                write_group, doc_result, self.metadata.col_to_doc
            )

            result = (doc_result, (doc_highlights, col_highlights))
            return result, self._get_parent_write_group(write_group)

        to_negate_cols: ColResult = clean_items[0]
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in range(len(self.metadata.col_to_doc))}
        result_col = all_columns - to_negate_cols
        self.intermediate_results.add_col_id_results(
            write_group, result_col, self.metadata.doc_to_cols
        )

        return result_col, self._get_parent_write_group(write_group)

    def query(self, items: list[tuple[DocResult, int]]) -> DocResult:
        logger.trace("Evaluating query with {} items", len(items))

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return items[0][0]
