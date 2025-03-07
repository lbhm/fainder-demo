from typing import TypedDict

from lark import ParseTree, Token, Tree


class ExecutorCase(TypedDict):
    query: str
    expected: list[int]
    parse_tree: ParseTree


EXECUTOR_CASES: dict[str, dict[str, ExecutorCase]] = {
    "basic_keyword": {
        "simple_keyword": {
            "query": "kw('germany')",
            "expected": [0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")])],
            ),
        },
        "simple_keyword_2": {
            "query": "kw('Avacado')",
            "expected": [1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'Avacado'")])],
            ),
        },
        "basic_query": {
            "query": 'kw("data")',
            "expected": [2, 1, 0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [Tree(Token("RULE", "keyword_op"), [Token("STRING", '"data"')])],
            ),
        },
    },
    "basic_percentile": {
        "simple_percentile": {
            "query": "col(pp(0.5;ge;2000))",
            "expected": [0, 1, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                Token("RULE", "percentile_op"),
                                [
                                    Token("FLOAT", "0.5"),
                                    Token("COMPARISON", "ge"),
                                    Token("SIGNED_NUMBER", "2000"),
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
        "high_percentile": {
            "query": "col(pp(0.9;ge;1000000))",
            "expected": [1, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                Token("RULE", "percentile_op"),
                                [
                                    Token("FLOAT", "0.9"),
                                    Token("COMPARISON", "ge"),
                                    Token("SIGNED_NUMBER", "1000000"),
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
        "very_high_percentile": {
            "query": "col(pp(0.99;ge;10000000))",
            "expected": [2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                Token("RULE", "percentile_op"),
                                [
                                    Token("FLOAT", "0.99"),
                                    Token("COMPARISON", "ge"),
                                    Token("SIGNED_NUMBER", "10000000"),
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
    },
    "NOT_operations": {
        "not_keyword": {
            "query": "NOT kw('germany')",
            "expected": [2, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "negation",
                        [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")])],
                    )
                ],
            ),
        },
        "not_percentile": {
            "query": "NOT col(pp(0.5;ge;2000))",
            "expected": [],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "negation",
                        [
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.5"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "2000"),
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
        "not_inside_percentile": {
            "query": "col(NOT pp(0.5;ge;2000))",
            "expected": [0, 1, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                "negation",
                                [
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.5"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "2000"),
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
    },
    "advanced_keyword_queries": {
        "field_specific_keyword": {
            "query": "kw('alternateName:(Weather)')",
            "expected": [0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "keyword_op"),
                        [Token("STRING", "'alternateName:(Weather)'")],
                    )
                ],
            ),
        },
        "field_specific_keyword_or": {
            "query": "kw('alternateName:(Weather) OR data')",
            "expected": [0, 2, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "keyword_op"),
                        [Token("STRING", "'alternateName:(Weather) OR data'")],
                    )
                ],
            ),
        },
        "wildcard_search": {
            "query": "kw('data')",
            "expected": [2, 1, 0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'data'")])],
            ),
        },
        "advanced_query": {
            "query": "kw('data AND weather')",
            "expected": [0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'data AND weather'")])],
            ),
        },
        "advanced_query_2": {
            "query": "kw('weather OR Avocado')",
            "expected": [0, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'weather OR Avocado'")])],
            ),
        },
        "advanced_query_3": {
            "query": "kw('\"a movie\"')",
            "expected": [2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [Tree(Token("RULE", "keyword_op"), [Token("STRING", "'\"a movie\"'")])],
            ),
        },
        "or_query": {
            "query": "kw('TMDB OR weather OR Avocado')",
            "expected": [0, 1, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "keyword_op"),
                        [Token("STRING", "'TMDB OR weather OR Avocado'")],
                    )
                ],
            ),
        },
        "nested_query": {
            "query": "kw('data AND (weather OR Avocado)')",
            "expected": [0, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "keyword_op"),
                        [Token("STRING", "'data AND (weather OR Avocado)'")],
                    )
                ],
            ),
        },
        "nested_query_2": {
            "query": "kw('(data AND weather) OR Avocado')",
            "expected": [0, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "keyword_op"),
                        [Token("STRING", "'(data AND weather) OR Avocado'")],
                    )
                ],
            ),
        },
        "double_nested_query": {
            "query": "kw('(data AND weather) OR (Avocado AND data)')",
            "expected": [0, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "keyword_op"),
                        [Token("STRING", "'(data AND weather) OR (Avocado AND data)'")],
                    )
                ],
            ),
        },
    },
    "combined_operations": {
        "keyword_and_percentile": {
            "query": "kw('germany') AND col(pp(0.5;ge;20.0))",
            "expected": [0],
            "parse_tree": Tree(
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
                                            Token("SIGNED_NUMBER", "20.0"),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            ),
        },
        # NOTE: This test case is potentially interesting for the optimizer/reordering
        "high_percentile_and_keyword": {
            "query": "col(pp(0.9;ge;1000000)) AND kw('germany')",
            "expected": [],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "conjunction",
                        [
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.9"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "1000000"),
                                        ],
                                    )
                                ],
                            ),
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        ],
                    )
                ],
            ),
        },
        "high_percentile_or_keyword": {
            "query": "col(pp(0.9;ge;1000000)) OR kw('germany')",
            "expected": [0, 1, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "disjunction",
                        [
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.9"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "1000000"),
                                        ],
                                    )
                                ],
                            ),
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        ],
                    )
                ],
            ),
        },
    },
    "mutliple_operations": {  # test for correct order of operations
        "1": {
            "query": "NOT kw('germany') AND col(pp(0.99;ge;10000000)) OR kw('germany')",
            "expected": [0, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "disjunction",
                        [
                            Tree(
                                "conjunction",
                                [
                                    Tree(
                                        "negation",
                                        [
                                            Tree(
                                                Token("RULE", "keyword_op"),
                                                [Token("STRING", "'germany'")],
                                            )
                                        ],
                                    ),
                                    Tree(
                                        Token("RULE", "col_op"),
                                        [
                                            Tree(
                                                Token("RULE", "percentile_op"),
                                                [
                                                    Token("FLOAT", "0.99"),
                                                    Token("COMPARISON", "ge"),
                                                    Token("SIGNED_NUMBER", "10000000"),
                                                ],
                                            )
                                        ],
                                    ),
                                ],
                            ),
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        ],
                    )
                ],
            ),
        },
        "2": {
            "query": "NOT kw('germany') AND (col(pp(0.99;ge;10000000)) OR kw('germany'))",
            "expected": [2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "conjunction",
                        [
                            Tree(
                                "negation",
                                [
                                    Tree(
                                        Token("RULE", "keyword_op"),
                                        [Token("STRING", "'germany'")],
                                    )
                                ],
                            ),
                            Tree(
                                "disjunction",
                                [
                                    Tree(
                                        Token("RULE", "col_op"),
                                        [
                                            Tree(
                                                Token("RULE", "percentile_op"),
                                                [
                                                    Token("FLOAT", "0.99"),
                                                    Token("COMPARISON", "ge"),
                                                    Token("SIGNED_NUMBER", "10000000"),
                                                ],
                                            )
                                        ],
                                    ),
                                    Tree(
                                        Token("RULE", "keyword_op"),
                                        [Token("STRING", "'germany'")],
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            ),
        },
        "3": {
            "query": "(NOT kw('germany') AND col(pp(0.99;ge;10000000))) OR kw('germany')",
            "expected": [0, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "disjunction",
                        [
                            Tree(
                                "conjunction",
                                [
                                    Tree(
                                        "negation",
                                        [
                                            Tree(
                                                Token("RULE", "keyword_op"),
                                                [Token("STRING", "'germany'")],
                                            )
                                        ],
                                    ),
                                    Tree(
                                        Token("RULE", "col_op"),
                                        [
                                            Tree(
                                                Token("RULE", "percentile_op"),
                                                [
                                                    Token("FLOAT", "0.99"),
                                                    Token("COMPARISON", "ge"),
                                                    Token("SIGNED_NUMBER", "10000000"),
                                                ],
                                            )
                                        ],
                                    ),
                                ],
                            ),
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'germany'")]),
                        ],
                    )
                ],
            ),
        },
    },
    "syntax_variations": {
        "optional_whitespaces": {
            "query": "kw('data') AND col(pp (0.9;ge;1000000))",
            "expected": [2, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "conjunction",
                        [
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'data'")]),
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.9"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "1000000"),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            ),
        },
        "no_whitespaces": {
            "query": "kw('data')ANDcol(pp(0.9;ge;1000000))",
            "expected": [2, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "conjunction",
                        [
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'data'")]),
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.9"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "1000000"),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            ),
        },
        "case_insensitive": {
            "query": "kw('data')AND col(Pp(0.9;ge;1000000))",
            "expected": [2, 1],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "conjunction",
                        [
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'data'")]),
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.9"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "1000000"),
                                        ],
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            ),
        },
    },
    "column_operations": {
        "column_name": {
            "query": "col(name('Latitude'; 0))",
            "expected": [0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                Token("RULE", "name_op"),
                                [Token("STRING", "'Latitude'"), Token("INT", "0")],
                            )
                        ],
                    )
                ],
            ),
        },
        # TODO
        "percentile_with_identifer": {
            "query": "col(name('Latitude'; 0) AND pp(0.5;ge;50))",
            "expected": [],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                "conjunction",
                                [
                                    Tree(
                                        Token("RULE", "name_op"),
                                        [Token("STRING", "'Latitude'"), Token("INT", "0")],
                                    ),
                                    Tree(
                                        Token("RULE", "percentile_op"),
                                        [
                                            Token("FLOAT", "0.5"),
                                            Token("COMPARISON", "ge"),
                                            Token("SIGNED_NUMBER", "50"),
                                        ],
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
        # TODO
        "keyword_filter": {
            "query": "col(name('Latitude'; 0) AND pp(0.5;ge;50)) AND kw('data')",
            "expected": [0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "conjunction",
                        [
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        "conjunction",
                                        [
                                            Tree(
                                                Token("RULE", "name_op"),
                                                [
                                                    Token("STRING", "'Latitude'"),
                                                    Token("INT", "0"),
                                                ],
                                            ),
                                            Tree(
                                                Token("RULE", "percentile_op"),
                                                [
                                                    Token("FLOAT", "0.5"),
                                                    Token("COMPARISON", "ge"),
                                                    Token("SIGNED_NUMBER", "50"),
                                                ],
                                            ),
                                        ],
                                    )
                                ],
                            ),
                            Tree(Token("RULE", "keyword_op"), [Token("STRING", "'data'")]),
                        ],
                    )
                ],
            ),
        },
        "not_column": {
            "query": "NOT col(name('Latitude'; 0))",
            "expected": [1, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "negation",
                        [
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "name_op"),
                                        [Token("STRING", "'Latitude'"), Token("INT", "0")],
                                    )
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
        # TODO
        "complex_column": {
            "query": "col((name('Latitude'; 0) AND pp(0.5;ge;50)) OR name('Longitude'; 0))",
            "expected": [0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                "disjunction",
                                [
                                    Tree(
                                        "conjunction",
                                        [
                                            Tree(
                                                Token("RULE", "name_op"),
                                                [
                                                    Token("STRING", "'Latitude'"),
                                                    Token("INT", "0"),
                                                ],
                                            ),
                                            Tree(
                                                Token("RULE", "percentile_op"),
                                                [
                                                    Token("FLOAT", "0.5"),
                                                    Token("COMPARISON", "ge"),
                                                    Token("SIGNED_NUMBER", "50"),
                                                ],
                                            ),
                                        ],
                                    ),
                                    Tree(
                                        Token("RULE", "name_op"),
                                        [Token("STRING", "'Longitude'"), Token("INT", "0")],
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
        # TODO
        "not_complex_column": {
            "query": "NOT col((name('Latitude'; 0) AND pp(0.5;ge;50)))",
            "expected": [0, 1, 2],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "negation",
                        [
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        "conjunction",
                                        [
                                            Tree(
                                                Token("RULE", "name_op"),
                                                [
                                                    Token("STRING", "'Latitude'"),
                                                    Token("INT", "0"),
                                                ],
                                            ),
                                            Tree(
                                                Token("RULE", "percentile_op"),
                                                [
                                                    Token("FLOAT", "0.5"),
                                                    Token("COMPARISON", "ge"),
                                                    Token("SIGNED_NUMBER", "50"),
                                                ],
                                            ),
                                        ],
                                    )
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
        "multiple_columns": {
            "query": 'col(name("Latitude"; 0)) AND col(name("Longitude"; 0))',
            "expected": [0],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        "conjunction",
                        [
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "name_op"),
                                        [Token("STRING", '"Latitude"'), Token("INT", "0")],
                                    )
                                ],
                            ),
                            Tree(
                                Token("RULE", "col_op"),
                                [
                                    Tree(
                                        Token("RULE", "name_op"),
                                        [Token("STRING", '"Longitude"'), Token("INT", "0")],
                                    )
                                ],
                            ),
                        ],
                    )
                ],
            ),
        },
        "multiple_columns_inside": {
            "query": "col(name('Latitude'; 0) AND name('Longitude'; 0))",
            "expected": [],
            "parse_tree": Tree(
                Token("RULE", "query"),
                [
                    Tree(
                        Token("RULE", "col_op"),
                        [
                            Tree(
                                "conjunction",
                                [
                                    Tree(
                                        Token("RULE", "name_op"),
                                        [Token("STRING", "'Latitude'"), Token("INT", "0")],
                                    ),
                                    Tree(
                                        Token("RULE", "name_op"),
                                        [Token("STRING", "'Longitude'"), Token("INT", "0")],
                                    ),
                                ],
                            )
                        ],
                    )
                ],
            ),
        },
    },
}

INVALID_QUERIES: dict[str, dict[str, list[str]]] = {
    "invalid_syntax": {
        "queries": [
            "keyword()",
            "pp()",
            "kw()",
        ]
    },
    "missing_parentheses": {
        "queries": [
            "keyword(test",
            "pp(0.5;ge;20.0",
        ]
    },
    "invalid_operators": {
        "queries": [
            "kw(test) INVALID pp(0.5;ge;20.0)",
            "kw(test) AND OR pp(0.5;ge;20.0)",
        ]
    },
    "incomplete_expressions": {
        "queries": [
            "kw(test) AND",
            "NOT",
        ]
    },
    "invalid_percentile": {
        "queries": [
            "pp(a;ge;20.0)",
            "pp(0.5;invalid;20.0)",
            "pp(0.5;ge;abc)",
        ]
    },
    "malformed_compound": {
        "queries": [
            "(kw(test) AND",
            "kw(test)) OR pp(0.5;ge;20.0)",
            "AND kw(test)",
        ]
    },
    "invalid_column": {
        "queries": [
            "col(keyword(test))",  # Keywords not allowed in column expressions
            "col(kw(test))",  # Keywords not allowed in column expressions
            "col()",  # Empty column expression
            "col(name('test'))",  # Missing k parameter
            "col(name(; 0))",  # Missing name parameter
        ]
    },
}
