import time
from typing import Any, Tuple, Dict, Callable
from loguru import logger
import pytest
import csv

from backend.query_evaluator import QueryEvaluator


TEST_CASES: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
    "base_keyword_queries": {
        "queries": {
            "double_wildcard_search": {"query": "kw(*a*)"},
            "wildcard_search": {"query": "kw(a*)"},
        }
    },
    "base_simple_keyword_queries": {
        "queries": {
            # just some words that are likely to be in the collection
            "simple_keyword_1": {"query": "kw(born)"},
            "simple_keyword_2": {"query": "kw(by)"},
            "simple_keyword_3": {"query": "kw(blood)"},
            "simple_keyword_4": {"query": "kw(heart)"},
            "simple_keyword_5": {"query": "kw(lung)"},
            "simple_keyword_6": {"query": "kw(test)"},
            "simple_keyword_7": {"query": "kw(germany)"},
            "simple_keyword_8": {"query": "kw(italy)"},
            "simple_keyword_9": {"query": "kw(usa)"},
            "simple_keyword_10": {"query": "kw(bank)"},
        }
    },

    "base_keyword_queries_1": {
        "queries": {
            "simple_keyword": {"query": "kw(lung)"},
            "not_keyword": {"query": "NOT kw(lung)",},
            "wildcard_search": {"query": "kw(lu?g)"},
            "double_wildcard_searches": {"query": "kw(?u?g)"},
            "field_specific_keyword": {"query": 'kw(alternateName:"Lung")'},
        }
    },
    "base_keyword_queries_2": {
        "queries": {
            "simple_keyword": {"query": "kw(heart)"},
            "not_keyword": {"query": "NOT kw(heart)",},
            "wildcard_search": {"query": "kw(he?rt)"},
            "double_wildcard_searches": {"query": "kw(h?art)"},
            "field_specific_keyword": {"query": 'kw(alternateName:"Heart")'},
        }
    },
    "base_percentile_queries": {
        "queries": {
            "small_percentile_1": {"query": "col(pp(0.5;le;2000))"},
            "small_percentile_2": {"query": "col(pp(0.5;le;1000))"},
            "small_percentile_3": {"query": "col(pp(0.5;le;500))"},
            "small_percentile_4": {"query": "col(pp(0.5;le;200))"},
            "high_percentile_1": {"query": "col(pp(0.9;ge;1000000))"},
            "high_percentile_2": {"query": "col(pp(0.9;ge;2000000))"},
            "high_percentile_3": {"query": "col(pp(0.9;ge;3000000))"},
            "high_percentile_4": {"query": "col(pp(0.9;ge;4000000))"},
        }
    },
    "base_name_queryies": {
        "queries": {
            "simple_name": {"query": "col(name(age; 0))"},
            "not_name": {"query": "col(NOT name(age; 0))"},
            "simple_name_2": {"query": "col(name(age; 3))"}
            },
    }
}

def execute_and_time(
    evaluator: QueryEvaluator,
    query: str,
    eval_params: Dict[str, Any]
) -> Tuple[Any, float]:
    """Execute a query with given parameters and measure execution time."""
    start_time = time.time()
    result, _ = evaluator.execute(query, **eval_params)
    end_time = time.time()
    return result, end_time - start_time

def run_evaluation_scenarios(
    evaluator: QueryEvaluator,
    query: str,
    scenarios: Dict[str, Dict[str, Any]]
) -> Tuple[Dict[str, float], Dict[str, Any], bool]:
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
    timings: Dict[str, float],
    cache_info: Any,
    is_consistent: bool
) -> None:
    """Log performance data to CSV file with one row per scenario."""
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    
    with open(csv_path, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)
        for scenario, execution_time in timings.items():
            writer.writerow([
                timestamp,
                category,
                test_name,
                query,
                scenario,
                execution_time,
                cache_info.hits,
                cache_info.misses,
                cache_info.curr_size,
                is_consistent
            ])

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
        "sequential": {
            "enable_filtering": False,
            "enable_highlighting": True
        },
        "filtered": {
            "enable_filtering": True,
            "enable_highlighting": True
        },
        "sequential_no_highlight": {
            "enable_filtering": False,
            "enable_highlighting": False
        },
        "filtered_no_highlight": {
            "enable_filtering": True,
            "enable_highlighting": False
        }
    }
    
    # Run all scenarios
    timings, results, is_consistent = run_evaluation_scenarios(
        performance_evaluator, query, evaluation_scenarios
    )
    
    # Get cache info
    cache_info = performance_evaluator.cache_info()
    
    # Log to CSV
    log_performance_csv(
        pytest.csv_log_path,
        category,
        test_name,
        query,
        timings,
        cache_info,
        is_consistent
    )
    
    # Create detailed performance log for console/file
    performance_log = {
        "category": category,
        "test_name": test_name,
        "query": query,
        "metrics": {
            "timings": timings,
            "timing_comparisons": {
                "filter_overhead": timings["filtered"] - timings["sequential"],
                "highlighting_overhead": timings["sequential"] - timings["sequential_no_highlight"],
            }
        },
        "cache_stats": {
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "max_size": cache_info.max_size,
            "curr_size": cache_info.curr_size,
        },
        "results_consistent": is_consistent
    }
    
    logger.info("PERFORMANCE_DATA: " + str(performance_log))
    
    # Assert that all results are consistent
    assert is_consistent, "Results differ between evaluation methods"
