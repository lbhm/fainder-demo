import os
from functools import lru_cache

from backend.config import CacheInfo, ExecutorType, FainderMode, Highlights, Metadata
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .execution.factory import create_executor
from .optimizer import create_optimizer
from .parser import Parser


class Engine:
    def __init__(
        self,
        tantivy_index: TantivyIndex,
        fainder_index: FainderIndex,
        hnsw_index: HnswIndex,
        metadata: Metadata,
        cache_size: int = 128,
        min_usability_score: float = 0.0,
        rank_by_usability: bool = True,
        executor_type: ExecutorType = ExecutorType.SIMPLE,
        max_workers: int = os.cpu_count() or 1,
    ) -> None:
        self.parser = Parser()
        self.optimizer = create_optimizer(executor_type)
        self.executor = create_executor(
            executor_type=executor_type,
            tantivy_index=tantivy_index,
            fainder_index=fainder_index,
            hnsw_index=hnsw_index,
            metadata=metadata,
            min_usability_score=min_usability_score,
            rank_by_usability=rank_by_usability,
            max_workers=max_workers,
        )
        self.max_workers = max_workers
        self.min_usability_score = min_usability_score
        self.rank_by_usability = rank_by_usability
        self.executor_type = executor_type

        # NOTE: Don't use lru_cache on methods
        # See https://docs.astral.sh/ruff/rules/cached-instance-method/ for details
        self.execute = lru_cache(maxsize=cache_size)(self._execute)

    def update_indices(
        self,
        tantivy_index: TantivyIndex,
        fainder_index: FainderIndex,
        hnsw_index: HnswIndex,
        metadata: Metadata,
    ) -> None:
        self.executor = create_executor(
            executor_type=self.executor_type,
            tantivy_index=tantivy_index,
            fainder_index=fainder_index,
            hnsw_index=hnsw_index,
            metadata=metadata,
            min_usability_score=self.min_usability_score,
            rank_by_usability=self.rank_by_usability,
            max_workers=self.max_workers,
        )
        self.clear_cache()

    def clear_cache(self) -> None:
        self.execute.cache_clear()

    def cache_info(self) -> CacheInfo:
        hits, misses, max_size, curr_size = self.execute.cache_info()
        return CacheInfo(hits=hits, misses=misses, max_size=max_size, curr_size=curr_size)

    def _execute(
        self,
        query: str,
        fainder_mode: FainderMode = FainderMode.LOW_MEMORY,
        enable_highlighting: bool = False,
    ) -> tuple[list[int], Highlights]:
        # Reset state for new query
        self.executor.reset(fainder_mode, enable_highlighting)

        # Parse query
        parse_tree = self.parser.parse(query)

        # Optimze query
        parse_tree = self.optimizer.optimize(parse_tree)

        # Execute query
        result, highlights = self.executor.execute(parse_tree)

        # Sort by score
        result_list = list(result)
        result_list.sort(key=lambda x: self.executor.scores.get(x, -1), reverse=True)
        return result_list, highlights
