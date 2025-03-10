import pytest

from backend.engine import Engine
from backend.engine.optimizer import Optimizer

from .assets.test_cases_higlighter import TEST_CASES_HIGHLIGHTER, CaseHighlighter


@pytest.mark.parametrize(
    ("test_name", "test_case"),
    [(name, case) for name, case in TEST_CASES_HIGHLIGHTER.items()],
)
def test_highlighter(test_name: str, test_case: CaseHighlighter, engine: Engine) -> None:
    engine.optimizer = Optimizer(
        cost_sorting=False, keyword_merging=False, intermediate_filtering=False
    )
    _, highlights = engine.execute(
        test_case["query"],
        enable_highlighting=True,
        enable_filtering=False,
    )

    assert highlights == test_case["expected"]
