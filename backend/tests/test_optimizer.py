from copy import deepcopy

import pytest

from backend.engine import Optimizer

from .assets.test_cases_optimizer import OPTIMIZER_CASES, OptimizerCase


@pytest.mark.parametrize(
    ("test_name", "test_case"), [(name, case) for name, case in OPTIMIZER_CASES.items()]
)
def test_cost_sorting(test_name: str, test_case: OptimizerCase) -> None:
    optimizer = Optimizer(cost_sorting=True, keyword_merging=False, split_up_junctions=False)
    plan = deepcopy(test_case["input_tree"])

    optimized_plan = optimizer.optimize(plan)
    assert test_case["cost_sorting"] == optimized_plan


@pytest.mark.parametrize(
    ("test_name", "test_case"), [(name, case) for name, case in OPTIMIZER_CASES.items()]
)
def test_kw_merging(test_name: str, test_case: OptimizerCase) -> None:
    optimizer = Optimizer(cost_sorting=False, keyword_merging=True, split_up_junctions=False)
    plan = deepcopy(test_case["input_tree"])

    assert test_case["kw_merging"] == optimizer.optimize(plan)


@pytest.mark.parametrize(
    ("test_name", "test_case"), [(name, case) for name, case in OPTIMIZER_CASES.items()]
)
def test_all_rules(test_name: str, test_case: OptimizerCase) -> None:
    optimizer = Optimizer(cost_sorting=True, keyword_merging=True, split_up_junctions=True)
    plan = deepcopy(test_case["input_tree"])

    assert test_case["all_rules"] == optimizer.optimize(plan)
