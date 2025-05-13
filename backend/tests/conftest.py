import json
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from backend.config import ExecutorType, Metadata, Settings
from backend.engine import Engine, Parser
from backend.indices import FainderIndex, HnswIndex, TantivyIndex


@pytest.fixture(autouse=True, scope="module")
def _setup_and_teardown() -> Generator[None, Any, None]:  # pyright: ignore[reportUnusedFunction]
    """
    Generic setup and teardown fixture that runs before and after each test.
    """
    # Setup code

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Remove default handler
    logger.remove()

    # Add handlers for both file and console
    logger.add(
        sys.stdout,
        format="{time:HH:mm:ss} | {level: >5} | {file}:{line} | <level>{message}</level>",
        level="TRACE",
    )
    logger.add(
        "logs/test_{time:YYYY-MM-DD HH:mm:ss}.log",
        format="{time:HH:mm:ss} | {level: >5} | {file}:{line} | {message}",
        level="TRACE",
    )

    yield

    # Teardown code
    pass  # noqa: PIE790


@pytest.fixture(scope="module")
def default_engine() -> Engine:
    settings = Settings(
        data_dir=Path(__file__).parent / "assets",
        collection_name="toy_collection",
        _env_file=None,  # type: ignore
    )

    with settings.metadata_path.open() as file:
        metadata = Metadata(**json.load(file))

    tantivy_index = TantivyIndex(index_path=settings.tantivy_path, recreate=False)
    # Fainder indices for testing are generated with the following parameters:
    # n_clusters = 23, bin_budget = 230, alpha = 1, transform = None,
    fainder_index = FainderIndex(
        rebinning_path=settings.rebinning_index_path,
        conversion_path=settings.conversion_index_path,
        histogram_path=settings.histogram_path,
    )
    hnsw_index = HnswIndex(path=settings.hnsw_index_path, metadata=metadata, use_embeddings=False)
    return Engine(
        tantivy_index=tantivy_index,
        fainder_index=fainder_index,
        hnsw_index=hnsw_index,
        metadata=metadata,
        cache_size=-1,
        min_usability_score=settings.min_usability_score,
        rank_by_usability=settings.rank_by_usability,
        executor_type=settings.executor_type,
        max_workers=settings.max_workers,
    )


@pytest.fixture(scope="module")
def small_fainder_engine() -> Engine:
    settings = Settings(
        data_dir=Path(__file__).parent / "assets",
        collection_name="toy_collection",
        _env_file=None,  # type: ignore
    )

    with settings.metadata_path.open() as file:
        metadata = Metadata(**json.load(file))

    tantivy_index = TantivyIndex(index_path=settings.tantivy_path, recreate=False)
    # Fainder indices for testing are generated with the following parameters:
    # n_clusters = 10, bin_budget = 230, alpha = 1, transform = None,
    rebinning_path = settings.rebinning_index_path.parent / "rebinning_small.zst"
    conversion_path = settings.conversion_index_path.parent / "conversion_small.zst"
    fainder_index = FainderIndex(
        rebinning_path=rebinning_path,
        conversion_path=conversion_path,
        histogram_path=settings.histogram_path,
    )
    hnsw_index = HnswIndex(path=settings.hnsw_index_path, metadata=metadata, use_embeddings=False)
    return Engine(
        tantivy_index=tantivy_index,
        fainder_index=fainder_index,
        hnsw_index=hnsw_index,
        metadata=metadata,
        cache_size=-1,
        min_usability_score=settings.min_usability_score,
        rank_by_usability=settings.rank_by_usability,
        executor_type=settings.executor_type,
        max_workers=settings.max_workers,
    )


@pytest.fixture(scope="module")
def prefiltering_engine() -> Engine:
    settings = Settings(
        data_dir=Path(__file__).parent / "assets",
        collection_name="toy_collection",
        _env_file=None,  # type: ignore
    )

    with settings.metadata_path.open() as file:
        metadata = Metadata(**json.load(file))

    tantivy_index = TantivyIndex(index_path=settings.tantivy_path, recreate=False)
    # Fainder indices for testing are generated with the following parameters:
    # n_clusters = 23, bin_budget = 230, alpha = 1, transform = None,
    fainder_index = FainderIndex(
        rebinning_path=settings.rebinning_index_path,
        conversion_path=settings.conversion_index_path,
        histogram_path=settings.histogram_path,
    )
    hnsw_index = HnswIndex(path=settings.hnsw_index_path, metadata=metadata, use_embeddings=False)
    return Engine(
        tantivy_index=tantivy_index,
        fainder_index=fainder_index,
        hnsw_index=hnsw_index,
        metadata=metadata,
        cache_size=-1,
        executor_type=ExecutorType.PREFILTERING,
        min_usability_score=settings.min_usability_score,
        rank_by_usability=settings.rank_by_usability,
        max_workers=settings.max_workers,
    )


@pytest.fixture(scope="module")
def parallel_engine() -> Engine:
    settings = Settings(
        data_dir=Path(__file__).parent / "assets",
        collection_name="toy_collection",
        _env_file=None,  # type: ignore
    )

    with settings.metadata_path.open() as file:
        metadata = Metadata(**json.load(file))

    tantivy_index = TantivyIndex(index_path=settings.tantivy_path, recreate=False)
    # Fainder indices for testing are generated with the following parameters:
    # n_clusters = 23, bin_budget = 230, alpha = 1, transform = None,
    fainder_index = FainderIndex(
        rebinning_path=settings.rebinning_index_path,
        conversion_path=settings.conversion_index_path,
        histogram_path=settings.histogram_path,
    )
    hnsw_index = HnswIndex(path=settings.hnsw_index_path, metadata=metadata, use_embeddings=False)
    return Engine(
        tantivy_index=tantivy_index,
        fainder_index=fainder_index,
        hnsw_index=hnsw_index,
        metadata=metadata,
        cache_size=-1,
        executor_type=ExecutorType.THREADED,
        min_usability_score=settings.min_usability_score,
        rank_by_usability=settings.rank_by_usability,
        max_workers=settings.max_workers,
    )


@pytest.fixture(scope="module")
def parallel_prefiltering_engine() -> Engine:
    settings = Settings(
        data_dir=Path(__file__).parent / "assets",
        collection_name="toy_collection",
        _env_file=None,  # type: ignore
    )

    with settings.metadata_path.open() as file:
        metadata = Metadata(**json.load(file))

    tantivy_index = TantivyIndex(index_path=settings.tantivy_path, recreate=False)
    # Fainder indices for testing are generated with the following parameters:
    # n_clusters = 23, bin_budget = 230, alpha = 1, transform = None,
    fainder_index = FainderIndex(
        rebinning_path=settings.rebinning_index_path,
        conversion_path=settings.conversion_index_path,
        histogram_path=settings.histogram_path,
    )
    hnsw_index = HnswIndex(path=settings.hnsw_index_path, metadata=metadata, use_embeddings=False)
    return Engine(
        tantivy_index=tantivy_index,
        fainder_index=fainder_index,
        hnsw_index=hnsw_index,
        metadata=metadata,
        cache_size=-1,
        executor_type=ExecutorType.THREADED_PREFILTERING,
        min_usability_score=settings.min_usability_score,
        rank_by_usability=settings.rank_by_usability,
        max_workers=settings.max_workers,
    )


@pytest.fixture(scope="module")
def parser() -> Parser:
    return Parser()
