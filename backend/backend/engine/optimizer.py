from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np
from lark import ParseTree, Token, Tree, Visitor
from loguru import logger

from backend.config import ExecutorType
from backend.engine.constants import COEF_LOG_THRESHOLD, COEF_PERCENTILE, INTERCEPT

if TYPE_CHECKING:
    from lark.tree import Branch

"""
Costs for each operator in the query tree. Currently, we define operator costs as a hand-picked
magic number. In the future, we may want to use a more sophisticated cost model.
"""
LEAF_COSTS = {"keyword_op": 1, "percentile_op": 2, "name_op": 1}
NODE_COSTS = {"col_op": 1, "negation": 0}


class OptimizationRule(ABC):
    """An optimization rule that can be applied to a ParseTree."""

    @abstractmethod
    def apply(self, tree: ParseTree) -> None:
        """Optimizes the given ParseTree in-place using this rule."""


class Optimizer:
    """This class is a wrapper around individual optimization rules that operate on a ParseTree.

    Currently, we support the following optimization techniques:
    - Cost-based sorting of sibling operators
    - Keyword merging
    """

    def __init__(
        self,
        cost_sorting: bool = True,
        keyword_merging: bool = True,
        split_up_junctions: bool = True,
    ) -> None:
        self.opt_rules: list[OptimizationRule] = [QuoteRemover()]
        if cost_sorting:
            self.opt_rules.append(CostSorter())
        if keyword_merging:
            if cost_sorting is False:
                logger.warning(
                    "Using keyword merging without cost sorting may lead to suboptimal results"
                )
            self.opt_rules.append(MergeKeywords())
        if split_up_junctions:
            if cost_sorting is False or keyword_merging is False:
                logger.warning(
                    "Using split up junctions without cost sorting"
                    " or keyword merging may lead to suboptimal results"
                )
            self.opt_rules.append(SplitUpJunctions())

    def optimize(self, tree: ParseTree) -> ParseTree:
        """Optimizes the given ParseTree in-place using a sequence of optimization techniques."""
        logger.debug(f"Unoptimized tree: {tree.pretty()}")
        logger.trace(f"Unoptimized tree data: {tree}")
        for rule in self.opt_rules:
            rule.apply(tree)
        logger.debug(f"Optimized tree: {tree.pretty()}")
        logger.trace(f"Optimized tree data: {tree}")
        return tree


def create_optimizer(
    executor_type: ExecutorType,
    cost_sorting: bool = True,
    keyword_merging: bool = True,
    split_up_junctions: bool = True,
) -> Optimizer:
    """Creates an optimizer based on the executor type."""
    if executor_type == ExecutorType.PREFILTERING:
        return Optimizer(cost_sorting=True, keyword_merging=True, split_up_junctions=True)
    # TODO: Handle other executor types properly
    return Optimizer(
        cost_sorting=cost_sorting,
        keyword_merging=keyword_merging,
        split_up_junctions=split_up_junctions,
    )


class QuoteRemover(Visitor[Token], OptimizationRule):
    """This visitor removes quotes from all string tokens in the tree.

    This is a hack and should be removed once we optimize our DQL grammar.
    """

    def __default__(self, tree: ParseTree) -> ParseTree:  # noqa: PLW3201
        children: list[Branch[Token]] = []
        for subtree in tree.children:
            if isinstance(subtree, Token) and subtree.type == "STRING":
                children.append(Token("STRING", subtree.value[1:-1]))
            else:
                children.append(subtree)
        tree.children = children
        return tree

    def apply(self, tree: ParseTree) -> None:
        self.visit(tree)


class SplitUpJunctions(Visitor[Token], OptimizationRule):
    """This vistor splits up junctions with more than two terms into Rules with two terms."""

    def __default__(self, tree: ParseTree) -> ParseTree:  # noqa: PLW3201
        return tree

    def apply(self, tree: ParseTree) -> None:
        self.visit(tree)

    def disjunction(self, tree: ParseTree) -> ParseTree:
        if len(tree.children) > 2:  # noqa: PLR2004
            # Split the disjunction into multiple rules
            new_children: list[Token | Tree[Token]] = []
            for i in range(0, len(tree.children), 2):
                if i + 1 < len(tree.children):
                    new_children.append(
                        Tree(
                            Token("RULE", "disjunction"), [tree.children[i], tree.children[i + 1]]
                        )
                    )
                else:
                    new_children.append(tree.children[i])
            tree.children = new_children
        return tree

    def conjunction(self, tree: ParseTree) -> ParseTree:
        if len(tree.children) > 2:  # noqa: PLR2004
            # Split the conjunction into multiple rules
            new_children: list[Token | Tree[Token]] = []
            for i in range(0, len(tree.children), 2):
                if i + 1 < len(tree.children):
                    new_children.append(
                        Tree(
                            Token("RULE", "conjunction"), [tree.children[i], tree.children[i + 1]]
                        )
                    )
                else:
                    new_children.append(tree.children[i])
            tree.children = new_children
        return tree


class ParentAnnotator(Visitor[Token], OptimizationRule):
    """This visitor annotates each node with its parent node's operator type."""

    def __default__(self, tree: ParseTree) -> ParseTree:  # noqa: PLW3201
        for subtree in tree.children:
            if isinstance(subtree, Tree):
                if not hasattr(subtree, "parent"):
                    subtree.parent = tree.data  # type: ignore[attr-defined]
                else:
                    raise ValueError(f"Parent of node {subtree} already set")

        return tree

    def apply(self, tree: ParseTree) -> None:
        self.visit_topdown(tree)


class CostSorter(Visitor[Token], OptimizationRule):
    """This visitor annotates each node with a cost value and sorts children by cost."""

    def __default__(self, tree: ParseTree) -> ParseTree:  # noqa: PLW3201
        if tree.data in LEAF_COSTS:
            # If the node is a leaf node, set its cost and return
            if tree.data == "percentile_op":
                if (
                    not isinstance(tree.children[2], Token)
                    or not isinstance(tree.children[0], Token)
                    or not isinstance(tree.children[1], Token)
                ):
                    raise ValueError("Expected Token children for percentile_op")
                threshold = float(tree.children[2].value)
                percentile = float(tree.children[0].value)
                comparison = tree.children[1].value
                tree.cost = self.estimate_result_size_for_pp(threshold, percentile, comparison)  # type: ignore[attr-defined]
                return tree
            tree.cost = LEAF_COSTS[tree.data]  # type: ignore[attr-defined]
            return tree

        # Compute the cost of the current node
        cost = NODE_COSTS.get(tree.data, 0)
        cost += sum(
            getattr(child, "cost", 0) for child in tree.children if isinstance(child, Tree)
        )

        # Sort children by cost
        tree.children.sort(key=lambda x: getattr(x, "cost", 0))

        # Store the cost on the tree node
        tree.cost = cost  # type: ignore[attr-defined]

        return tree

    def apply(self, tree: ParseTree) -> None:
        self.visit(tree)

    def estimate_result_size_for_pp(
        self, threshold: float, percentile: float, comparison: str
    ) -> float:
        """Estimate the number of results using a regression model.

        Parameters:
        - threshold (float): the threshold value (must be > 0)
        - percentile (float): the predicate percentile, between 0 and 1
        - comparison (str): the comparison operator, "le", "lt", "ge", "gt"

        Returns:
        - Estimated result size (float)
        """
        if comparison not in {"le", "lt", "ge", "gt"}:
            raise ValueError("Comparison must be one of 'le', 'lt', 'ge', 'gt'.")
        if comparison in {"gt", "ge"}:
            percentile = 1 - percentile  # Invert percentile for gt/ge comparisons

        # Formular for the regression model for le
        if threshold <= 0:
            raise ValueError("Threshold must be positive.")
        if not (0 <= percentile <= 1):
            raise ValueError("Percentile must be between 0 and 1.")

        log_thresh = np.log10(threshold)
        return INTERCEPT + COEF_LOG_THRESHOLD * log_thresh + COEF_PERCENTILE * percentile


class MergeKeywords(Visitor[Token], OptimizationRule):
    """This transformer merges sibling keyword queries into a single query string."""

    def __init__(self) -> None:
        super().__init__()

    def apply(self, tree: ParseTree) -> None:
        self.visit(tree)

    def conjunction(self, tree: ParseTree) -> None:
        self._merge_terms(tree, "AND")

    def disjunction(self, tree: ParseTree) -> None:
        self._merge_terms(tree, "OR")

    def _merge_terms(self, tree: ParseTree, operator: str) -> None:
        """Merges consecutive keyword terms in a list of parse trees."""
        if len(tree.children) < 2:  # noqa: PLR2004
            raise ValueError("Junction must have at least two items")

        keyword_ops: list[ParseTree] = []
        other_ops: list[ParseTree] = []

        one_positive_kw_op = False
        for child in tree.children:
            if isinstance(child, Token):
                raise TypeError("Junction children must be trees, not tokens.")
            if child.data == "keyword_op":
                keyword_ops.append(child)
                one_positive_kw_op = True
            elif child.data == "negation":
                # We can only negate keywords if they appear together with other keywords since
                # tantivy does not support stand-alone negation queries
                negation_child = child.children[0]
                if isinstance(negation_child, Tree) and negation_child.data == "keyword_op":
                    keyword_ops.append(self._negate_keyword(negation_child))
                else:
                    other_ops.append(child)
            else:
                other_ops.append(child)

        # Nothing to merge for less than two keyword operators
        if len(keyword_ops) < 2 or one_positive_kw_op is False:  # noqa: PLR2004
            return

        merged_string = self._merge_keyword_string(keyword_ops, operator)

        if len(other_ops) == 0:
            tree.data = Token("RULE", "keyword_op")
            tree.children = [Token("STRING", merged_string)]
        else:
            merged_op = Tree(Token("RULE", "keyword_op"), [Token("STRING", merged_string)])

            # NOTE: We assume that keyword ops are cheaper than other ops and always put them first
            tree.children = [merged_op, *other_ops]

    def _negate_keyword(self, tree: ParseTree) -> ParseTree:
        """Negates a keyword operator."""
        if len(tree.children) != 1:
            raise ValueError("Negation must have exactly one child")

        child = tree.children[0]
        if not isinstance(child, Token):
            raise TypeError("Negation must have a token child")

        return Tree(Token("RULE", "keyword_op"), [Token("STRING", f"-({child})")])

    def _merge_keyword_string(self, keyword_ops: list[ParseTree], operator: str) -> str:
        """Merges a list of keyword operators into a single string."""
        keyword_strings: list[str] = []
        for keyword_op in keyword_ops:
            child = keyword_op.children[0]
            if isinstance(child, Token):
                if child.startswith("-"):
                    # Negations must not be wrapped in parentheses again
                    keyword_strings.append(child)
                else:
                    keyword_strings.append(f"({child})")
        return f" {operator} ".join(keyword_strings)
