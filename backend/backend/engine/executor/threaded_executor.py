import os
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from operator import and_, or_
from typing import Any

from lark import ParseTree, Token, Transformer
from loguru import logger
from numpy import uint32

from backend.config import (
    ColumnHighlights,
    DocumentHighlights,
    FainderMode,
    Highlights,
    Metadata,
)
from backend.engine.conversion import (
    col_to_doc_ids,
    hist_to_col_ids,
)
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .helper import (
    Executor,
    junction,
)


class ThreadedExecutor(Transformer[Token, tuple[set[int], Highlights]], Executor):
    """This transformer evaluates a parse tree bottom-up
    and computes the query result in parallel using Threading."""

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
        self.min_usability_score = min_usability_score
        self.rank_by_usability = rank_by_usability
        self.max_workers = max_workers

        self.reset(fainder_mode, enable_highlighting)
        self._thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)

    def __del__(self) -> None:
        # Shutdown the thread pool if it is still running
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
    ) -> None:
        self.scores = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting

    def execute(self, tree: ParseTree) -> tuple[set[int], Highlights]:
        """Start processing the parse tree."""
        # Create a new thread pool for this execution
        
        self._thread_results: dict[int, Any] = {}

        result = self.transform(tree)

        return result

    def updates_scores(self, doc_ids: Sequence[int], scores: Sequence[float]) -> None:
        logger.trace(f"Updating scores for {len(doc_ids)} documents")

        for doc_id, score in zip(doc_ids, scores, strict=True):
            self.scores[doc_id] += score

    ### Threaded task methods ###

    def _keyword_task(self, token: Token) -> tuple[set[int], Highlights]:
        """Task function for keyword search to be run in a thread"""
        logger.trace(f"Thread executing keyword search for: {token}")
        result_docs, scores, highlights = self.tantivy_index.search(
            token, self.enable_highlighting, self.min_usability_score, self.rank_by_usability
        )
        self.updates_scores(result_docs, scores)
        return set(result_docs), (highlights, set())

    def _name_task(self, column: Token, k: int) -> set[uint32]:
        """Task function for column name search to be run in a thread"""
        logger.trace(f"Thread executing column name search for: {column}")
        return self.hnsw_index.search(column, k, None)

    def _percentile_task(
        self, percentile: float, comparison: str, reference: float
    ) -> set[uint32]:
        """Task function for percentile search to be run in a thread"""
        logger.trace(
            f"Thread executing percentile search with {percentile} {comparison} {reference}"
        )
        result_hists = self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode
        )
        return hist_to_col_ids(result_hists, self.metadata.hist_to_col)

    ### Operator implementations ###

    def keyword_op(self, items: list[Token]) -> Future[tuple[set[int], Highlights]]:
        logger.trace(f"Starting threaded keyword search for: {items}")

        # Submit task to thread pool and store the future with a unique ID
        task_id = id(items[0])
        future = self._thread_pool.submit(self._keyword_task, items[0])
        self._thread_results[task_id] = future

        # Get result from future (immediate, non-blocking as result might not be ready yet)
        return future

    def name_op(self, items: list[Token]) -> Future[set[uint32]]:
        logger.trace(f"Starting threaded column name search for: {items}")

        column = items[0]
        k = int(items[1])

        # Submit task to thread pool and store the future with a unique ID
        task_id = id(items[0])
        future = self._thread_pool.submit(self._name_task, column, k)
        self._thread_results[task_id] = future

        # Return future (non-blocking)
        return future

    def percentile_op(self, items: list[Token]) -> Future[set[uint32]]:
        logger.trace(f"Starting threaded percentile search for: {items}")

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])

        # Submit task to thread pool and store the future with a unique ID
        task_id = id(items[0])
        future = self._thread_pool.submit(self._percentile_task, percentile, comparison, reference)
        self._thread_results[task_id] = future

        # Return future (non-blocking)
        return future

    def _resolve_item(
        self,
        item: Future[tuple[set[int], Highlights]]
        | tuple[set[int], Highlights]
        | Future[set[uint32]]
        | set[uint32],
    ) -> tuple[set[int], Highlights] | set[uint32]:
        """Resolve item if it's a Future, otherwise return the item itself"""
        return item.result() if isinstance(item, Future) else item

    def _resolve_col_result(self, item: Future[set[uint32]] | set[uint32]) -> set[uint32]:
        """Resolve column result from a Future if needed"""
        return item.result() if isinstance(item, Future) else item

    def _resolve_doc_result(
        self, item: Future[tuple[set[int], Highlights]] | tuple[set[int], Highlights]
    ) -> tuple[set[int], Highlights]:
        """Resolve document result from a Future if needed"""
        return item.result() if isinstance(item, Future) else item

    def _resolve_items(
        self,
        items: list[tuple[set[int], Highlights] | Future[tuple[set[int], Highlights]]]
        | list[set[uint32] | Future[set[uint32]]],
    ) -> list[tuple[set[int], Highlights]] | list[set[uint32]]:
        """Resolve all items in the list if they are futures"""
        doc_results: list[tuple[set[int], Highlights]] = []
        col_results: list[set[uint32]] = []

        for item in items:
            resolved = self._resolve_item(item)
            if isinstance(resolved, tuple):
                doc_results.append(resolved)
            else:
                col_results.append(resolved)

        # We should only have one type of result
        if doc_results and col_results:
            raise ValueError("Cannot mix document and column results")
        if doc_results:
            return doc_results
        return col_results

    def col_op(
        self, items: list[set[uint32] | Future[set[uint32]]]
    ) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating column term: {items}")

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")

        # Get actual result if it's a future
        col_ids = self._resolve_col_result(items[0])

        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        if self.enable_highlighting:
            return doc_ids, ({}, col_ids)

        return doc_ids, ({}, set())

    def conjunction(
        self,
        items: list[tuple[set[int], Highlights] | Future[tuple[set[int], Highlights]]]
        | list[set[uint32] | Future[set[uint32]]],
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating conjunction with items: {items}")

        # Resolve all futures in items
        resolved_items: list[tuple[set[int], Highlights]] | list[set[uint32]] = (
            self._resolve_items(items)
        )

        return junction(resolved_items, and_, self.enable_highlighting, self.metadata.doc_to_cols)

    def disjunction(
        self,
        items: list[tuple[set[int], Highlights] | Future[tuple[set[int], Highlights]]]
        | list[set[uint32] | Future[set[uint32]]],
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating disjunction with items: {items}")

        # Resolve all futures in items
        resolved_items = self._resolve_items(items)

        return junction(resolved_items, or_, self.enable_highlighting, self.metadata.doc_to_cols)

    def negation(
        self,
        items: list[tuple[set[int], Highlights] | Future[tuple[set[int], Highlights]]]
        | list[set[uint32] | Future[set[uint32]]],
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating negation with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")

        # Resolve the item if it's a future
        item = self._resolve_item(items[0])

        if isinstance(item, tuple):
            to_negate, _ = item
            all_docs = set(self.metadata.doc_to_cols.keys())
            # Result highlights are reset for negated results
            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = set()
            return all_docs - to_negate, (doc_highlights, col_highlights)

        to_negate_cols = item
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in range(len(self.metadata.col_to_doc))}
        return all_columns - to_negate_cols

    def query(
        self, items: list[tuple[set[int], Highlights] | Future[tuple[set[int], Highlights]]]
    ) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating query with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")

        # Resolve the item if it's a future
        item = self._resolve_doc_result(items[0])

        return item
