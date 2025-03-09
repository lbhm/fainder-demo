from typing import TypedDict

from lark import ParseTree, Token, Tree


class OptimizerCase(TypedDict):
    input_tree: ParseTree
    kw_merging: ParseTree
    cost_sorting: ParseTree
    all_rules: ParseTree


OPTIMIZER_CASES: dict[str, OptimizerCase] = {
    "only_one_kw": {
        "input_tree": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")])],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")])],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")])],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")])],
        ),
    },
    "multiple_kws_with_and": {
        "input_tree": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'france'")]),
                    ],
                )
            ],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "(germany) AND (france)")])],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "(germany) AND (france)")])],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "france")]),
                    ],
                )
            ],
        ),
    },
    "multiple_kws_with_or": {
        "input_tree": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "disjunction"),
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'france'")]),
                    ],
                )
            ],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "(germany) OR (france)")])],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "(germany) OR (france)")])],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "disjunction"),
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "france")]),
                    ],
                )
            ],
        ),
    },
    "multiple_kws_with_not_and": {
        "input_tree": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(
                            Token("RULE", "negation"),
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                            ],
                        ),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'france'")]),
                    ],
                )
            ],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "-(germany) AND (france)")])],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [Tree(Token("RULE", "keyword_op"), [Token("STRING", "-(germany) AND (france)")])],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(
                            Token("RULE", "negation"),
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")]),
                            ],
                        ),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "france")]),
                    ],
                )
            ],
        ),
    },
    "multiple_kws_with_and_or": {
        "input_tree": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "disjunction"),
                    [
                        Tree(
                            Token("RULE", "conjunction"),
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "'france'")]),
                            ],
                        ),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'spain'")]),
                    ],
                )
            ],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "keyword_op"),
                    [Token("STRING", "((germany) AND (france)) OR (spain)")],
                )
            ],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "keyword_op"),
                    [Token("STRING", "(spain) OR ((germany) AND (france))")],
                )
            ],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "disjunction"),
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "spain")]),
                        Tree(
                            Token("RULE", "conjunction"),
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")]),
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "france")]),
                            ],
                        ),
                    ],
                )
            ],
        ),
    },
    "nested_and_or_not": {
        # KW("a") OR KW("b") AND COL(NAME("x";0)) OR KW("c") OR NOT(KW("d")) AND
        # NOT(COL(NAME("y";0))) AND NOT(NOT(KW("e"))) AND KW("f")
        "input_tree": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "disjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", '"a"')]),
                        Tree(
                            "conjunction",
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", '"b"')]),
                                Tree(
                                    Token("RULE", "col_op"),
                                    [
                                        Tree(
                                            Token("RULE", "name_op"),
                                            [Token("STRING", '"x"'), Token("INT", "0")],
                                        )
                                    ],
                                ),
                            ],
                        ),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", '"c"')]),
                        Tree(
                            "conjunction",
                            [
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            Token("RULE", "keyword_op"),
                                            [Token("STRING", '"d"')],
                                        )
                                    ],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            Token("RULE", "col_op"),
                                            [
                                                Tree(
                                                    Token("RULE", "name_op"),
                                                    [
                                                        Token("STRING", '"y"'),
                                                        Token("INT", "0"),
                                                    ],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            "negation",
                                            [
                                                Tree(
                                                    Token("RULE", "keyword_op"),
                                                    [Token("STRING", '"e"')],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                                Tree(
                                    Token("RULE", "keyword_op"),
                                    [Token("STRING", '"f"')],
                                ),
                            ],
                        ),
                    ],
                )
            ],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "disjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "(a) OR (c)")]),
                        Tree(
                            "conjunction",
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "b")]),
                                Tree(
                                    Token("RULE", "col_op"),
                                    [
                                        Tree(
                                            Token("RULE", "name_op"),
                                            [Token("STRING", "x"), Token("INT", "0")],
                                        )
                                    ],
                                ),
                            ],
                        ),
                        Tree(
                            "conjunction",
                            [
                                Tree(
                                    Token("RULE", "keyword_op"),
                                    [Token("STRING", "-(d) AND (f)")],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            Token("RULE", "col_op"),
                                            [
                                                Tree(
                                                    Token("RULE", "name_op"),
                                                    [
                                                        Token("STRING", "y"),
                                                        Token("INT", "0"),
                                                    ],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            "negation",
                                            [
                                                Tree(
                                                    Token("RULE", "keyword_op"),
                                                    [Token("STRING", "e")],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            ],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "disjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "(a) OR (c)")]),
                        Tree(
                            "conjunction",
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "b")]),
                                Tree(
                                    Token("RULE", "col_op"),
                                    [
                                        Tree(
                                            Token("RULE", "name_op"),
                                            [Token("STRING", "x"), Token("INT", "0")],
                                        )
                                    ],
                                ),
                            ],
                        ),
                        Tree(
                            "conjunction",
                            [
                                Tree(
                                    Token("RULE", "keyword_op"),
                                    [Token("STRING", "-(d) AND (f)")],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            "negation",
                                            [
                                                Tree(
                                                    Token("RULE", "keyword_op"),
                                                    [Token("STRING", "e")],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            Token("RULE", "col_op"),
                                            [
                                                Tree(
                                                    Token("RULE", "name_op"),
                                                    [
                                                        Token("STRING", "y"),
                                                        Token("INT", "0"),
                                                    ],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            ],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "disjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "a")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "c")]),
                        Tree(
                            "conjunction",
                            [
                                Tree(Token("RULE", "keyword_op"), [Token("STRING", "b")]),
                                Tree(
                                    Token("RULE", "col_op"),
                                    [
                                        Tree(
                                            Token("RULE", "name_op"),
                                            [Token("STRING", "x"), Token("INT", "0")],
                                        )
                                    ],
                                ),
                            ],
                        ),
                        Tree(
                            "conjunction",
                            [
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            Token("RULE", "keyword_op"),
                                            [Token("STRING", "d")],
                                        )
                                    ],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            "negation",
                                            [
                                                Tree(
                                                    Token("RULE", "keyword_op"),
                                                    [Token("STRING", "e")],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                                Tree(
                                    Token("RULE", "keyword_op"),
                                    [Token("STRING", "f")],
                                ),
                                Tree(
                                    "negation",
                                    [
                                        Tree(
                                            Token("RULE", "col_op"),
                                            [
                                                Tree(
                                                    Token("RULE", "name_op"),
                                                    [
                                                        Token("STRING", "y"),
                                                        Token("INT", "0"),
                                                    ],
                                                )
                                            ],
                                        )
                                    ],
                                ),
                            ],
                        ),
                    ],
                )
            ],
        ),
    },
    "multiple_kws_with_col_in_between_and": {
        "input_tree": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "conjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'france'")]),
                    ],
                )
            ],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(
                            Token("RULE", "keyword_op"),
                            [Token("STRING", "(germany) AND (france)")],
                        ),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                    ],
                )
            ],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(
                            Token("RULE", "keyword_op"),
                            [Token("STRING", "(germany) AND (france)")],
                        ),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                    ],
                )
            ],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "conjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "france")]),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                    ],
                )
            ],
        ),
    },
    "multiple_kws_with_col_at_the_end_and": {
        "input_tree": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "conjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "'france'")]),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                    ],
                )
            ],
        ),
        "kw_merging": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(
                            Token("RULE", "keyword_op"),
                            [Token("STRING", "(germany) AND (france)")],
                        ),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                    ],
                )
            ],
        ),
        "all_rules": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    Token("RULE", "conjunction"),
                    [
                        Tree(
                            Token("RULE", "keyword_op"),
                            [Token("STRING", "(germany) AND (france)")],
                        ),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                    ],
                )
            ],
        ),
        "cost_sorting": Tree(
            Token("RULE", "query"),
            [
                Tree(
                    "conjunction",
                    [
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "germany")]),
                        Tree(Token("RULE", "keyword_op"), [Token("STRING", "france")]),
                        Tree(
                            Token("RULE", "col_op"),
                            [
                                Tree(
                                    Token("RULE", "percentile_op"),
                                    [
                                        Token("FLOAT", "0.5"),
                                        Token("COMPARISON", "ge"),
                                        Token("SIGNED_NUMBER", "50"),
                                    ],
                                )
                            ],
                        ),
                    ],
                )
            ],
        ),
    },
}
