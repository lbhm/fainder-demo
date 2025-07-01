import os
from collections import defaultdict
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np
from lark import ParseTree, Token, Transformer
from loguru import logger

from backend.config import ColumnHighlights, DocumentHighlights, FainderMode, Metadata
from backend.engine.conversion import col_to_doc_ids
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .common import ColResult, DocResult, TResult, junction, negate_array
from .executor import Executor


class ThreadedExecutor(Transformer[Token, DocResult], Executor):
    """This transformer evaluates a query bottom-up and computes results in parallel threads."""

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
        # TODO: Migrate this to using the weakref module and a finalizer
        if self._thread_pool:
            self._thread_pool.shutdown(wait=True)

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
        fainder_index_name: str = "default",
    ) -> None:
        self.scores = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting
        self.fainder_index_name = fainder_index_name

    def execute(self, tree: ParseTree) -> DocResult:
        """Start processing the parse tree."""
        # Create a new thread pool for this execution

        result = self.transform(tree)

        logger.debug("Result of query execution: ", result)

        return result

    def _resolve_item(self, item: TResult | Future[TResult]) -> TResult:
        """Resolve item if it's a Future, otherwise return the item itself."""
        return item.result(timeout=300) if isinstance(item, Future) else item

    def _resolve_items(self, items: Sequence[TResult | Future[TResult]]) -> list[TResult]:
        """Resolve all items in the list if they are futures."""
        return [self._resolve_item(item) for item in items]

    ##########################
    # Operator implementations
    ##########################

    def keyword_op(self, items: list[Token]) -> Future[DocResult]:
        def _keyword_task(token: Token) -> DocResult:
            """Task function for keyword search to be run in a thread."""
            logger.trace("Thread executing keyword search for: {}", token)
            result_docs, scores, highlights = self.tantivy_index.search(
                token, self.enable_highlighting, self.min_usability_score, self.rank_by_usability
            )
            self.updates_scores(result_docs, scores)
            return result_docs, (highlights, np.array([], dtype=np.uint32))

        logger.trace("Evaluating keyword term: {}", items)
        return self._thread_pool.submit(_keyword_task, items[0])

    def name_op(self, items: list[Token]) -> Future[ColResult]:
        def _name_task(column: Token, k: int) -> ColResult:
            """Task function for column name search to be run in a thread."""
            logger.trace("Thread executing column name search for: {}", column)
            return self.hnsw_index.search(column, k, None)

        logger.trace("Evaluating column name term: {}", items)

        column = items[0]
        k = int(items[1])

        # Submit task to thread pool
        return self._thread_pool.submit(_name_task, column, k)

    def percentile_op(self, items: list[Token]) -> Future[ColResult]:
        def _percentile_task(percentile: float, comparison: str, reference: float) -> ColResult:
            """Task function for percentile search to be run in a thread."""
            logger.trace(
                "Thread executing percentile search with {} {} {}",
                percentile,
                comparison,
                reference,
            )
            return self.fainder_index.search(
                percentile, comparison, reference, self.fainder_mode, self.fainder_index_name
            )

        logger.trace("Evaluating percentile term: {}", items)

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])

        # Submit task to thread pool and store the future with a unique ID
        return self._thread_pool.submit(_percentile_task, percentile, comparison, reference)

    def col_op(self, items: Sequence[ColResult | Future[ColResult]]) -> Future[DocResult]:
        def _col_op_task(items: Sequence[ColResult | Future[ColResult]]) -> DocResult:
            logger.trace("Evaluating column term with items of length: {}", len(items))

            if len(items) != 1:
                raise ValueError("Column term must have exactly one item")

            # Get actual result if it's a future
            col_ids = self._resolve_item(items[0])

            doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
            if self.enable_highlighting:
                return doc_ids, ({}, col_ids)

            return doc_ids, ({}, np.array([], dtype=np.uint32))

        logger.trace("Evaluating column operation with items of length: {}", len(items))

        return self._thread_pool.submit(_col_op_task, items)

    def conjunction(self, items: Sequence[TResult | Future[TResult]]) -> Future[TResult]:
        def _conjunction_task(items: Sequence[TResult | Future[TResult]]) -> TResult:
            """Task function for conjunction to be run in a thread."""
            logger.trace("Thread executing conjunction with items of length: {}", len(items))

            # Resolve all futures in items
            resolved_items = self._resolve_items(items)

            return junction(
                resolved_items, "and", self.enable_highlighting, self.metadata.doc_to_cols
            )

        logger.trace("Evaluating conjunction with items of length: {}", len(items))

        return self._thread_pool.submit(_conjunction_task, items)

    def disjunction(self, items: Sequence[TResult | Future[TResult]]) -> Future[TResult]:
        def _disjunction_task(items: Sequence[TResult | Future[TResult]]) -> TResult:
            """Task function for disjunction to be run in a thread."""
            logger.trace("Thread executing disjunction with items of length: {}", len(items))

            # Resolve all futures in items
            resolved_items = self._resolve_items(items)

            return junction(
                resolved_items, "or", self.enable_highlighting, self.metadata.doc_to_cols
            )

        logger.trace("Evaluating disjunction with items of length: {}", len(items))

        return self._thread_pool.submit(_disjunction_task, items)

    def negation(self, items: Sequence[TResult | Future[TResult]]) -> Future[TResult]:
        def _negation_task(items: Sequence[TResult | Future[TResult]]) -> TResult:
            """Task function for negation to be run in a thread."""
            logger.trace("Thread executing negation with items of length: {}", len(items))

            if len(items) != 1:
                raise ValueError("Negation term must have exactly one item")

            # Resolve the item if it's a future
            item = self._resolve_item(items[0])

            if isinstance(item, tuple):
                to_negate, _ = item
                doc_result = negate_array(to_negate, len(self.metadata.doc_to_cols))
                # Result highlights are reset for negated results
                doc_highlights: DocumentHighlights = {}
                col_highlights: ColumnHighlights = np.array([], dtype=np.uint32)
                return doc_result, (doc_highlights, col_highlights)  # type: ignore[return-value]

            to_negate_cols = item
            return negate_array(to_negate_cols, len(self.metadata.col_to_doc))

        logger.trace("Evaluating negation with items of length: {}", len(items))
        return self._thread_pool.submit(_negation_task, items)

    def query(self, items: Sequence[DocResult | Future[DocResult]]) -> DocResult:
        logger.trace("Evaluating query with {} items", len(items))

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")

        # Resolve the item if it's a future
        return self._resolve_item(items[0])
