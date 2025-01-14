from collections import defaultdict
from collections.abc import Sequence

from lark import Lark, Token, Transformer, Tree, Visitor
from loguru import logger
from numpy import uint32

from backend.column_search import ColumnSearch
from backend.config import Metadata
from backend.fainder_index import FainderIndex
from backend.lucene_connector import LuceneConnector

GRAMMAR = """
    start: query
    query: expression (OPERATOR query)?
    expression: not_expr | term | "(" query ")"
    not_expr: "NOT" term | "NOT" "(" query ")"
    term: PERCENTILE_OPERATOR "(" percentileterm ")"
        | KEYWORD_OPERATOR "(" keywordterm ")"
        | COLUMN_OPERATOR "(" columnterm ")"
    percentileterm: FLOAT ";" COMPARISON ";" FLOAT
    keywordterm: KEYWORD
    columnterm: IDENTIFIER ";" NUMBER
    OPERATOR: "AND" | "OR" | "XOR"
    COMPARISON: "ge" | "gt" | "le" | "lt"
    PERCENTILE_OPERATOR: ("pp"i | "percentile"i) " "*
    KEYWORD_OPERATOR: ("kw"i | "keyword"i) " "*
    COLUMN_OPERATOR: ("col"i | "column"i) " "*
    NUMBER: /[0-9]+/
    FLOAT: /[0-9]+(\\.[0-9]+)?/
    IDENTIFIER: /[a-zA-Z0-9_]+/
    KEYWORD: /[^;)]+/
    %ignore " "
"""


class QueryEvaluator:
    def __init__(
        self,
        lucene_connector: LuceneConnector,
        rebinning_index: FainderIndex,
        conversion_index: FainderIndex,
        column_search: ColumnSearch,
        metadata: Metadata,
    ):
        self.metadata = metadata
        self.lucene_connector = lucene_connector
        self.rebinning_index = rebinning_index
        self.conversion_index = conversion_index  # NOTE: Currently unused
        self.grammar = Lark(GRAMMAR, start="start")
        self.annotator = QueryAnnotator()
        self.column_search = column_search
        self.executor = QueryExecutor(
            self.lucene_connector, self.rebinning_index, self.column_search, self.metadata
        )

    def parse(self, query: str) -> Tree:
        return self.grammar.parse(query)

    async def execute(self, query: str, enable_filtering: bool = True) -> list[int]:
        self.annotator.reset()
        self.executor.reset()
        self.executor.enable_filtering = enable_filtering

        parse_tree = self.parse(query)
        self.annotator.visit(parse_tree)
        logger.trace(f"Parse tree: {parse_tree.pretty()}")

        result: list[int] = list(self.executor.transform(parse_tree))
        # Sort the results by score (descending), append to the end if no score is available
        result.sort(key=lambda x: self.executor.scores.get(x, -1), reverse=True)
        return result


class QueryAnnotator(Visitor):
    """
    This visitor goes top-down through the parse tree and annotates each percentile and keyword
    term with its parent operator and side (i.e., evaluation order) in the parent expression.
    """

    # TODO: We need to investigate this class because nodes are annotated too often

    def __init__(self) -> None:
        self.current_operator: str | None = None
        self.current_side: str | None = None

    def reset(self) -> None:
        self.current_operator = None
        self.current_side = None

    def query(self, tree: Tree):
        if len(tree.children) == 3:  # Has operator
            old_operator = self.current_operator
            old_side = self.current_side

            assert isinstance(tree.children[1], Token)
            self.current_operator = tree.children[1].value

            # Visit left side
            self.current_side = "left"
            self.visit(tree.children[0])

            # Visit right side
            self.current_side = "right"
            self.visit(tree.children[2])

            self.current_operator = old_operator
            self.current_side = old_side
        else:
            self.visit(tree.children[0])

    def percentileterm(self, tree: Tree) -> None:
        if self.current_operator:
            tree.children.append(self.current_operator)
            tree.children.append(self.current_side)

    def keywordterm(self, tree: Tree) -> None:
        if self.current_operator:
            tree.children.append(self.current_operator)
            tree.children.append(self.current_side)

    def columnterm(self, tree: Tree) -> None:
        if self.current_operator:
            tree.children.append(self.current_operator)
            tree.children.append(self.current_side)


class QueryExecutor(Transformer):
    """This transformer evaluates the parse tree bottom-up and compute the query result."""

    scores: dict[int, float]
    last_result: set[uint32] | None  # ids of the columns
    current_side: str | None

    def __init__(
        self,
        lucene_connector: LuceneConnector,
        fainder_index: FainderIndex,
        column_search: ColumnSearch,
        metadata: Metadata,
        enable_filtering: bool = True,
    ):
        self.fainder_index = fainder_index
        self.lucene_connector = lucene_connector
        self.enable_filtering = enable_filtering
        self.column_search = column_search
        self.metadata = metadata
        self.reset()

    def _get_column_filter(self, operator: str | None, side: str | None) -> set[uint32] | None:
        """Create a document filter for AND operators based on previous results."""
        if (
            not self.enable_filtering
            or not self.last_result
            or operator != "AND"
            or side != "right"
        ):
            return None

        # Only apply filters to the right side of AND operations
        logger.trace(f"Applying filter from previous result: {self.last_result}")
        return self.last_result

    def reset(self) -> None:
        self.scores = defaultdict(int)
        self.last_result = None
        self.current_side = None

    def updates_scores(self, doc_ids: Sequence[int], scores: Sequence[float]) -> None:
        logger.trace(f"Updating scores for {len(doc_ids)} documents")
        for doc_id, score in zip(doc_ids, scores, strict=True):
            self.scores[doc_id] += score

        for i, doc_id in enumerate(doc_ids):
            self.scores[doc_id] += scores[i]

    def percentileterm(self, items: list[Token]) -> set[uint32]:
        # TODO: Investigate length of items and annotations
        logger.trace(f"Evaluating percentile term: {items}")
        percentile = float(items[0].value)
        comparison = items[1].value
        reference = float(items[2].value)
        operator = None
        side = None
        if len(items) >= 5:
            operator = items[-2]
            side = items[-1]

        filter_column = self._get_column_filter(operator, side)
        filter_hists = None
        if filter_column:
            filter_hists = columns_ids_to_hist_ids(filter_column, self.metadata.col_to_hist)

        result_hists = self.fainder_index.search(percentile, comparison, reference, filter_hists)
        result = hist_ids_to_column_ids(result_hists, self.metadata.hist_to_col)
        self.last_result = result
        return result

    def keywordterm(self, items: list[Token]) -> set[uint32]:
        # TODO: Investigate length of items and annotations
        logger.trace(f"Evaluating keyword term: {items}")
        keyword = items[0].value.strip()
        operator = items[-2] if len(items) > 2 else None
        side = items[-1] if len(items) > 2 else None
        filter_column = self._get_column_filter(operator, side)

        filter_docs = None
        if filter_column:
            filter_docs = column_ids_to_doc_ids(filter_column, self.metadata.col_to_doc)

        result_docs, scores = self.lucene_connector.evaluate_query(keyword, filter_docs)
        self.updates_scores(result_docs, scores)
        #
        result_set = doc_ids_to_column_ids(set(result_docs), self.metadata.doc_to_cols)
        self.last_result = result_set
        return result_set

    def columnterm(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating column term: {items}")
        column = items[0].value.strip()
        k = int(items[1].value.strip())
        operator = items[-2] if len(items) > 2 else None
        side = items[-1] if len(items) > 2 else None
        filter_column = self._get_column_filter(operator, side)

        result = self.column_search.search(column, k, filter_column)
        self.last_result = result
        return result

    def term(self, items: tuple[Token, set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating term with items: {items}")
        return items[1]

    def not_expr(self, items: list[set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating NOT expression with {len(items)} items")
        # TODO: Same "Problem" as in the query function with xor
        to_negate = items[0]
        doc_ids = column_ids_to_doc_ids(to_negate, self.metadata.col_to_doc)
        all_docs = set(self.metadata.doc_to_cols.keys())
        result = all_docs - doc_ids
        return doc_ids_to_column_ids(result, self.metadata.doc_to_cols)

    def expression(self, items: list[set[uint32]]) -> set[uint32]:
        logger.trace(f"Evaluating expression with {len(items[0])} items")
        return items[0]

    def query(self, items: list[set[uint32] | Token]) -> set[uint32]:
        logger.trace(f"Evaluating query with {len(items)} items")
        if len(items) == 1 and isinstance(items[0], set):
            return items[0]

        left: set[uint32] = items[0]  # type: ignore
        operator: str = items[1].value.strip()  # type: ignore
        right: set[uint32] = items[2]  # type: ignore

        match operator:
            case "AND":
                return left & right
            case "OR":
                return left | right
            case "XOR":
                # TODO: Document 2-level XOR
                left_docs = column_ids_to_doc_ids(left, self.metadata.col_to_doc)
                right_docs = column_ids_to_doc_ids(right, self.metadata.col_to_doc)
                return doc_ids_to_column_ids(left_docs ^ right_docs, self.metadata.doc_to_cols)
            case _:
                raise ValueError(f"Unknown operator: {operator}")

    def start(self, items: list[set[uint32]]) -> set[int]:
        logger.trace("Starting query evaluation")
        logger.trace(f"Final result: {items[0]}")
        return column_ids_to_doc_ids(items[0], self.metadata.col_to_doc)


def doc_ids_to_column_ids(doc_ids: set[int], doc_to_columns: dict[int, set[int]]) -> set[uint32]:
    column_ids: set[uint32] = set()
    for doc_id in doc_ids:
        if doc_id in doc_to_columns:
            column_ids.update(uint32(x) for x in doc_to_columns[doc_id])

    return column_ids


def column_ids_to_doc_ids(column_ids: set[uint32], column_to_doc: dict[int, int]) -> set[int]:
    doc_ids = set()
    for column_id in column_ids:
        if int(column_id) in column_to_doc:
            doc_ids.add(column_to_doc[int(column_id)])

    return doc_ids


def columns_ids_to_hist_ids(
    column_ids: set[uint32], column_to_hist: dict[int, int]
) -> set[uint32]:
    hist_ids = set()
    for column_id in column_ids:
        if int(column_id) in column_to_hist:
            hist_ids.add(uint32(column_to_hist[int(column_id)]))

    return hist_ids


def hist_ids_to_column_ids(hist_ids: set[uint32], hist_to_column: dict[int, int]) -> set[uint32]:
    column_ids = set()
    for hist_id in hist_ids:
        if hist_id in hist_to_column:
            column_ids.add(uint32(hist_to_column[int(hist_id)]))

    return column_ids
