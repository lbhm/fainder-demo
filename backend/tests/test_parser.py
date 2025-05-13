import time

import pytest
from lark import UnexpectedCharacters, UnexpectedEOF, UnexpectedInput
from loguru import logger

from backend.engine import Parser

from .assets.test_cases_executor import EXECUTOR_CASES, INVALID_QUERIES, ExecutorCase


@pytest.mark.parametrize(
    ("category", "test_name", "test_case"),
    [(cat, name, case) for cat, cases in EXECUTOR_CASES.items() for name, case in cases.items()],
)
def test_parse(category: str, test_name: str, test_case: ExecutorCase, parser: Parser) -> None:
    start_time = time.perf_counter()
    tree = parser.parse(test_case["query"])
    duration = time.perf_counter() - start_time

    validation_log: dict[str, str | float] = {
        "test_type": "parser",
        "category": category,
        "test_name": test_name,
        "query": test_case["query"],
        "parse_tree": tree.pretty(),
        "parse_time": duration,
    }
    logger.info(validation_log)

    assert tree == test_case["parse_tree"]


@pytest.mark.parametrize(
    ("category", "query"),
    [(cat, q) for cat, data in INVALID_QUERIES.items() for q in data["queries"]],
)
def test_query_evaluation_fail(category: str, query: str, parser: Parser) -> None:
    with pytest.raises((UnexpectedInput, SyntaxError, UnexpectedCharacters, UnexpectedEOF)):
        parser.parse(query)
