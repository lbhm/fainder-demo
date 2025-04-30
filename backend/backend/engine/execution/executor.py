from abc import ABC, abstractmethod
from collections.abc import Sequence

from lark import ParseTree
from loguru import logger

from backend.config import (
    FainderMode,
    Highlights,
    Metadata,
)
from backend.indices import FainderIndex, HnswIndex, TantivyIndex


class Executor(ABC):
    """Base abstract class for query executors that defines the common interface."""

    scores: dict[int, float]

    @abstractmethod
    def __init__(
        self,
        tantivy_index: TantivyIndex,
        fainder_index: FainderIndex,
        hnsw_index: HnswIndex,
        metadata: Metadata,
        fainder_mode: FainderMode = FainderMode.LOW_MEMORY,
        enable_highlighting: bool = False,
    ) -> None:
        """Initialize the executor with the necessary indices and metadata."""

    @abstractmethod
    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
    ) -> None:
        """Reset the executor's state."""

    @abstractmethod
    def execute(self, tree: ParseTree) -> tuple[set[int], Highlights]:
        """Start processing the parse tree."""

    def updates_scores(self, doc_ids: Sequence[int], scores: Sequence[float]) -> None:
        logger.trace(f"Updating scores for {len(doc_ids)} documents")

        for doc_id, score in zip(doc_ids, scores, strict=True):
            self.scores[doc_id] += score
