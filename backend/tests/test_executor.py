import time

import pytest
from loguru import logger

from backend.config import FainderMode
from backend.engine import Engine, Optimizer

from .assets.test_cases_executor import EXECUTOR_CASES, ExecutorCase


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [(cat, name, case) for cat, cases in EXECUTOR_CASES.items() for name, case in cases.items()],
)
def test_execute(
    category: str,
    test_name: str,
    test_case: ExecutorCase,
    default_engine: Engine,
    prefiltering_engine: Engine,
    parallel_engine: Engine,
    parallel_prefiltering_engine: Engine,
    small_fainder_engine: Engine,
) -> None:
    query = test_case["query"]
    expected_result = test_case["expected"]

    # Execute with all configurations
    default_engine.optimizer = Optimizer()
    exec_start = time.perf_counter()
    default_result, _ = default_engine.execute(query, enable_highlighting=False)
    default_time = time.perf_counter() - exec_start

    default_engine.optimizer = Optimizer(cost_sorting=True, keyword_merging=False)
    exec_start = time.perf_counter()
    no_merging_result, _ = default_engine.execute(query, enable_highlighting=False)
    no_merging_time = time.perf_counter() - exec_start

    default_engine.optimizer = Optimizer(cost_sorting=False, keyword_merging=False)
    exec_start = time.perf_counter()
    no_opt_result, _ = default_engine.execute(query, enable_highlighting=False)
    no_opt_time = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    prefiltering_result, _ = prefiltering_engine.execute(query, enable_highlighting=False)
    prefiltering_time = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    parallel_result, _ = parallel_engine.execute(query, enable_highlighting=False)
    parallel_time = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    parallel_prefiltering_result, _ = parallel_prefiltering_engine.execute(
        query, enable_highlighting=False
    )
    parallel_prefiltering_time = time.perf_counter() - exec_start

    exec_start = time.perf_counter()
    small_fainder_exact_result, _ = small_fainder_engine.execute(
        query, enable_highlighting=False, fainder_mode=FainderMode.EXACT
    )
    small_fainder_exact_time = time.perf_counter() - exec_start

    # Log timing information in a structured format
    performance_log: dict[str, str | float] = {
        "test_type": "executor",
        "category": category,
        "test_name": test_name,
        "query": query,
        "default_time": default_time,
        "no_merging_time": no_merging_time,
        "no_opt_time": no_opt_time,
        "prefiltering_time": prefiltering_time,
        "parallel_time": parallel_time,
        "parallel_prefiltering_time": parallel_prefiltering_time,
        "small_fainder_exact_time": small_fainder_exact_time,
    }
    logger.info(performance_log)

    # Verify all results are consistent and match the expected result
    assert set(default_result) == set(expected_result), (
        f"Default result: {default_result}, Expected: {expected_result}"
    )
    assert set(no_merging_result) == set(expected_result), (
        f"No merging result: {no_merging_result}, Expected: {expected_result}"
    )
    assert set(no_opt_result) == set(expected_result), (
        f"No opt result: {no_opt_result}, Expected: {expected_result}"
    )
    assert set(prefiltering_result) == set(expected_result), (
        f"Prefiltering result: {prefiltering_result}, Expected: {expected_result}"
    )
    assert set(parallel_result) == set(expected_result), (
        f"Parallel result: {parallel_result}, Expected: {expected_result}"
    )
    assert set(parallel_prefiltering_result) == set(expected_result), (
        f"Parallel prefiltering result: {parallel_prefiltering_result}, "
        f"Expected: {expected_result}"
    )
    assert set(small_fainder_exact_result) == set(expected_result), (
        f"Small Fainder exact result: {small_fainder_exact_result}, Expected: {expected_result}"
    )
