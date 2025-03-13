from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from lark import ParseTree, Token, Tree, Visitor
from loguru import logger

if TYPE_CHECKING:
    from lark.tree import Branch

"""
Costs for each operator in the query tree. Currently, we define operator costs as a hand-picked
magic number. In the future, we may want to use a more sophisticated cost model.
"""
LEAF_COSTS = {
    "keyword_op": 1,
    "percentile_op": 2,
    "name_op": 1,
}
NODE_COSTS = {
    "col_op": 1,
    "negation": 0,
}


class OptimizationRule(ABC):
    """
    An optimization rule that can be applied to a ParseTree.
    """

    @abstractmethod
    def apply(self, tree: ParseTree) -> None:
        """
        Optimizes the given ParseTree in-place using this rule.
        """


class Optimizer:
    """
    This class is a wrapper around individual optimization techniques that operate on a ParseTree.

    Currently, we support the following optimization techniques:
    - Cost-based sorting of sibling operators
    - Keyword merging

    Planned optimizations include:
    - Pre-filtering for conjuctions based on intermediate results
    """

    def __init__(
        self,
        cost_sorting: bool = True,
        keyword_merging: bool = True,
        intermediate_filtering: bool = False,
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
        if intermediate_filtering:
            logger.warning("Intermediate filtering not yet implemented")
            self.opt_rules.append(ParentAnnotator())

    def optimize(self, tree: ParseTree) -> ParseTree:
        """
        Optimizes the given ParseTree in-place using a sequence of optimization techniques.
        """
        for rule in self.opt_rules:
            rule.apply(tree)
        return tree


class QuoteRemover(Visitor[Token], OptimizationRule):
    """
    This visitor removes quotes from all string tokens in the tree.

    This is a hack and should be removed once we optimize our DQL grammar.
    """

    def __default__(self, tree: ParseTree) -> ParseTree:
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


class ParentAnnotator(Visitor[Token], OptimizationRule):
    """
    This visitor annotates each node with its parent node's operator type.
    """

    def __default__(self, tree: ParseTree) -> ParseTree:
        for subtree in tree.children:
            if isinstance(subtree, Tree):
                if not hasattr(subtree, "parent"):
                    subtree.parent = tree.data  # type: ignore
                else:
                    raise ValueError(f"Parent of node {subtree} already set")

        return tree

    def apply(self, tree: ParseTree) -> None:
        self.visit(tree)


class CostSorter(Visitor[Token], OptimizationRule):
    """
    This visitor annotates each node with a cost value and sorts the children of each node by cost.
    """

    def __default__(self, tree: ParseTree) -> ParseTree:
        if tree.data in LEAF_COSTS:
            # If the node is a leaf node, set its cost and return
            tree.cost = LEAF_COSTS[tree.data]  # type: ignore
            return tree

        # Compute the cost of the current node
        cost = NODE_COSTS.get(tree.data, 0)
        cost += sum(
            getattr(child, "cost", 0) for child in tree.children if isinstance(child, Tree)
        )

        # Sort children by cost
        logger.trace(f"Before sorting: {tree.children}")
        tree.children.sort(key=lambda x: getattr(x, "cost", 0))
        logger.trace(f"After sorting: {tree.children}")

        # Store the cost on the tree node
        tree.cost = cost  # type: ignore

        return tree

    def apply(self, tree: ParseTree) -> None:
        self.visit(tree)


class MergeKeywords(Visitor[Token], OptimizationRule):
    """
    This transformer merges sibling keyword queries into a single query string.
    """

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
        if len(tree.children) < 2:
            raise ValueError("Junction must have at least two items")

        keyword_ops: list[ParseTree] = []
        other_ops: list[ParseTree] = []

        one_positive_kw_op = False
        for child in tree.children:
            if isinstance(child, Token):
                raise ValueError("Junction children must be trees")
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
        if len(keyword_ops) < 2 or one_positive_kw_op is False:
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
            raise ValueError("Negation must have a token child")

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
