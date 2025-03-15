from functools import lru_cache

from backend.config import CacheInfo, FainderMode, Metadata
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .executor import Executor, Highlights
from .optimizer import Optimizer
from .parser import Parser


class Engine:
    def __init__(
        self,
        tantivy_index: TantivyIndex,
        fainder_index: FainderIndex,
        hnsw_index: HnswIndex,
        metadata: Metadata,
        cache_size: int = 128,
    ) -> None:
        self.parser = Parser()
        self.optimizer = Optimizer()
        self.executor = Executor(tantivy_index, fainder_index, hnsw_index, metadata)

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
        self.executor = Executor(tantivy_index, fainder_index, hnsw_index, metadata)
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
        enable_filtering: bool = False,
        min_usability_score: float = 0.0,
        use_usability_score: bool = True,
    ) -> tuple[list[int], Highlights]:
        # Reset state for new query
        self.executor.reset(
            fainder_mode,
            enable_highlighting,
            enable_filtering,
            min_usability_score,
            use_usability_score,
        )

        # Parse query
        parse_tree = self.parser.parse(query)

        # Optimze query
        parse_tree = self.optimizer.optimize(parse_tree)

        # Execute query
        result, highlights = self.executor.transform(parse_tree)

        # Sort by score
        result_list = list(result)
        result_list.sort(key=lambda x: self.executor.scores.get(x, -1), reverse=True)
        return result_list, highlights
