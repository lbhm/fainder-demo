from collections import defaultdict
from collections.abc import Sequence

import numpy as np
from lark import ParseTree, Token, Transformer_NonRecursive
from loguru import logger

from backend.config import ColumnHighlights, DocumentHighlights, FainderMode, Metadata
from backend.engine.conversion import col_to_doc_ids
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .common import ColResult, DocResult, TResult, junction, negate_array
from .executor import Executor


class SimpleExecutor(Transformer_NonRecursive[Token, DocResult], Executor):
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

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
        fainder_index_name: str = "default",
    ) -> None:
        self.fainder_index_name = fainder_index_name
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
        logger.trace("Evaluating keyword term: {}", items)

        result_docs, scores, highlights = self.tantivy_index.search(
            items[0], self.enable_highlighting, self.min_usability_score, self.rank_by_usability
        )
        self.updates_scores(result_docs, scores)

        return result_docs, (
            highlights,
            np.array([], dtype=np.uint32),
        )  # Return empty array for column highlights

    def col_op(self, items: list[ColResult]) -> DocResult:
        logger.trace("Evaluating column term with items of length: {}", len(items))

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        col_ids = items[0]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        if self.enable_highlighting:
            return doc_ids, ({}, col_ids)

        return doc_ids, ({}, np.array([], dtype=np.uint32))

    def name_op(self, items: list[Token]) -> ColResult:
        logger.trace("Evaluating column term: {}", items)

        column = items[0]
        k = int(items[1])

        return self.hnsw_index.search(column, k, None)

    def percentile_op(self, items: list[Token]) -> ColResult:
        logger.trace("Evaluating percentile term: {}", items)

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])

        return self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode, self.fainder_index_name
        )

    def conjunction(self, items: Sequence[TResult]) -> TResult:
        logger.trace("Evaluating conjunction with items of length: {}", len(items))

        return junction(items, "and", self.enable_highlighting, self.metadata.doc_to_cols)

    def disjunction(self, items: Sequence[TResult]) -> TResult:
        logger.trace("Evaluating disjunction with items of length: {}", len(items))

        return junction(items, "or", self.enable_highlighting, self.metadata.doc_to_cols)

    def negation(self, items: Sequence[TResult]) -> TResult:
        logger.trace("Evaluating negation with items of length: {}", len(items))

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")
        if isinstance(items[0], tuple):
            to_negate, _ = items[0]
            doc_result = negate_array(to_negate, len(self.metadata.doc_to_cols))
            # Result highlights are reset for negated results
            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = np.array([], dtype=np.uint32)
            return doc_result, (doc_highlights, col_highlights)

        to_negate_cols = items[0]
        return negate_array(to_negate_cols, len(self.metadata.col_to_doc))

    def query(self, items: Sequence[DocResult]) -> DocResult:
        logger.trace("Evaluating query with {} items", len(items))

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return items[0]
