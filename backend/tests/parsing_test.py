import time
from typing import Any

import pytest
from lark import ParseTree, UnexpectedCharacters, UnexpectedEOF, UnexpectedInput
from loguru import logger

from backend.query_evaluator import QueryEvaluator
from tests.testing_data import INVALID_TEST_CASES, TEST_CASES


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [
        (cat, name, case)
        for cat, data in TEST_CASES.items()
        for name, case in data["queries"].items()
    ],
)
def test_query_evaluation_success(
    category: str, test_name: str, test_case: dict[str, Any], evaluator: QueryEvaluator
) -> None:
    query = test_case["query"]
    parse_tree: ParseTree | None = test_case.get("parse_tree")
    assert parse_tree is not None
    start_time = time.perf_counter()
    tree = evaluator.parse(query)
    duration = time.perf_counter() - start_time

    validation_log = {
        "type": "valid",
        "category": category,
        "query": query,
        "parse_tree": tree.pretty(),
        "parse_time": duration,
    }

    logger.info("VALIDATION_DATA: " + str(validation_log))
    assert not isinstance(tree, Exception)

    logger.debug("Expected parse tree: ")
    logger.debug(parse_tree.pretty())
    logger.debug("Actual parse tree: ")
    logger.debug(tree.pretty())
    assert tree == parse_tree


@pytest.mark.parametrize(
    ("category", "query"),
    [(cat, q) for cat, data in INVALID_TEST_CASES.items() for q in data["queries"]],
)
def test_query_evaluation_fail(category: str, query: str, evaluator: QueryEvaluator) -> None:
    with pytest.raises((UnexpectedInput, SyntaxError, UnexpectedCharacters, UnexpectedEOF)):
        evaluator.parse(query)
