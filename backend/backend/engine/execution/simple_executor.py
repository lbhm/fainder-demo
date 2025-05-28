from collections import defaultdict
from collections.abc import Sequence
from operator import and_, or_

from lark import ParseTree, Token, Transformer
from loguru import logger
from numpy import uint32

from backend.config import ColumnHighlights, DocumentHighlights, FainderMode, Metadata
from backend.engine.conversion import col_to_doc_ids
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .common import ColResult, DocResult, TResult, junction
from .executor import Executor


class SimpleExecutor(Transformer[Token, DocResult], Executor):
    """This transformer evaluates a parse tree bottom-up and computes the query result."""

    fainder_mode: FainderMode
    scores: dict[int, float]

    def __init__(
        self,
        tantivy_index: TantivyIndex,
        fainder_index: FainderIndex,
        hnsw_index: HnswIndex,
        metadata: Metadata,
        fainder_mode: FainderMode = FainderMode.LOW_MEMORY,
        enable_highlighting: bool = False,
        min_usability_score: float = 0.0,
        rank_by_usability: bool = True,
    ) -> None:
        super().__init__(visit_tokens=False)
        self.tantivy_index = tantivy_index
        self.fainder_index = fainder_index
        self.hnsw_index = hnsw_index
        self.metadata = metadata
        self.min_usability_score = min_usability_score
        self.rank_by_usability = rank_by_usability

        self.reset(fainder_mode, enable_highlighting)

    def reset(self, fainder_mode: FainderMode, enable_highlighting: bool = False) -> None:
        self.scores = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting

    def execute(self, tree: ParseTree) -> DocResult:
        """Start processing the parse tree."""
        return self.transform(tree)

    ##########################
    # Operator implementations
    ##########################

    def keyword_op(self, items: list[Token]) -> DocResult:
        logger.trace(f"Evaluating keyword term: {items}")

        result_docs, scores, highlights = self.tantivy_index.search(
            items[0], self.enable_highlighting, self.min_usability_score, self.rank_by_usability
        )
        self.updates_scores(result_docs, scores)

        return set(result_docs), (highlights, set())  # Return empty set for column highlights

    def col_op(self, items: list[ColResult]) -> DocResult:
        logger.trace(f"Evaluating column term: {items}")

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        col_ids = items[0]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        if self.enable_highlighting:
            return doc_ids, ({}, col_ids)

        return doc_ids, ({}, set())

    def name_op(self, items: list[Token]) -> ColResult:
        logger.trace(f"Evaluating column term: {items}")

        column = items[0]
        k = int(items[1])

        return self.hnsw_index.search(column, k, None)

    def percentile_op(self, items: list[Token]) -> ColResult:
        logger.trace(f"Evaluating percentile term: {items}")

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])

        return self.fainder_index.search(percentile, comparison, reference, self.fainder_mode)

    def conjunction(self, items: Sequence[TResult]) -> TResult:
        logger.trace(f"Evaluating conjunction with items: {items}")

        return junction(items, and_, self.enable_highlighting, self.metadata.doc_to_cols)

    def disjunction(self, items: Sequence[TResult]) -> TResult:
        logger.trace(f"Evaluating disjunction with items: {items}")

        return junction(items, or_, self.enable_highlighting, self.metadata.doc_to_cols)

    def negation(self, items: Sequence[TResult]) -> TResult:
        logger.trace(f"Evaluating negation with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")
        if isinstance(items[0], tuple):
            to_negate, _ = items[0]
            all_docs = set(self.metadata.doc_to_cols.keys())
            # Result highlights are reset for negated results
            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = set()
            return all_docs - to_negate, (doc_highlights, col_highlights)

        to_negate_cols = items[0]
        # For column expressions, we negate using the set of all column IDs
        all_columns = {uint32(col_id) for col_id in range(len(self.metadata.col_to_doc))}
        return all_columns - to_negate_cols

    def query(self, items: Sequence[DocResult]) -> DocResult:
        logger.trace(f"Evaluating query with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return items[0]
