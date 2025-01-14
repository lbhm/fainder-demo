import time
from typing import Any

import pytest
from loguru import logger

from backend.query_evaluator import QueryEvaluator

TEST_CASES: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
    "basic_keyword": {
        "queries": {
            "simple_keyword": {"query": "kw(germany)", "expected": [0]},
            "simple_keyword_a": {"query": "kw(a)", "expected": [2, 1, 0]},
            "not_keyword": {"query": "NOT kw(a)", "expected": []},
        }
    },
    "basic_percentile": {
        "queries": {
            "simple_percentile": {"query": "pp(0.5;ge;2000)", "expected": [0, 1, 2]},
            "high_percentile": {"query": "pp(0.9;ge;1000000)", "expected": [1, 2]},
        }
    },
    "combined_operations": {
        "queries": {
            "keyword_and_percentile": {
                "query": "kw(germany) AND pp(0.5;ge;20.0)",
                "expected": [0],
            },
            "high_percentile_and_keyword": {
                "query": "pp(0.9;ge;1000000) AND kw(germany)",
                "expected": [],
            },
            "high_percentile_or_keyword": {
                "query": "pp(0.9;ge;1000000) OR kw(germany)",
                "expected": [0, 1, 2],
            },
            "high_percentile_xor_simple_keyword_a": {
                "query": "pp(0.9;ge;1000000) XOR kw(a)",
                "expected": [0],
            },
        }
    },
    "nested_queries": {
        "queries": {
            "nested_query_1": {
                "query": "(kw(a) AND pp(0.9;ge;1000000)) OR kw(germany)",
                "expected": [0, 2, 1],
            },
            "nested_query_2": {
                "query": "(kw(a) AND pp(0.9;ge;1000000)) XOR kw(germany)",
                "expected": [0, 2, 1],
            },
            "nested_query_3": {
                "query": "(kw(a) AND pp(0.9;ge;1000000)) AND kw(germany)",
                "expected": [],
            },
            "nested_not_query": {"query": "NOT (kw(a) AND pp(0.9;ge;1000000))", "expected": [0]},
        }
    },
    "syntax_variations": {
        "queries": {
            "optional_whitespaces": {"query": "kw(a) AND pp (0.9;ge;1000000)", "expected": [2, 1]},
            "no_whitespaces": {"query": "kw(a)ANDpp(0.9;ge;1000000)", "expected": [2, 1]},
            "case_insensitive": {"query": "KW(a)AND Pp(0.9;ge;1000000)", "expected": [2, 1]},
        }
    },
    "column_operations": {
        "queries": {
            "column_name": {"query": "col(Latitude; 0)", "expected": [0]},
            "percentile_with_identifer": {
                "query": "col(Latitude; 0) AND pp(0.5;ge;50)",
                "expected": [0],
            },
            "keyword_filter": {
                "query": "col(Latitude; 0) AND pp(0.5;ge;50) AND kw(a)",
                "expected": [0],
            },
        }
    },
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [
        (cat, name, case)
        for cat, data in TEST_CASES.items()
        for name, case in data["queries"].items()
    ],
)
async def test_new_grammar_correctness(
    category: str, test_name: str, test_case: dict[str, Any], evaluator: QueryEvaluator
) -> None:
    query = test_case["query"]
    expected_result = test_case["expected"]

    start = time.perf_counter()
    result1 = await evaluator.execute(query)
    end = time.perf_counter()
    time_taken_1 = end - start
    logger.info(f"Result1: {result1}")

    start = time.perf_counter()
    result2 = await evaluator.execute(query, enable_filtering=False)
    end = time.perf_counter()
    time_taken_2 = end - start
    logger.info(f"Result2: {result2}")

    assert result1 == result2
    assert expected_result == result1

    logger.info(f"Time taken with filter: {time_taken_1} and without filter: {time_taken_2}")
    div = time_taken_1 - time_taken_2
    logger.info(f"Time difference: {div}")
