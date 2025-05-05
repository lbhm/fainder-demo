import os
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from operator import and_, or_

from lark import ParseTree, Token, Transformer
from loguru import logger
from numpy import uint32
from numpy.typing import NDArray

from backend.config import (
    COLUMN_RESULTS,
    DOC_RESULTS,
    ColumnHighlights,
    DocumentHighlights,
    FainderMode,
    Metadata,
)
from backend.engine.conversion import (
    col_to_doc_ids,
    col_to_hist_ids,
    doc_to_col_ids,
    hist_to_col_ids,
)
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .common import ResultGroupAnnotator, TResultSet, exceeds_filtering_limit, junction
from .executor import Executor


class IntermediateResultFuture:
    """Stores futures and results for intermediate results during parallel execution."""

    def __init__(
        self,
        write_group: int,
        doc_ids: set[int] | None = None,
        col_ids: COLUMN_RESULTS | None = None,
    ) -> None:
        # resolved results trump futures
        self.write_group = write_group
        self.kw_result_futures: list[Future[tuple[DOC_RESULTS, int]]] = []
        self.column_result_futures: list[Future[tuple[COLUMN_RESULTS, int]]] = []
        self.pp_result_futures: list[Future[tuple[COLUMN_RESULTS, int]]] = []

        # Store resolved results only one of these should be set
        self._col_ids: COLUMN_RESULTS | None = col_ids
        self._doc_ids: set[int] | None = doc_ids

    def add_doc_future(self, future: Future[tuple[DOC_RESULTS, int]]) -> None:
        """Add a future that will resolve to document IDs"""
        self.kw_result_futures.append(future)

    def add_col_future(self, future: Future[tuple[COLUMN_RESULTS, int]]) -> None:
        """Add a future that will resolve to column IDs"""
        self.column_result_futures.append(future)

    def add_hist_future(self, future: Future[tuple[COLUMN_RESULTS, int]]) -> None:
        """Add a future that will resolve to histogram IDs"""
        self.pp_result_futures.append(future)

    def add_col_ids(self, col_ids: COLUMN_RESULTS, doc_to_cols: dict[int, set[int]]) -> None:
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

    def _build_hist_filter_resolved(
        self, metadata: Metadata, fainder_mode: FainderMode
    ) -> COLUMN_RESULTS | None:
        if self._doc_ids is not None:
            if exceeds_filtering_limit(self._doc_ids, "num_doc_ids", fainder_mode):
                return None
            col_ids = doc_to_col_ids(self._doc_ids, metadata.doc_to_cols)
            return col_to_hist_ids(col_ids, metadata.col_to_hist)
        if self._col_ids is not None:
            if exceeds_filtering_limit(self._col_ids, "num_col_ids", fainder_mode):
                return None
            return col_to_hist_ids(self._col_ids, metadata.col_to_hist)
        return None

    def _build_hist_filter_future(
        self, metadata: Metadata, fainder_mode: FainderMode
    ) -> COLUMN_RESULTS | None:
        hist_ids: COLUMN_RESULTS = set()
        first = True
        for kw_future in self.kw_result_futures:
            doc_ids, _ = kw_future.result()
            if exceeds_filtering_limit(doc_ids[0], "num_doc_ids", fainder_mode):
                return None
            col_ids = doc_to_col_ids(doc_ids[0], metadata.doc_to_cols)
            new_hist_ids = col_to_hist_ids(col_ids, metadata.col_to_hist)
            if first:
                hist_ids = new_hist_ids
                first = False
            else:
                hist_ids.intersection_update(new_hist_ids)

        for col_future in self.column_result_futures:
            col_ids, _ = col_future.result()
            if exceeds_filtering_limit(col_ids, "num_col_ids", fainder_mode):
                return None
            new_hist_ids = col_to_hist_ids(col_ids, metadata.col_to_hist)
            if first:
                hist_ids = new_hist_ids
                first = False
            else:
                hist_ids.intersection_update(new_hist_ids)

        # not resolve the pp_result_futures

        if first:
            return None
        return hist_ids

    def build_hist_filter(
        self, metadata: Metadata, fainder_mode: FainderMode
    ) -> COLUMN_RESULTS | None:
        """Build a histogram filter from the intermediate results."""
        hist_ids_resolved = self._build_hist_filter_resolved(metadata, fainder_mode)
        if hist_ids_resolved is not None:
            return hist_ids_resolved

        return self._build_hist_filter_future(metadata, fainder_mode)

    def is_empty(self) -> bool:
        """Check if the intermediate result is empty."""
        return (
            self._doc_ids is None
            and self._col_ids is None
            and len(self.kw_result_futures) == 0
            and len(self.column_result_futures) == 0
        )  # not checking pp_result_futures becuase they are irrelevant for the histogram filter

    def __str__(self) -> str:
        """String representation of the intermediate result future."""
        return (
            f"IntermediateResultFuture(\n\twrite_group={self.write_group},"
            f"\n\tdoc_ids={self._doc_ids},\n\tcol_ids={self._col_ids},\n\t,"
            f"\n\tkw_futures={len(self.kw_result_futures)},\n\t"
            f"col_futures={len(self.column_result_futures)},\n\tpp_futures={len(self.pp_result_futures)}\n)"
        )


class IntermediateResultStoreFuture:
    """Stores futures and results for intermediate results during parallel execution."""

    def __init__(self, fainder_mode: FainderMode) -> None:
        self.results: dict[int, IntermediateResultFuture] = {}
        self.fainder_mode = fainder_mode

    def add_future_kw_result(
        self, write_group: int, future: Future[tuple[DOC_RESULTS, int]]
    ) -> None:
        """Add a future that will resolve to document IDs"""
        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(write_group)
        self.results[write_group].add_doc_future(future)

    def add_future_col_result(
        self, write_group: int, future: Future[tuple[COLUMN_RESULTS, int]]
    ) -> None:
        """Add a future that will resolve to column IDs"""
        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(write_group)
        self.results[write_group].add_col_future(future)

    def add_future_hist_result(
        self, write_group: int, future: Future[tuple[COLUMN_RESULTS, int]]
    ) -> None:
        """Add a future that will resolve to histogram IDs"""
        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(write_group)
        self.results[write_group].add_hist_future(future)

    def add_col_ids(
        self, write_group: int, col_ids: COLUMN_RESULTS, doc_to_cols: dict[int, set[int]]
    ) -> None:
        """Add column IDs to the intermediate result."""
        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(write_group, col_ids=col_ids)
        self.results[write_group].add_col_ids(col_ids, doc_to_cols)
        logger.trace(f"Adding column IDs to write group {write_group}: {col_ids}")

    def add_doc_ids(
        self, write_group: int, doc_ids: set[int], col_to_doc: NDArray[uint32]
    ) -> None:
        """Add document IDs to the intermediate result."""
        if write_group not in self.results:
            self.results[write_group] = IntermediateResultFuture(write_group, doc_ids=doc_ids)
        self.results[write_group].add_doc_ids(doc_ids, col_to_doc)
        logger.trace(f"Adding document IDs to write group {write_group}: {doc_ids}")

    def get_hist_filter(
        self, read_groups: list[int], metadata: Metadata, fainder_mode: FainderMode
    ) -> COLUMN_RESULTS | None:
        """Build a histogram filter from the intermediate results."""
        hist_filter: COLUMN_RESULTS | None = None
        if len(read_groups) == 0:
            return hist_filter

        logger.trace(f"read groups {read_groups}")
        for read_group in read_groups:
            if read_group not in self.results or self.results[read_group].is_empty():
                logger.trace(
                    f"Read group {read_group} does not have an intermediate result, skipping"
                )
                continue

            logger.trace(
                f"Processing read group {read_group} with results {self.results[read_group]}"
            )
            intermediate = self.results[read_group].build_hist_filter(metadata, fainder_mode)

            if intermediate is None:
                return None

            logger.trace(f"intermediate {intermediate}")
            if hist_filter is None:
                hist_filter = intermediate
            else:
                hist_filter &= intermediate

        logger.trace(f"Hist filter: {hist_filter}")
        return hist_filter


class ParallelPrefilteringExecutor(Transformer[Token, DOC_RESULTS], Executor):
    """This transformer evaluates a parse tree bottom-up
    and computes the query result in parallel using Threading.
    It also uses prefiltering to reduce the number of documents
    before executing the query for percentile predicates."""

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
        self.intermediate_results = IntermediateResultStoreFuture(fainder_mode=fainder_mode)
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
    ) -> None:
        self.scores = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting
        self.intermediate_results = IntermediateResultStoreFuture(fainder_mode=fainder_mode)

    def execute(self, tree: ParseTree) -> DOC_RESULTS:
        """Start processing the parse tree."""
        self.write_groups = {}
        self.read_groups = {}
        logger.trace(tree.pretty())
        groups = ResultGroupAnnotator()
        groups.apply(tree, parallel=True)

        self.write_groups = groups.write_groups
        self.read_groups = groups.read_groups
        self.parent_write_group = groups.parent_write_group
        logger.trace(f"Write groups: {self.write_groups}")
        logger.trace(f"Read groups: {self.read_groups}")
        logger.trace(f"Parent write groups: {self.parent_write_group}")
        # create intermediate results for all write groups
        for write_group in self.write_groups.values():
            self.intermediate_results.results[write_group] = IntermediateResultFuture(write_group)

        result = self.transform(tree)

        logger.trace(f"Final result: {result}")

        return result

    def _get_write_group(self, node: ParseTree | Token) -> int:
        """Get the write group for a node."""
        node_id = id(node)
        if node_id in self.write_groups:
            return self.write_groups[node_id]
        logger.warning(f"Node {node} does not have a write group with id {node_id}")
        logger.warning(f"Write groups: {self.write_groups}")
        raise ValueError("Node does not have a write group")

    def _get_read_groups(self, node: ParseTree | Token) -> list[int]:
        """Get the read groups for a node."""
        node_id = id(node)
        if node_id in self.read_groups:
            return self.read_groups[node_id]
        logger.warning(f"Node {node} does not have read groups")
        logger.warning(f"Read groups: {self.read_groups}")
        raise ValueError("Node does not have read groups")

    def _get_parent_write_group(self, write_group: int) -> int:
        """Get the parent write group for a write group."""
        if write_group in self.parent_write_group:
            return self.parent_write_group[write_group]
        logger.warning(f"Write group {write_group} does not have a parent write group")
        logger.warning(f"Parent write groups: {self.parent_write_group}")
        raise ValueError("Write group does not have a parent write group")

    def _resolve_items(
        self, items: Sequence[tuple[TResultSet, int] | Future[tuple[TResultSet, int]]]
    ) -> tuple[Sequence[TResultSet], int]:
        """Resolve items from futures."""
        clean_item: list[TResultSet] = []
        write_group: int = 0
        for item in items:
            resolved_item = item.result() if isinstance(item, Future) else item
            clean_item.append(resolved_item[0])
            write_group = resolved_item[1]
        return clean_item, write_group

    def _resolve_item(
        self, item: tuple[TResultSet, int] | Future[tuple[TResultSet, int]]
    ) -> tuple[TResultSet, int]:
        """Resolve item from future."""
        if isinstance(item, Future):
            return item.result()
        return item

    ### Operator implementations ###

    def keyword_op(self, items: list[Token]) -> Future[tuple[DOC_RESULTS, int]]:
        def _keyword_task(token: Token) -> tuple[DOC_RESULTS, int]:
            """Task function for keyword search to be run in a thread"""
            logger.trace(f"Thread executing keyword search for: {token}")
            write_group = self._get_write_group(token)
            result_docs, scores, highlights = self.tantivy_index.search(
                token, self.enable_highlighting, self.min_usability_score, self.rank_by_usability
            )
            self.updates_scores(result_docs, scores)
            parent_write_group = self._get_parent_write_group(write_group)
            return (set(result_docs), (highlights, set())), parent_write_group

        logger.trace(f"Evaluating keyword term: {items}")

        # Submit task to thread pool and store the future with a unique ID
        future = self._thread_pool.submit(_keyword_task, items[0])

        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_future_kw_result(write_group, future)
        return future

    def name_op(self, items: list[Token]) -> Future[tuple[COLUMN_RESULTS, int]]:
        def _name_task(column: Token, k: int) -> tuple[COLUMN_RESULTS, int]:
            """Task function for column name search to be run in a thread"""
            logger.trace(f"Thread executing column name search for: {column}")
            write_group = self._get_write_group(column)
            parent_write_group = self._get_parent_write_group(write_group)
            return self.hnsw_index.search(column, k, None), parent_write_group

        logger.trace(f"Evaluating column term: {items}")

        column = items[0]
        k = int(items[1])

        # Submit task to thread pool and store the future with a unique ID
        future = self._thread_pool.submit(_name_task, column, k)
        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_future_col_result(write_group, future)
        return future

    def percentile_op(self, items: list[Token]) -> Future[tuple[COLUMN_RESULTS, int]]:
        def _percentile_task(items: list[Token]) -> tuple[COLUMN_RESULTS, int]:
            """Task function for percentile search to be run in a thread"""
            percentile = float(items[0])
            comparison: str = items[1]
            reference = float(items[2])
            logger.trace(
                f"Thread executing percentile search with {percentile} {comparison} {reference}"
            )
            hist_filter = self.intermediate_results.get_hist_filter(
                self._get_read_groups(items[0]), self.metadata, self.fainder_mode
            )
            logger.trace(f"Hist filter: {hist_filter}")
            write_group = self._get_write_group(items[0])
            if hist_filter is not None and len(hist_filter) == 0:
                return set(), write_group
            result_hists = self.fainder_index.search(
                percentile, comparison, reference, self.fainder_mode, hist_filter
            )
            result = hist_to_col_ids(result_hists, self.metadata.hist_to_col)
            parent_write_group = self._get_parent_write_group(write_group)
            return result, parent_write_group

        logger.trace(f"Evaluating percentile term: {items}")

        # Submit task to thread pool and store the future with a unique ID
        future = self._thread_pool.submit(_percentile_task, items)
        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_future_hist_result(write_group, future)
        return future

    def col_op(
        self, items: list[tuple[COLUMN_RESULTS, int] | Future[tuple[COLUMN_RESULTS, int]]]
    ) -> tuple[DOC_RESULTS, int]:
        logger.trace(f"Evaluating column term: {items}")

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

        return (doc_ids, ({}, set())), parent_write_group

    def conjunction(
        self, items: Sequence[tuple[TResultSet, int] | Future[tuple[TResultSet, int]]]
    ) -> tuple[TResultSet, int]:
        logger.trace(f"Evaluating conjunction with items: {items}")

        clean_items, write_group = self._resolve_items(items)

        result = junction(clean_items, and_, self.enable_highlighting, self.metadata.doc_to_cols)

        if isinstance(result, tuple):
            self.intermediate_results.add_doc_ids(write_group, result[0], self.metadata.col_to_doc)
        else:
            self.intermediate_results.add_col_ids(write_group, result, self.metadata.doc_to_cols)

        parent_write_group = self._get_parent_write_group(write_group)

        return result, parent_write_group

    def disjunction(
        self, items: Sequence[tuple[TResultSet, int] | Future[tuple[TResultSet, int]]]
    ) -> tuple[TResultSet, int]:
        logger.trace(f"Evaluating disjunction with items: {items}")

        clean_items, write_group = self._resolve_items(items)

        result = junction(clean_items, or_, self.enable_highlighting, self.metadata.doc_to_cols)

        if isinstance(result, tuple):
            self.intermediate_results.add_doc_ids(write_group, result[0], self.metadata.col_to_doc)
        else:
            self.intermediate_results.add_col_ids(write_group, result, self.metadata.doc_to_cols)

        parent_write_group = self._get_parent_write_group(write_group)
        return result, parent_write_group

    def negation(
        self, items: Sequence[tuple[TResultSet, int] | Future[tuple[TResultSet, int]]]
    ) -> tuple[TResultSet, int]:
        logger.trace(f"Evaluating negation with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")
        # Resolve the item if it's a future
        item, write_group = self._resolve_item(items[0])

        if isinstance(item, tuple):
            to_negate, _ = item
            all_docs = set(self.metadata.doc_to_cols.keys())
            # Result highlights are reset for negated results
            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = set()
            parent_write_group = self._get_parent_write_group(write_group)
            doc_result = all_docs.difference(to_negate)
            result = (doc_result, (doc_highlights, col_highlights))
            self.intermediate_results.add_doc_ids(
                write_group, doc_result, self.metadata.col_to_doc
            )
            return result, parent_write_group

        to_negate_cols: COLUMN_RESULTS = item
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in range(len(self.metadata.col_to_doc))}
        result_col = all_columns - to_negate_cols
        self.intermediate_results.add_col_ids(write_group, result_col, self.metadata.doc_to_cols)
        parent_write_group_cols = self._get_parent_write_group(write_group)
        return result_col, parent_write_group_cols

    def query(
        self,
        items: list[tuple[DOC_RESULTS, int] | Future[tuple[DOC_RESULTS, int]]],
    ) -> DOC_RESULTS:
        logger.trace(f"Evaluating query with {len(items)} items")

        clean_item = items[0].result() if isinstance(items[0], Future) else items[0]

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return clean_item[0]
