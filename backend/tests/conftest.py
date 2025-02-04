import json
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from backend.column_index import ColumnIndex
from backend.config import Metadata, Settings
from backend.fainder_index import FainderIndex
from backend.lucene_connector import LuceneConnector
from backend.query_evaluator import QueryEvaluator


@pytest.fixture(autouse=True, scope="module")
def _setup_and_teardown() -> Generator[None, Any, None]:
    """
    Generic setup and teardown fixture that runs before and after each test.
    """
    # Setup code

    # Create logs directory if it doesn't exist
    log_dir = Path("logs/logs")
    log_dir.mkdir(exist_ok=True)

    # Remove default handler
    logger.remove()

    # Add handlers for both file and console
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | {message}",
        filter=lambda record: record["level"].name == "INFO",
    )
    logger.add(
        "logs/query_performance__{time:YYYY-MM-DD HH:mm:ss}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        filter=lambda record: record["level"].name == "INFO",
        rotation="1 day",
    )

    yield

    # Teardown code
    pass


@pytest.fixture(scope="module")
def evaluator() -> QueryEvaluator:
    settings = Settings(
        data_dir=Path(__file__).parent / "assets",
        collection_name="toy_collection",
        _env_file=None,  # type: ignore
    )
    with settings.metadata_path.open() as file:
        metadata = Metadata(**json.load(file))

    lucene_connector = LuceneConnector(settings.lucene_host, settings.lucene_port)
    # Fainder indices for testing are generated with the following parameters:
    # n_clusters = 27, bin_budget = 270, alpha = 1, transform = None,
    fainder_index = FainderIndex(
        metadata=metadata,
        rebinning_path=settings.rebinning_index_path,
        conversion_path=settings.conversion_index_path,
    )
    column_index = ColumnIndex(path=settings.hnsw_index_path, metadata=metadata)
    return QueryEvaluator(
        lucene_connector=lucene_connector,
        fainder_index=fainder_index,
        hnsw_index=column_index,
        metadata=metadata,
        cache_size=0,
    )
