import os
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np
from lark import ParseTree, Token, Transformer
from loguru import logger
from numpy.typing import NDArray

from backend.config import (
    ColumnArray,
    ColumnHighlights,
    DocumentArray,
    DocumentHighlights,
    FainderMode,
    Metadata,
)
from backend.engine.conversion import col_to_doc_ids, col_to_hist_ids, doc_to_col_ids
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .common import (
    ColResult,
    DocResult,
    ResultGroupAnnotator,
    TResult,
    exceeds_filtering_limit,
    junction,
    negate_array,
    reduce_arrays,
)
from .executor import Executor


class IntermediateResultFuture:
    """Stores futures and results for intermediate results during parallel execution."""

    def __init__(
        self,
        write_group: int,
        fainder_mode: FainderMode,
        doc_ids: DocumentArray | None = None,
        col_ids: ColumnArray | None = None,
    ) -> None:
        # resolved results trump futures
        self.write_group = write_group
        self.kw_result_futures: list[Future[tuple[DocResult, int]]] = []
        self.col_result_futures: list[Future[tuple[ColResult, int]]] = []

        # Store resolved results only one of these should be set
        self._doc_ids: DocumentArray | None = (
            None
            if doc_ids is not None
            and exceeds_filtering_limit(doc_ids, "num_doc_ids", fainder_mode)
            else doc_ids
        )
        self._col_ids: ColumnArray | None = (
            None
            if col_ids is not None
            and exceeds_filtering_limit(col_ids, "num_col_ids", fainder_mode)
            else col_ids
        )

        self.fainder_mode = fainder_mode

    def add_doc_future(self, future: Future[tuple[DocResult, int]]) -> None:
        """Add a future that will resolve to document IDs."""
        self.kw_result_futures.append(future)

    def add_col_future(self, future: Future[tuple[ColResult, int]]) -> None:
        """Add a future that will resolve to column IDs."""
        self.col_result_futures.append(future)

    def add_col_ids(self, col_ids: ColumnArray, doc_to_cols: list[NDArray[np.uint32]]) -> None:
        if self._doc_ids is not None:
            helper_col_ids = doc_to_col_ids(self._doc_ids, doc_to_cols)
            col_ids = reduce_arrays([helper_col_ids, col_ids], "and")
        if self._col_ids is not None:
            col_ids = reduce_arrays([col_ids, self._col_ids], "and")
        self._col_ids = col_ids
        self._doc_ids = None

    def add_doc_ids(self, doc_ids: DocumentArray, col_to_doc: NDArray[np.uint32]) -> None:
        if self._col_ids is not None:
            helper_doc_ids = col_to_doc_ids(self._col_ids, col_to_doc)
            doc_ids = reduce_arrays([doc_ids, helper_doc_ids], "and")
        if self._doc_ids is not None:
            doc_ids = reduce_arrays([doc_ids, self._doc_ids], "and")
        self._doc_ids = doc_ids
        self._col_ids = None

    def _build_hist_filter_resolved(self, metadata: Metadata) -> ColResult | None:
        if self._doc_ids is not None:
            if exceeds_filtering_limit(self._doc_ids, "num_doc_ids", self.fainder_mode):
                return None
            return doc_to_col_ids(self._doc_ids, metadata.doc_to_cols)
        if self._col_ids is not None:
            if exceeds_filtering_limit(self._col_ids, "num_col_ids", self.fainder_mode):
                return None
            return self._col_ids
        return None

    def _build_hist_filter_future(self, metadata: Metadata) -> ColResult | None:
        hist_ids: list[ColumnArray] = []
        first = True
        for kw_future in self.kw_result_futures:
            doc_ids, _ = kw_future.result()
            if exceeds_filtering_limit(doc_ids[0], "num_doc_ids", self.fainder_mode):
                continue
            col_ids = doc_to_col_ids(doc_ids[0], metadata.doc_to_cols)
            new_hist_ids = col_to_hist_ids(col_ids, metadata.num_hists)
            if first:
                hist_ids = [new_hist_ids]
                first = False
            else:
                hist_ids.append(new_hist_ids)

        for col_future in self.col_result_futures:
            col_ids, _ = col_future.result()
            if exceeds_filtering_limit(col_ids, "num_col_ids", self.fainder_mode):
                continue
            new_hist_ids = col_to_hist_ids(col_ids, metadata.num_hists)
            if first:
                hist_ids = [new_hist_ids]
                first = False
            else:
                hist_ids.append(new_hist_ids)

        # not resolve the pp_result_futures

        if first:
            return None
        filter_result = reduce_arrays(hist_ids, "and")
        if exceeds_filtering_limit(filter_result, "num_col_ids", self.fainder_mode):
            return None
        return filter_result

    def build_hist_filter(self, metadata: Metadata) -> ColResult | None:
        """Build a histogram filter from the intermediate results."""
        hist_ids_resolved = self._build_hist_filter_resolved(metadata)
        if hist_ids_resolved is not None:
            return hist_ids_resolved

        return self._build_hist_filter_future(metadata)

    def is_empty(self) -> bool:
        """Check if the intermediate result is empty."""
        return (
            self._doc_ids is None
            and self._col_ids is None
            and len(self.kw_result_futures) == 0
            and len(self.col_result_futures) == 0
        )  # not checking pp_result_futures becuase they are irrelevant for the histogram filter

    def __str__(self) -> str:
        """String representation of the intermediate result future."""
        return (
            f"IntermediateResultFuture(\n\twrite_group={self.write_group},"
            f"\n\tdoc_ids={self._doc_ids},\n\tcol_ids={self._col_ids},\n\t,"
            f"\n\tkw_futures={len(self.kw_result_futures)},\n\t"
            f"col_futures={len(self.col_result_futures)},\n"
        )


class IntermediateResultStoreFuture:
    """Stores futures and results for intermediate results during parallel execution."""

    def __init__(self, fainder_mode: FainderMode, write_groups_used: dict[int, int]) -> None:
        self.results: dict[int, IntermediateResultFuture] = {}
        self.fainder_mode = fainder_mode
        self.write_groups_used = write_groups_used
        self.write_groups_actually_used: dict[int, int] = {}

    def add_future_kw_result(
        self, write_group: int, future: Future[tuple[DocResult, int]]
    ) -> None:
        """Add a future that will resolve to document IDs."""
        if write_group not in self.write_groups_used:
            raise ValueError(f"Write group {write_group} is not used")

        if write_group in self.write_groups_used and self.write_groups_used[write_group] < 1:
            logger.trace("Write group {} is not used, skipping adding column IDs", write_group)
            return

        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(
                write_group, fainder_mode=self.fainder_mode
            )
        self.results[write_group].add_doc_future(future)

    def add_future_col_result(
        self, write_group: int, future: Future[tuple[ColResult, int]]
    ) -> None:
        """Add a future that will resolve to column IDs."""
        if write_group not in self.write_groups_used:
            raise ValueError(f"Write group {write_group} is not used")

        if write_group in self.write_groups_used and self.write_groups_used[write_group] < 1:
            logger.trace("Write group {} is not used, skipping adding column IDs", write_group)
            return

        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(
                write_group, fainder_mode=self.fainder_mode
            )
        self.results[write_group].add_col_future(future)

    def add_col_ids(
        self, write_group: int, col_ids: ColumnArray, doc_to_cols: list[NDArray[np.uint32]]
    ) -> None:
        """Add column IDs to the intermediate result."""
        if write_group not in self.write_groups_used:
            raise ValueError(f"Write group {write_group} is not used")

        if write_group in self.write_groups_used and self.write_groups_used[write_group] < 1:
            logger.trace("Write group {} is not used, skipping adding column IDs", write_group)
            return

        if exceeds_filtering_limit(col_ids, "num_col_ids", self.fainder_mode):
            logger.trace("Column IDs exceed filtering limit: {}", len(col_ids))
            return

        logger.trace("Write group {} is used, adding column IDs", write_group)
        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(
                write_group, col_ids=col_ids, fainder_mode=self.fainder_mode
            )
        else:
            self.results[write_group].add_col_ids(col_ids, doc_to_cols)
        logger.trace("Adding column IDs to write group {}: length {}", write_group, len(col_ids))

    def add_doc_ids(
        self, write_group: int, doc_ids: DocumentArray, col_to_doc: NDArray[np.uint32]
    ) -> None:
        """Add document IDs to the intermediate result."""
        if write_group not in self.write_groups_used:
            raise ValueError(f"Write group {write_group} is not used")

        if write_group in self.write_groups_used and self.write_groups_used[write_group] < 1:
            logger.trace("Write group {} is not used, skipping adding document IDs", write_group)
            return

        if exceeds_filtering_limit(doc_ids, "num_doc_ids", self.fainder_mode):
            logger.trace("Document IDs exceed filtering limit: {}", len(doc_ids))
            return

        logger.trace("Write group {} is used, adding document IDs", write_group)
        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(
                write_group, doc_ids=doc_ids, fainder_mode=self.fainder_mode
            )
        else:
            self.results[write_group].add_doc_ids(doc_ids, col_to_doc)
        logger.trace("Adding document IDs to write group {}: length {}", write_group, len(doc_ids))

    def get_hist_filter(self, read_groups: list[int], metadata: Metadata) -> ColResult | None:
        """Build a histogram filter from the intermediate results."""
        hist_filter: ColResult | None = None
        if len(read_groups) == 0:
            return hist_filter

        logger.trace("read groups {}", read_groups)
        for read_group in read_groups:
            if read_group not in self.results or self.results[read_group].is_empty():
                logger.trace(
                    "Read group {} does not have an intermediate result, skipping", read_group
                )
                continue

            logger.trace(
                "Processing read group {} with results {}", read_group, self.results[read_group]
            )
            intermediate = self.results[read_group].build_hist_filter(metadata)

            self.write_groups_actually_used[read_group] = (
                self.write_groups_actually_used.get(read_group, 0) + 1
            )

            if intermediate is None:
                continue

            logger.trace(
                "Intermediate length: {}",
                intermediate.size,
            )
            if hist_filter is None:
                hist_filter = intermediate
            else:
                hist_filter = reduce_arrays([hist_filter, intermediate], "and")

        logger.trace(
            "Hist filter length: {}", (hist_filter.size if hist_filter is not None else "None")
        )
        return hist_filter


class ThreadedPrefilteringExecutor(Transformer[Token, DocResult], Executor):
    """This transformer evaluates a parse tree bottom-up and computes results in parallel threads.

    It also uses prefiltering to reduce the number of documents before executing the query for
    percentile predicates.
    """

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
        max_workers: int = os.cpu_count() or 1,
    ) -> None:
        self.tantivy_index = tantivy_index
        self.fainder_index = fainder_index
        self.hnsw_index = hnsw_index
        self.metadata = metadata
        self.write_groups: dict[int, int] = {}
        self.read_groups: dict[int, list[int]] = {}
        self.parent_write_group: dict[int, int] = {}
        self.min_usability_score = min_usability_score
        self.rank_by_usability = rank_by_usability
        self.max_workers = max_workers
        # Create a new thread pool for this execution
        self._thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)

        self.reset(fainder_mode, enable_highlighting)

    def __del__(self) -> None:
        """Clean up the thread pool when the executor is deleted."""
        self._thread_pool.shutdown(wait=True)
        logger.debug("Thread pool shut down")

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
        fainder_index_name: str = "default",
    ) -> None:
        self.fainder_index_name = fainder_index_name
        self.scores = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting
        self.intermediate_results = IntermediateResultStoreFuture(
            fainder_mode=fainder_mode, write_groups_used={}
        )

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
        logger.trace("Write groups used: {}", groups.write_groups_used)
        logger.trace("Write groups: {}", self.write_groups)
        logger.trace("Read groups: {}", self.read_groups)
        logger.trace("Parent write groups: {}", self.parent_write_group)
        # create intermediate results for all write groups
        for write_group in self.write_groups.values():
            self.intermediate_results.results[write_group] = IntermediateResultFuture(
                write_group, self.fainder_mode
            )

        result = self.transform(tree)

        self.write_groups_actually_used = self.intermediate_results.write_groups_actually_used
        self.write_groups_used = self.intermediate_results.write_groups_used
        logger.trace("Write groups actually used: {}", self.write_groups_actually_used)
        logger.trace("Write groups used: {}", self.write_groups_used)

        return result

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

    def _resolve_items(
        self, items: Sequence[tuple[TResult, int] | Future[tuple[TResult, int]]]
    ) -> tuple[Sequence[TResult], int]:
        """Resolve items from futures."""
        clean_item: list[TResult] = []
        write_group = 0
        for item in items:
            resolved_item = item.result() if isinstance(item, Future) else item
            clean_item.append(resolved_item[0])
            # NOTE: The write group is the same for all items in the input sequence
            write_group = resolved_item[1]

        return clean_item, write_group

    def _resolve_item(
        self, item: tuple[TResult, int] | Future[tuple[TResult, int]]
    ) -> tuple[TResult, int]:
        """Resolve item from future."""
        return item.result() if isinstance(item, Future) else item

    ##########################
    # Operator implementations
    ##########################

    def keyword_op(self, items: list[Token]) -> Future[tuple[DocResult, int]]:
        def _keyword_task(token: Token) -> tuple[DocResult, int]:
            """Task function for keyword search to be run in a thread."""
            logger.trace("Thread executing keyword search for: {}", token)
            write_group = self._get_write_group(token)
            result_docs, scores, highlights = self.tantivy_index.search(
                token, self.enable_highlighting, self.min_usability_score, self.rank_by_usability
            )
            self.updates_scores(result_docs, scores)
            parent_write_group = self._get_parent_write_group(write_group)
            return (result_docs, (highlights, np.array([], dtype=np.uint32))), parent_write_group

        logger.trace("Evaluating keyword term: {}", items)

        # Submit task to thread pool and store the future with a unique ID
        future = self._thread_pool.submit(_keyword_task, items[0])

        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_future_kw_result(write_group, future)
        return future

    def name_op(self, items: list[Token]) -> Future[tuple[ColResult, int]]:
        def _name_task(column: Token, k: int) -> tuple[ColResult, int]:
            """Task function for column name search to be run in a thread."""
            logger.trace("Thread executing column name search for: {}", column)
            write_group = self._get_write_group(column)
            parent_write_group = self._get_parent_write_group(write_group)
            return self.hnsw_index.search(column, k, None), parent_write_group

        logger.trace("Evaluating column name term: {}", items)

        column = items[0]
        k = int(items[1])

        # Submit task to thread pool and store the future with a unique ID
        future = self._thread_pool.submit(_name_task, column, k)
        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_future_col_result(write_group, future)
        return future

    def percentile_op(self, items: list[Token]) -> Future[tuple[ColResult, int]]:
        def _percentile_task(items: list[Token]) -> tuple[ColResult, int]:
            """Task function for percentile search to be run in a thread."""
            percentile = float(items[0])
            comparison: str = items[1]
            reference = float(items[2])
            logger.trace(
                "Thread executing percentile search with {} {} {}",
                percentile,
                comparison,
                reference,
            )
            hist_filter = self.intermediate_results.get_hist_filter(
                self._get_read_groups(items[0]), self.metadata
            )
            logger.trace(
                "Length hist filter: {}", len(hist_filter) if hist_filter is not None else "None"
            )
            write_group = self._get_write_group(items[0])
            if hist_filter is not None and len(hist_filter) == 0:
                return np.array([], dtype=np.uint32), write_group
            result_hists = self.fainder_index.search(
                percentile,
                comparison,
                reference,
                self.fainder_mode,
                self.fainder_index_name,
                hist_filter,
            )
            parent_write_group = self._get_parent_write_group(write_group)
            self.intermediate_results.add_col_ids(
                write_group, result_hists, self.metadata.doc_to_cols
            )
            return result_hists, parent_write_group

        logger.trace("Evaluating percentile term: {}", items)

        # Submit task to thread pool and store the future with a unique ID
        return self._thread_pool.submit(_percentile_task, items)

    def col_op(
        self, items: list[tuple[ColResult, int] | Future[tuple[ColResult, int]]]
    ) -> tuple[DocResult, int]:
        logger.trace("Evaluating column term")

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        if isinstance(items[0], Future):
            col_ids, write_group = items[0].result()
        else:
            col_ids = items[0][0]
            write_group = items[0][1]

        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        self.intermediate_results.add_doc_ids(write_group, doc_ids, self.metadata.col_to_doc)
        parent_write_group = self._get_parent_write_group(write_group)
        if self.enable_highlighting:
            return (doc_ids, ({}, col_ids)), parent_write_group

        return ((doc_ids, ({}, np.array([], dtype=np.uint32))), parent_write_group)

    def conjunction(
        self, items: Sequence[tuple[TResult, int] | Future[tuple[TResult, int]]]
    ) -> tuple[TResult, int]:
        logger.trace("Evaluating conjunction with number of items: {}", len(items))

        clean_items, write_group = self._resolve_items(items)
        result = junction(clean_items, "and", self.enable_highlighting, self.metadata.doc_to_cols)

        if isinstance(result, tuple):
            self.intermediate_results.add_doc_ids(write_group, result[0], self.metadata.col_to_doc)
        else:
            self.intermediate_results.add_col_ids(write_group, result, self.metadata.doc_to_cols)

        parent_write_group = self._get_parent_write_group(write_group)

        return result, parent_write_group

    def disjunction(
        self, items: Sequence[tuple[TResult, int] | Future[tuple[TResult, int]]]
    ) -> tuple[TResult, int]:
        logger.trace("Evaluating disjunction with number of items: {}", len(items))

        clean_items, write_group = self._resolve_items(items)
        result = junction(clean_items, "or", self.enable_highlighting, self.metadata.doc_to_cols)

        if isinstance(result, tuple):
            self.intermediate_results.add_doc_ids(write_group, result[0], self.metadata.col_to_doc)
        else:
            self.intermediate_results.add_col_ids(write_group, result, self.metadata.doc_to_cols)

        parent_write_group = self._get_parent_write_group(write_group)
        return result, parent_write_group

    def negation(
        self, items: Sequence[tuple[TResult, int] | Future[tuple[TResult, int]]]
    ) -> tuple[TResult, int]:
        logger.trace("Evaluating negation with {} items", len(items))

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")
        # Resolve the item if it's a future
        item, write_group = self._resolve_item(items[0])

        if isinstance(item, tuple):
            to_negate, _ = item

            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = np.array([], dtype=np.uint32)
            doc_result = negate_array(to_negate, len(self.metadata.doc_to_cols))
            result = (doc_result, (doc_highlights, col_highlights))
            self.intermediate_results.add_doc_ids(
                write_group, doc_result, self.metadata.col_to_doc
            )
            return result, self._get_parent_write_group(write_group)

        to_negate_cols: ColResult = item

        negated_cols = negate_array(to_negate_cols, len(self.metadata.col_to_doc))
        self.intermediate_results.add_col_ids(write_group, negated_cols, self.metadata.doc_to_cols)

        return negated_cols, self._get_parent_write_group(write_group)

    def query(
        self, items: list[tuple[DocResult, int] | Future[tuple[DocResult, int]]]
    ) -> DocResult:
        logger.trace(f"Evaluating query with {len(items)} items")

        clean_item = items[0].result() if isinstance(items[0], Future) else items[0]

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return clean_item[0]
