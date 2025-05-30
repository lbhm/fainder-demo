import argparse
from typing import Literal

from lark import Lark


class Parser(Lark):
    GRAMMAR = """
    query:          tbl_expr

    ?tbl_expr:      tbl_term
                    | tbl_term ("OR" tbl_term)+ -> disjunction
    ?tbl_term:      tbl_factor
                    | tbl_factor ("AND" tbl_factor)+ -> conjunction
    ?tbl_factor:    tbl_operator
                    | "NOT" tbl_factor -> negation
                    | "(" tbl_expr ")"
    ?tbl_operator:  _KEYWORD_KW "(" keyword_op ")"
                    | _COLUMN_KW "(" col_op ")"

    ?col_expr:      col_term
                    | col_term ("OR" col_term)+ -> disjunction
    ?col_term:      col_factor
                    | col_factor ("AND" col_factor)+ -> conjunction
    ?col_factor:    col_operator
                    | "NOT" col_factor -> negation
                    | "(" col_expr ")"
    ?col_operator:  _NAME_KW "(" name_op ")"
                    | _PERCENTILE_KW "(" percentile_op ")"

    col_op:         col_expr
    keyword_op:     STRING
    percentile_op:  FLOAT ";" COMPARISON ";" SIGNED_NUMBER
    name_op:        STRING ";" INT

    _KEYWORD_KW:    "kw"i | "keyword"i
    _COLUMN_KW:     "col"i | "column"i
    _NAME_KW:       "name"i
    _PERCENTILE_KW: "pp"i | "percentile"i
    COMPARISON:     "ge" | "gt" | "le" | "lt"

    %import common.FLOAT
    %import common.INT
    %import common.SIGNED_NUMBER
    %import common.WS
    %import common.SH_COMMENT
    %import python.STRING

    %ignore WS
    %ignore SH_COMMENT
    """

    def __init__(
        self,
        parser: Literal["earley", "lalr"] = "lalr",
        lexer: Literal["auto", "basic", "contextual", "dynamic", "dynamic_complete"] = "auto",
        strict: bool = True,
    ) -> None:
        super().__init__(  # pyright: ignore[reportUnknownMemberType]
            Parser.GRAMMAR, start="query", parser=parser, lexer=lexer, strict=strict
        )


def main() -> None:
    argparser = argparse.ArgumentParser("DQL Parser")
    argparser.add_argument("query", type=str, help="DQL query")
    args = argparser.parse_args()

    parser = Parser()
    print(parser.parse(args.query).pretty(), end="")  # noqa: T201
