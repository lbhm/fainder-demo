import time

import pytest
from loguru import logger

from backend.query_evaluator import QueryEvaluator

from .assets.test_cases import TEST_CASES, Case


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [(cat, name, case) for cat, cases in TEST_CASES.items() for name, case in cases.items()],
)
def test_grammar_correctness(
    category: str, test_name: str, test_case: Case, evaluator: QueryEvaluator
) -> None:
    query = test_case["query"]
    expected_result = test_case["expected"]

    # Execute twice with caching to measure impact of cache hits
    exec_start = time.perf_counter()
    result1, _ = evaluator.execute(query)
    cold_exec_time = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    result1_cached, _ = evaluator.execute(query)
    warm_exec_time = time.perf_counter() - exec_start

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
        "test_type": "executor",
        "category": category,
        "test_name": test_name,
        "query": query,
        "metrics": {
            "cold_exec_time": cold_exec_time,
            "warm_exec_time": warm_exec_time,
            "no_cache_exec_time": no_cache_exec_time,
            "cache_speedup": no_cache_exec_time / warm_exec_time,
        },
        "cache_stats": {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "max_size": cache_info.max_size,
            "curr_size": cache_info.curr_size,
        },
    }
    logger.info(performance_log)

    # Verify results are consistent
    assert set(result1) == set(result2)
    assert set(result1) == set(result1_cached)
    assert set(expected_result) == set(result1)
