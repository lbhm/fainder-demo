import csv
import time
from typing import Any

import pytest
from loguru import logger

from backend.query_evaluator import QueryEvaluator

from .generate_test_cases import generate_all_test_cases

TEST_CASES = generate_all_test_cases()


def execute_and_time(
    evaluator: QueryEvaluator, query: str, eval_params: dict[str, Any]
) -> tuple[Any, float]:
    """Execute a query with given parameters and measure execution time."""
    start_time = time.time()
    result, _ = evaluator.execute(query, **eval_params)
    end_time = time.time()
    return result, end_time - start_time


def run_evaluation_scenarios(
    evaluator: QueryEvaluator, query: str, scenarios: dict[str, dict[str, Any]]
) -> tuple[dict[str, float], dict[str, Any], bool]:
    """
    Run multiple evaluation scenarios for a query and return timing results.
    Returns (timings, results, is_consistent)
    """
    timings = {}
    results = {}

    for scenario_name, params in scenarios.items():
        result, execution_time = execute_and_time(evaluator, query, params)
        timings[scenario_name] = execution_time
        results[scenario_name] = result

    # Check if all results are consistent
    first_result = next(iter(results.values()))
    is_consistent = all(result == first_result for result in results.values())

    return timings, results, is_consistent


def log_performance_csv(
    csv_path: str,
    category: str,
    test_name: str,
    query: str,
    timings: dict[str, float],
    cache_info: Any,
    is_consistent: bool,
) -> None:
    """Log performance data to CSV file with one row per scenario."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(csv_path, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        for scenario, execution_time in timings.items():
            writer.writerow(
                [
                    timestamp,
                    category,
                    test_name,
                    query,
                    scenario,
                    execution_time,
                    cache_info.hits,
                    cache_info.misses,
                    cache_info.curr_size,
                    is_consistent,
                ]
            )


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [
        (cat, name, case)
        for cat, data in TEST_CASES.items()
        for name, case in data["queries"].items()
    ],
)
def test_performance(
    category: str, test_name: str, test_case: dict[str, Any], performance_evaluator: QueryEvaluator
) -> None:
    query = test_case["query"]

    # Define different evaluation scenarios
    evaluation_scenarios = {
        "sequential": {"enable_filtering": False, "enable_highlighting": True},
        "filtered": {"enable_filtering": True, "enable_highlighting": True},
        "sequential_no_highlight": {"enable_filtering": False, "enable_highlighting": False},
        "filtered_no_highlight": {"enable_filtering": True, "enable_highlighting": False},
    }

    # Run all scenarios
    timings, results, is_consistent = run_evaluation_scenarios(
        performance_evaluator, query, evaluation_scenarios
    )

    # Get cache info
    cache_info = performance_evaluator.cache_info()

    # Log to CSV
    csv_path = pytest.csv_log_path  # type: ignore
    log_performance_csv(csv_path, category, test_name, query, timings, cache_info, is_consistent)

    # Create detailed performance log for console/file
    performance_log = {
        "category": category,
        "test_name": test_name,
        "query": query,
        "metrics": {
            "timings": timings,
            "timing_comparisons": {
                "filter_overhead": timings["filtered"] - timings["sequential"],
                "highlighting_overhead": timings["sequential"]
                - timings["sequential_no_highlight"],
            },
        },
        "cache_stats": {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "max_size": cache_info.max_size,
            "curr_size": cache_info.curr_size,
        },
        "results_consistent": is_consistent,
    }

    logger.info("PERFORMANCE_DATA: " + str(performance_log))

    # Assert that all results are consistent
    assert is_consistent, "Results differ between evaluation methods"
