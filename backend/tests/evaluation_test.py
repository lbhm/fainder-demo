import time
from typing import Any

import pytest
from loguru import logger

from backend.query_evaluator import QueryEvaluator
from tests.testing_data import TEST_CASES


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [
        (cat, name, case)
        for cat, data in TEST_CASES.items()
        for name, case in data["queries"].items()
    ],
)
def test_grammar_correctness(
    category: str, test_name: str, test_case: dict[str, Any], evaluator: QueryEvaluator
) -> None:
    query = test_case["query"]
    expected_result = test_case["expected"]

    # First run with caching enabled (default)
    parse_start = time.perf_counter()
    _ = evaluator.parse(query)
    parse_end = time.perf_counter()
    parse_time = parse_end - parse_start

    # Execute twice with caching to measure cache hit
    exec_start = time.perf_counter()
    result1, _ = evaluator.execute(query)
    first_exec_time = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    result1_cached, _ = evaluator.execute(query)
    cached_exec_time = time.perf_counter() - exec_start

    # Execute without caching
    no_cache_evaluator = QueryEvaluator(
        lucene_connector=evaluator.lucene_connector,
        fainder_index=evaluator.executor.fainder_index,
        hnsw_index=evaluator.executor.hnsw_index,
        metadata=evaluator.executor.metadata,
        cache_size=-1,
    )

    exec_start = time.perf_counter()
    result2, _ = no_cache_evaluator.execute(query)
    no_cache_exec_time = time.perf_counter() - exec_start

    # Log cache statistics
    cache_info = evaluator.cache_info()
    # Log timing information in a structured format
    performance_log = {
        "category": category,
        "test_name": test_name,
        "query": query,
        "metrics": {
            "parse_time": parse_time,
            "first_exec_time": first_exec_time,
            "cached_exec_time": cached_exec_time,
            "non_cached_exec_time": no_cache_exec_time,
            "cache_speedup": no_cache_exec_time / cached_exec_time,
        },
        "cache_stats": {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "max_size": cache_info.max_size,
            "curr_size": cache_info.curr_size,
        },
    }

    # Log as JSON for easier parsing
    logger.info("PERFORMANCE_DATA: " + str(performance_log))

    # Verify results are consistent
    assert set(result1) == set(result2)
    assert set(result1) == set(result1_cached)
    assert set(expected_result) == set(result1)
