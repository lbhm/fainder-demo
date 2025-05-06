import os

from backend.config import ExecutorType, FainderMode, Metadata
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .executor import Executor
from .prefiltering_executor import PrefilteringExecutor
from .simple_executor import SimpleExecutor
from .threaded_executor import ThreadedExecutor
from .threaded_prefiltering_executor import ThreadedPrefilteringExecutor


def create_executor(
    executor_type: ExecutorType,
    tantivy_index: TantivyIndex,
    fainder_index: FainderIndex,
    hnsw_index: HnswIndex,
    metadata: Metadata,
    fainder_mode: FainderMode = FainderMode.LOW_MEMORY,
    enable_highlighting: bool = False,
    min_usability_score: float = 0.0,
    rank_by_usability: bool = True,
    max_workers: int = os.cpu_count() or 1,
) -> Executor:
    """Factory function to create the appropriate executor based on the executor type."""
    match executor_type:
        case ExecutorType.SIMPLE:
            return SimpleExecutor(
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                metadata=metadata,
                fainder_mode=fainder_mode,
                enable_highlighting=enable_highlighting,
                min_usability_score=min_usability_score,
                rank_by_usability=rank_by_usability,
            )
        case ExecutorType.PREFILTERING:
            return PrefilteringExecutor(
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                metadata=metadata,
                fainder_mode=fainder_mode,
                enable_highlighting=enable_highlighting,
                min_usability_score=min_usability_score,
                rank_by_usability=rank_by_usability,
            )
        case ExecutorType.THREADED:
            return ThreadedExecutor(
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                metadata=metadata,
                fainder_mode=fainder_mode,
                enable_highlighting=enable_highlighting,
                min_usability_score=min_usability_score,
                rank_by_usability=rank_by_usability,
                max_workers=max_workers,
            )
        case ExecutorType.THREADED_PREFILTERING:
            return ThreadedPrefilteringExecutor(
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                metadata=metadata,
                fainder_mode=fainder_mode,
                enable_highlighting=enable_highlighting,
                min_usability_score=min_usability_score,
                rank_by_usability=rank_by_usability,
                max_workers=max_workers,
            )
        case _:
            raise ValueError(f"Unknown executor type: {executor_type}")
