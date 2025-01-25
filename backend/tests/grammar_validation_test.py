import pytest
from lark import UnexpectedCharacters, UnexpectedInput, UnexpectedEOF
import time
from loguru import logger

from backend.query_evaluator import QueryEvaluator

VALID_TEST_CASES = {
    "basic_keyword": {
        "queries": [
            "keyword(test)",
            "kw(hello world)",
        ]
    },
    "basic_percentile": {
        "queries": [
            "col(pp(0.5;ge;20.0))",
            "col(percentile(0.5;ge;20.0))",
        ]
    },
    "combined": {
        "queries": [
            "kw(test) AND col(pp(0.5;ge;20.0))",
            "keyword(hello) OR col(percentile(0.5;ge;20.0))",
            "kw(test) XOR col(pp(0.5;ge;20.0))",
        ]
    },
    "nested": {
        "queries": [
            "(kw(test) AND col(pp(0.5;ge;20.0))) OR keyword(other)",
            "(keyword(hello) OR kw(world)) AND col(pp(0.5;ge;20.0))",
        ]
    },
    "not_operations": {
        "queries": [
            "NOT kw(test)",
            "NOT col(pp(0.5;ge;20.0))",
            "NOT (kw(test) AND col(pp(0.5;ge;20.0)))",
        ]
    },
    "optional_whitespaces": {
        "queries": [
            "kw(test) AND col(pp (0.5;ge;20.0))",
            "kw(test) AND col(pp (0.5;ge;20.0))",
            "keyword (test) AND col(pp  (0.5;ge;20.0))",
            "keyword(test)ANDcol(pp(0.5;ge;20.0))",
        ]
    },
    "column_operator": {
        "queries": [
            "col(name(test; 0))",
            "column(name(hello; 1))",
            "col(pp(0.5;ge;20.0))",
            "col(name(test; 0) AND pp(0.5;ge;20.0))",
            "col(NOT name(test; 0))",
            "col((name(test; 0) AND pp(0.5;ge;20.0)) OR name(other; 1))",
            "col(NOT (name(test; 0) AND pp(0.5;ge;20.0)))",
        ]
    },
}

INVALID_TEST_CASES = {
    "invalid_syntax": {
        "queries": [
            "keyword()",
            "pp()",
            "kw()",
        ]
    },
    "missing_parentheses": {
        "queries": [
            "keyword(test",
            "pp(0.5;ge;20.0",
        ]
    },
    "invalid_operators": {
        "queries": [
            "kw(test) INVALID pp(0.5;ge;20.0)",
            "kw(test) AND OR pp(0.5;ge;20.0)",
        ]
    },
    "incomplete_expressions": {
        "queries": [
            "kw(test) AND",
            "NOT",
        ]
    },
    "invalid_percentile": {
        "queries": [
            "pp(a;ge;20.0)",
            "pp(0.5;invalid;20.0)",
            "pp(0.5;ge;abc)",
        ]
    },
    "malformed_compound": {
        "queries": [
            "(kw(test) AND",
            "kw(test)) OR pp(0.5;ge;20.0)",
            "AND kw(test)",
        ]
    },
    "invalid_column": {
        "queries": [
            "col(keyword(test))",  # Keywords not allowed in column expressions
            "col(kw(test))",  # Keywords not allowed in column expressions
            "col()",  # Empty column expression
            "col(name(test))",  # Missing k parameter
            "col(name(; 0))",  # Missing name parameter
        ]
    },
}


@pytest.mark.parametrize(
    ("category", "query"),
    [(cat, q) for cat, data in VALID_TEST_CASES.items() for q in data["queries"]],
)
def test_query_evaluation_success(category: str, query: str, evaluator: QueryEvaluator) -> None:
    start_time = time.perf_counter()
    r = evaluator.parse(query)
    duration = time.perf_counter() - start_time
    
    validation_log = {
        "type": "valid",
        "category": category,
        "query": query,
        "parse_time": duration
    }
    
    logger.info("VALIDATION_DATA: " + str(validation_log))
    assert not isinstance(r, Exception)

@pytest.mark.parametrize(
    ("category", "query"),
    [(cat, q) for cat, data in INVALID_TEST_CASES.items() for q in data["queries"]],
)
def test_query_evaluation_fail(category: str, query: str, evaluator: QueryEvaluator) -> None:
    with pytest.raises((UnexpectedInput, SyntaxError, UnexpectedCharacters, UnexpectedEOF)):
        evaluator.parse(query)