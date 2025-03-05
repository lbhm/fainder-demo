import time

import pytest
from lark import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput
from loguru import logger

from backend.query_evaluator import QueryEvaluator

from .assets.test_cases import INVALID_TEST_CASES, TEST_CASES, Case


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [(cat, name, case) for cat, cases in TEST_CASES.items() for name, case in cases.items()],
)
def test_query_evaluation_success(
    category: str, test_name: str, test_case: Case, evaluator: QueryEvaluator
) -> None:
    query = test_case["query"]
    parse_tree = test_case["parse_tree"]
    start_time = time.perf_counter()
    tree = evaluator.parse(query)
    duration = time.perf_counter() - start_time

    validation_log = {
        "test_type": "parser",
        "category": category,
        "test_name": test_name,
        "query": query,
        "parse_tree": tree.pretty(),
        "parse_time": duration,
    }
    logger.info(validation_log)

    assert not isinstance(tree, Exception)
    assert tree == parse_tree


@pytest.mark.parametrize(
    ("category", "query"),
    [(cat, q) for cat, data in INVALID_TEST_CASES.items() for q in data["queries"]],
)
def test_query_evaluation_fail(category: str, query: str, evaluator: QueryEvaluator) -> None:
    with pytest.raises((UnexpectedInput, SyntaxError, UnexpectedCharacters, UnexpectedEOF)):
        evaluator.parse(query)
