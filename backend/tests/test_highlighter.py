import pytest

from backend.query_evaluator import QueryEvaluator

from .assets.test_cases_higlighter import TEST_CASES_HIGHLIGHTER, CaseHighlighter


@pytest.mark.parametrize(
    ("test_name", "test_case"),
    [(name, case) for name, case in TEST_CASES_HIGHLIGHTER.items()],
)
def test_highlighter(
    test_name: str, test_case: CaseHighlighter, evaluator: QueryEvaluator
) -> None:
    _, highlights = evaluator.execute(
        test_case["query"],
        enable_highlighting=True,
        enable_filtering=False,
        enable_kw_merge=False,
        enable_cost_sorting=False,
    )

    assert highlights == test_case["expected"]
