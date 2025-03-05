from lark import ParseTree, Token, Tree, Visitor


class ParentAnnotator(Visitor[Token]):
    def __default__(self, tree: ParseTree) -> ParseTree:
        for subtree in tree.children:
            if isinstance(subtree, Tree):
                assert not hasattr(subtree, "parent")
                subtree.parent = tree.data  # pyright: ignore

        return tree
