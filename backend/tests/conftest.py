import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from backend.config import Settings
from backend.fainder_index import FainderIndex
from backend.lucene_connector import LuceneConnector
from backend.query_evaluator import QueryEvaluator


@pytest.fixture(autouse=True, scope="module")
def _setup_and_teardown() -> Generator[None, Any, None]:
    """
    Generic setup and teardown fixture that runs before and after each test.
    """
    # Setup code
    # TODO: Set up logging properly
    logger.remove()
    logger.add(sys.stderr, level="INFO")

    yield

    # Teardown code
    pass


@pytest.fixture(scope="module")
def evaluator() -> QueryEvaluator:
    settings = Settings(
        data_dir=Path(__file__).parent / "assets", collection_name="toy_collection"
    )
    metadata = settings.metadata

    lucene_connector = LuceneConnector(settings.lucene_host, settings.lucene_port)
    rebinning_index = FainderIndex(settings.rebinning_index_path, metadata)
    conversion_index = FainderIndex(settings.conversion_index_path, metadata)
    return QueryEvaluator(
        set(metadata.doc_to_cols.keys()), lucene_connector, rebinning_index, conversion_index
    )
