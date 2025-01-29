import time
from typing import Any

import pytest
from loguru import logger

from backend.query_evaluator import QueryEvaluator

TEST_CASES: dict[str, dict[str, dict[str, dict[str, Any]]]] = {
    "basic_keyword": {
        "queries": {
            "simple_keyword": {"query": "kw(germany)", "expected": [0]},
            "not_keyword": {"query": "NOT kw(germany)", "expected": [2, 1]},
        }
    },
    "queryparser": {
        "queries": {
            "field_specific_keyword": {"query": 'kw(alternateName:"Weather")', "expected": [0]},
            "field_specific_keyword_or": {
                "query": 'kw(alternateName:"Weather" OR *a*)',
                "expected": [0, 2, 1],
            },
            "wildcard_searches": {"query": 'kw(alternateName:"Wea*")', "expected": [0]},
            "wildcard_searches_2": {"query": "kw(Germa?y)", "expected": [0, 2, 1]},
            "double_wildcard_searches": {"query": "kw(*a*)", "expected": [2, 1, 0]},
        }
    },
    "basic_percentile": {
        "queries": {
            "simple_percentile": {"query": "col(pp(0.5;ge;2000))", "expected": [0, 1, 2]},
            "high_percentile": {"query": "col(pp(0.9;ge;1000000))", "expected": [1, 2]},
        }
    },
    "combined_operations": {
        "queries": {
            "keyword_and_percentile": {
                "query": "kw(germany) AND col(pp(0.5;ge;20.0))",
                "expected": [0],
            },
            "high_percentile_and_keyword": {
                "query": "col(pp(0.9;ge;1000000)) AND kw(germany)",
                "expected": [],
            },
            "high_percentile_or_keyword": {
                "query": "col(pp(0.9;ge;1000000)) OR kw(germany)",
                "expected": [0, 1, 2],
            },
            "high_percentile_xor_simple_keyword_a": {
                "query": "col(pp(0.5;ge;2000)) XOR kw(germany)",
                "expected": [0],
            },
        }
    },
    "nested_queries": {
        "queries": {
            "nested_query_1": {
                "query": "(kw(*a*) AND col(pp(0.9;ge;1000000))) OR kw(germany)",
                "expected": [0, 2, 1],
            },
            "nested_query_2": {
                "query": "(kw(*a*) AND col(pp(0.9;ge;1000000))) XOR kw(germany)",
                "expected": [0, 2, 1],
            },
            "nested_query_3": {
                "query": "(kw(*a*) AND col(pp(0.9;ge;1000000))) AND kw(germany)",
                "expected": [],
            },
            "nested_not_query": {
                "query": "NOT (kw(*a*) AND col(pp(0.9;ge;1000000)))",
                "expected": [0],
            },
        }
    },
    "syntax_variations": {
        "queries": {
            "optional_whitespaces": {
                "query": "kw(*a*) AND col(pp (0.9;ge;1000000))",
                "expected": [2, 1],
            },
            "no_whitespaces": {"query": "kw(*a*)ANDcol(pp(0.9;ge;1000000))", "expected": [2, 1]},
            "case_insensitive": {
                "query": "KW(*a*)AND col(Pp(0.9;ge;1000000))",
                "expected": [2, 1],
            },
        }
    },
    "column_operations": {
        "queries": {
            "column_name": {"query": "col(name(Latitude; 0))", "expected": [0]},
            "percentile_with_identifer": {
                "query": "col(name(Latitude; 0) AND pp(0.5;ge;50))",
                "expected": [0],
            },
            "keyword_filter": {
                "query": "col(name(Latitude; 0) AND pp(0.5;ge;50)) AND kw(*a*)",
                "expected": [0],
            },
            "nested_column": {
                "query": "col(name(Latitude; 0) AND pp(0.5;ge;50))",
                "expected": [0],
            },
            "not_column": {"query": "NOT col(name(Latitude; 0))", "expected": [1, 2]},
            "complex_column": {
                "query": "col((name(Latitude; 0) AND pp(0.5;ge;50)) OR name(Longitude; 0))",
                "expected": [0],
            },
            "not_complex_column": {
                "query": "NOT col((name(Latitude; 0) AND pp(0.5;ge;50)))",
                "expected": [1, 2],
            },
            "multiple_columns": {
                "query": "col(name(Latitude; 0)) AND col(name(Longitude; 0))",
                "expected": [0],
            },
        }
    },
}


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
