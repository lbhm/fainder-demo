import pytest
from lark import UnexpectedInput

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
            "pp(0.5;ge;20.0)",
            "percentile(0.5;ge;20.0)",
        ]
    },
    "combined": {
        "queries": [
            "kw(test) AND pp(0.5;ge;20.0)",
            "keyword(hello) OR percentile(0.5;ge;20.0)",
            "kw(test) XOR pp(0.5;ge;20.0)",
        ]
    },
    "nested": {
        "queries": [
            "(kw(test) AND pp(0.5;ge;20.0)) OR keyword(other)",
            "(keyword(hello) OR kw(world)) AND pp(0.5;ge;20.0)",
        ]
    },
    "not_operations": {
        "queries": [
            "NOT kw(test)",
            "NOT pp(0.5;ge;20.0)",
            "NOT (kw(test) AND pp(0.5;ge;20.0))",
        ]
    },
    "optional_whitespaces": {
        "queries": [
            "kw(test) AND pp (0.5;ge;20.0)",
            "kw(test) AND pp (0.5;ge;20.0)",
            "keyword (test) AND pp  (0.5;ge;20.0)",
            "keyword(test)ANDpp(0.5;ge;20.0)",
        ]
    },
    "column_operator": {
        "queries": [
            "col(test; 0)",
            "column(hello; 1)",
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
}


@pytest.mark.parametrize(
    ("category", "query"),
    [(cat, q) for cat, data in VALID_TEST_CASES.items() for q in data["queries"]],
)
def test_query_evaluation_success(category: str, query: str, evaluator: QueryEvaluator) -> None:
    r = evaluator.parse(query)
    assert not isinstance(r, Exception)


@pytest.mark.parametrize(
    ("category", "query"),
    [(cat, q) for cat, data in INVALID_TEST_CASES.items() for q in data["queries"]],
)
def test_query_evaluation_fail(category: str, query: str, evaluator: QueryEvaluator) -> None:
    with pytest.raises((UnexpectedInput, SyntaxError)):
        evaluator.parse(query)
