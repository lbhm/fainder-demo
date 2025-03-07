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

    # Execute with all configurations
    exec_start = time.perf_counter()
    result1, _ = evaluator.execute(
        query,
        enable_highlighting=False,
        enable_filtering=False,
        enable_kw_merge=False,
        enable_cost_sorting=False,
    )
    exec_time = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    result_kw_merge, _ = evaluator.execute(
        query,
        enable_highlighting=False,
        enable_filtering=False,
        enable_kw_merge=True,
        enable_cost_sorting=False,
    )
    exec_time_kw_merge = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    result_kw_merge_cost_sorting, _ = evaluator.execute(
        query,
        enable_highlighting=False,
        enable_filtering=False,
        enable_kw_merge=True,
        enable_cost_sorting=True,
    )
    exec_time_cost_sorting = time.perf_counter() - exec_start

    # Log timing information in a structured format
    performance_log = {
        "test_type": "executor",
        "category": category,
        "test_name": test_name,
        "query": query,
        "execution_time": exec_time,
        "execution_time_kw_merge": exec_time_kw_merge,
        "execution_time_kw_merge_sort": exec_time_cost_sorting,
    }
    logger.info(performance_log)

    # Verify results are consistent
    assert (
        set(result1)
        == set(result_kw_merge)
        == set(expected_result)
        == set(result_kw_merge_cost_sorting)
    )
