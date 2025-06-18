from abc import ABC, abstractmethod
from collections.abc import Sequence

from lark import ParseTree
from loguru import logger

from backend.config import DocumentArray, FainderMode, Metadata
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

from .common import DocResult


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
        fainder_index_name: str = "default",
    ) -> None:
        """Reset the executor's state."""

    @abstractmethod
    def execute(self, tree: ParseTree) -> DocResult:
        """Start processing the parse tree."""

    def updates_scores(self, doc_ids: DocumentArray, scores: Sequence[float]) -> None:
        logger.trace("Updating scores for {} documents", doc_ids.size)

        for doc_id, score in zip(doc_ids, scores, strict=True):
            self.scores[int(doc_id)] += score
