import csv
import json
import sys
import time
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
    base_log_dir = Path("logs")
    base_log_dir.mkdir(exist_ok=True)
    log_dir = Path("logs/logs")
    log_dir.mkdir(exist_ok=True)

    performance_log_dir = Path("logs/performance")
    performance_log_dir.mkdir(exist_ok=True)

    # Create CSV performance log file and write headers
    csv_log_path = (
        performance_log_dir / f"performance_metrics_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    )
    with open(csv_log_path, "w", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(
            [
                "timestamp",
                "category",
                "test_name",
                "query",
                "scenario",
                "execution_time",
                "cache_hits",
                "cache_misses",
                "cache_size",
                "results_consistent",
                "num_results",
                "results",
                "ids",
                "num_terms",
                "id_str",
            ]
        )

    # Remove default handler
    logger.remove()

    # Add handlers for both file and console
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | {message}",
        filter=lambda record: record["level"].name == "INFO",
    )
    logger.add(
        "logs/logs/query_performance__{time:YYYY-MM-DD HH:mm:ss}.log",
        format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
        filter=lambda record: record["level"].name == "INFO",
        rotation="1 day",
    )

    # Add CSV log path to pytest's config
    pytest.csv_log_path = csv_log_path  # type: ignore

    yield

    # Teardown code
    pass


@pytest.fixture(scope="module")
def performance_evaluator() -> QueryEvaluator:
    settings = Settings()  # type: ignore # uses the environment variables
    with settings.metadata_path.open() as file:
        metadata = Metadata(**json.load(file))

    lucene_connector = LuceneConnector(settings.lucene_host, settings.lucene_port)

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
