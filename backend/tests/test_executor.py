import time

import pytest
from loguru import logger

from backend.engine import Engine, Optimizer

from .assets.test_cases_executor import EXECUTOR_CASES, ExecutorCase


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [(cat, name, case) for cat, cases in EXECUTOR_CASES.items() for name, case in cases.items()],
)
def test_execute(category: str, test_name: str, test_case: ExecutorCase, engine: Engine) -> None:
    query = test_case["query"]
    expected_result = test_case["expected"]

    # Execute with all configurations
    engine.optimizer = Optimizer()
    exec_start = time.perf_counter()
    default_result, _ = engine.execute(
        query,
        enable_highlighting=False,
        enable_filtering=False,
    )
    default_time = time.perf_counter() - exec_start

    engine.optimizer = Optimizer(cost_sorting=True, keyword_merging=False)
    exec_start = time.perf_counter()
    no_merging_result, _ = engine.execute(
        query,
        enable_highlighting=False,
        enable_filtering=False,
    )
    no_merging_time = time.perf_counter() - exec_start

    engine.optimizer = Optimizer(cost_sorting=False, keyword_merging=False)
    exec_start = time.perf_counter()
    no_opt_result, _ = engine.execute(
        query,
        enable_highlighting=False,
        enable_filtering=False,
    )
    no_opt_time = time.perf_counter() - exec_start

    # Log timing information in a structured format
    performance_log = {
        "test_type": "executor",
        "category": category,
        "test_name": test_name,
        "query": query,
        "default_time": default_time,
        "no_merging_time": no_merging_time,
        "no_opt_time": no_opt_time,
    }
    logger.info(performance_log)

    # Verify results are consistent
    assert (
        set(default_result) == set(no_merging_result) == set(expected_result) == set(no_opt_result)
    )
