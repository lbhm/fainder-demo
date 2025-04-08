import re
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable, Sequence
from functools import reduce
from operator import and_, or_
from typing import Any, Literal, TypeGuard, TypeVar

from lark import ParseTree, Token, Transformer
from lark.visitors import Visitor_Recursive
from loguru import logger
from numpy import uint32
from numpy.typing import NDArray

from backend.config import (
    ColumnHighlights,
    DocumentHighlights,
    ExecutorType,
    FainderMode,
    Highlights,
    Metadata,
)
from backend.engine.constants import FILTERING_STOP_POINTS
from backend.indices import FainderIndex, HnswIndex, TantivyIndex

T = TypeVar("T", tuple[set[int], Highlights], set[uint32])


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


class SimpleExecutor(Transformer[Token, tuple[set[int], Highlights]], Executor):
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
    ) -> None:
        self.scores = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting

    def updates_scores(self, doc_ids: Sequence[int], scores: Sequence[float]) -> None:
        logger.trace(f"Updating scores for {len(doc_ids)} documents")

        for doc_id, score in zip(doc_ids, scores, strict=True):
            self.scores[doc_id] += score

        for i, doc_id in enumerate(doc_ids):
            self.scores[doc_id] += scores[i]

    ### Operator implementations ###

    def keyword_op(self, items: list[Token]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating keyword term: {items}")

        result_docs, scores, highlights = self.tantivy_index.search(
            items[0], self.enable_highlighting, self.min_usability_score, self.rank_by_usability
        )
        self.updates_scores(result_docs, scores)

        return set(result_docs), (highlights, set())  # Return empty set for column highlights

    def col_op(self, items: list[set[uint32]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating column term: {items}")

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        col_ids = items[0]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        if self.enable_highlighting:
            return doc_ids, ({}, col_ids)

        return doc_ids, ({}, set())

    def name_op(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating column term: {items}")

        column = items[0]
        k = int(items[1])

        return self.hnsw_index.search(column, k, None)

    def percentile_op(self, items: list[Token]) -> set[uint32]:
        logger.trace(f"Evaluating percentile term: {items}")

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])

        result_hists = self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode
        )
        return hist_to_col_ids(result_hists, self.metadata.hist_to_col)

    def conjunction(
        self, items: list[tuple[set[int], Highlights]] | list[set[uint32]]
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating conjunction with items: {items}")

        return junction(items, and_, self.enable_highlighting, self.metadata.doc_to_cols)

    def disjunction(
        self, items: list[tuple[set[int], Highlights]] | list[set[uint32]]
    ) -> tuple[set[int], Highlights] | set[uint32]:
        logger.trace(f"Evaluating disjunction with items: {items}")

        return junction(items, or_, self.enable_highlighting, self.metadata.doc_to_cols)

    def negation(self, items: list[T]) -> T:
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

    def query(self, items: list[tuple[set[int], Highlights]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating query with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return items[0]

    def execute(self, tree: ParseTree) -> tuple[set[int], Highlights]:
        """Start processing the parse tree."""
        return self.transform(tree)


class ResultGroupAnnotator(Visitor_Recursive[Token]):
    """
    This visitor adds numbers for intermediate result groups to each node.
    A node has a write group and a list of read groups.
    """

    def __init__(self) -> None:
        super().__init__()
        # Use dictionaries to store attributes for both Tree and Token objects
        self.write_groups: dict[int, int] = {}
        self.read_groups: dict[int, list[int]] = {}
        self.parent_write_group: dict[int, int] = {}  # node write group to parent write group
        self.current_write_group: int = 0

    def apply(self, tree: ParseTree) -> None:
        # Initialize the root node with group 0
        self.write_groups[id(tree)] = 0
        self.read_groups[id(tree)] = [0]
        self.visit_topdown(tree)

    def _create_group_id(self) -> int:
        """Create a new group ID."""
        logger.trace(f"new group id: {self.current_write_group + 1}")
        self.current_write_group += 1
        return self.current_write_group

    def __default__(self, tree: ParseTree) -> None:
        # Set attributes for all children using the parent's values
        logger.trace(f"Processing default node: {tree}")
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            write_group = self.write_groups[id(tree)]
            read_group = self.read_groups[id(tree)]

            for child in tree.children:
                # Store in our dictionaries rather than on the objects directly
                self.write_groups[id(child)] = write_group
                self.read_groups[id(child)] = read_group
                logger.trace(
                    f"Child {child} has write group {write_group} and read group {read_group}"
                )
        else:
            logger.warning(f"Node {tree} does not have write or read groups")

    def query(self, tree: ParseTree) -> None:
        logger.trace(f"Processing query node: {tree}")
        # Set attributes for query node and children
        self.write_groups[id(tree)] = 0
        self.read_groups[id(tree)] = [0]
        self.parent_write_group[0] = 0

        # Set same attributes for all children
        for child in tree.children:
            self.write_groups[id(child)] = 0
            self.read_groups[id(child)] = [0]

    def conjunction(self, tree: ParseTree) -> None:
        logger.trace(f"Processing conjunction node: {tree}")
        # For conjunction, all children read and write to the same groups
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            write_group = self.write_groups[id(tree)]
            read_group = self.read_groups[id(tree)]

            for child in tree.children:
                self.write_groups[id(child)] = write_group
                self.read_groups[id(child)] = read_group
                self.parent_write_group[write_group] = write_group
        else:
            logger.warning(f"Node {tree} does not have write or read groups")

    def disjunction(self, tree: ParseTree) -> None:
        logger.trace(f"Processing disjunction node: {tree}")
        # For disjunction, give each child a new write group and add to read groups
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            parent_write_group = self.write_groups[id(tree)]
            parent_read_groups = self.read_groups[id(tree)].copy()
            parent_read_groups.remove(parent_write_group)

            for child in tree.children:
                current_write_group = self._create_group_id()
                self.write_groups[id(child)] = current_write_group
                self.read_groups[id(child)] = [current_write_group, *parent_read_groups]
                self.parent_write_group[current_write_group] = parent_write_group
        else:
            logger.warning(f"Node {tree} does not have write or read groups")

    def negation(self, tree: ParseTree) -> None:
        logger.trace(f"Processing negation node: {tree}")
        # For negation, increment the write group and add to read groups
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            parent_group = self.write_groups[id(tree)]
            new_group = self._create_group_id()
            read_groups = [new_group]

            for child in tree.children:
                self.write_groups[id(child)] = new_group
                self.read_groups[id(child)] = read_groups
                self.parent_write_group[new_group] = parent_group
        else:
            logger.warning(f"Node {tree} does not have write or read groups")


class IntermediateResult:
    """Intermediate results for prefiltering.
    Only one of doc_ids or col_ids should be set.
    If multiple are set, this should result in an error.
    """

    doc_ids: set[int] | None = None
    col_ids: set[uint32] | None = None

    def build_hist_filter(
        self, metadata: Metadata, fainder_mode: FainderMode
    ) -> set[uint32] | None:
        """Build a histogram filter from the intermediate results."""
        if self.col_ids is not None:
            if self._exceeds_filtering_limit(self.col_ids, "num_col_ids", fainder_mode):
                raise ValueError("Exceeded filtering limit for column IDs")
            return col_to_hist_ids(self.col_ids, metadata.col_to_hist)
        if self.doc_ids is not None:
            if self._exceeds_filtering_limit(self.doc_ids, "num_doc_ids", fainder_mode):
                raise ValueError("Exceeded filtering limit for document IDs")
            col_ids = doc_to_col_ids(self.doc_ids, metadata.doc_to_cols)
            return col_to_hist_ids(col_ids, metadata.col_to_hist)
        return None

    def _exceeds_filtering_limit(
        self,
        ids: set[uint32] | set[int],
        id_type: Literal["num_col_ids", "num_doc_ids"],
        fainder_mode: FainderMode,
    ) -> bool:
        """Check if the number of IDs exceeds the filtering limit for the current mode."""
        return len(ids) > FILTERING_STOP_POINTS[fainder_mode][id_type]

    def __str__(self) -> str:
        """String representation of the intermediate result."""
        return f"""IntermediateResult(
        doc_ids={self.doc_ids},
        col_ids={self.col_ids},
        )"""


class IntermediateDataStore:
    """Store intermediate results for prefiltering per group."""

    def __init__(self) -> None:
        self.results: dict[int, IntermediateResult] = {}

    def add_col_id_results(self, write_group: int, col_ids: set[uint32]) -> None:
        logger.trace(f"Adding column IDs to write group {write_group}: {col_ids}")
        self.results[write_group] = IntermediateResult()
        self.results[write_group].col_ids = col_ids.copy()

    def add_doc_id_results(self, write_group: int, doc_ids: set[int]) -> None:
        logger.trace(f"Adding document IDs to write group {write_group}: {doc_ids}")
        self.results[write_group] = IntermediateResult()
        self.results[write_group].doc_ids = doc_ids.copy()

    def build_filter(
        self, read_groups: list[int], metadata: Metadata, fainder_mode: FainderMode
    ) -> set[uint32] | None:
        """Build a histogram filter from the intermediate results."""
        hist_ids: set[uint32] = set()
        first = True
        if len(read_groups) == 0:
            return hist_ids

        logger.trace(f"read groups {read_groups}")
        for read_group in read_groups:
            if read_group not in self.results:
                return None

            try:
                logger.trace(
                    f"Processing read group {read_group} with results {self.results[read_group]}"
                )
                intermediate = self.results[read_group].build_hist_filter(metadata, fainder_mode)
                if intermediate is not None:
                    logger.trace(f"intermediate {intermediate}")
                    if first:
                        hist_ids = intermediate
                        first = False
                    else:
                        hist_ids.intersection_update(intermediate)
            except ValueError:
                return None

        logger.trace(f"Hist IDs: {hist_ids}")
        return hist_ids if not first else None


class PrefilteringExecutor(Transformer[Token, tuple[set[int], Highlights]], Executor):
    """Uses prefiltering to reduce the number of documents before executing the query."""

    fainder_mode: FainderMode
    scores: dict[int, float]
    intermediate_results: IntermediateDataStore
    write_groups: dict[int, int]  # Maps node ID to write group
    read_groups: dict[int, list[int]]  # Maps node ID to read groups
    parent_write_group: dict[int, int]  # Maps write group to parent write group

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
        self.tantivy_index = tantivy_index
        self.fainder_index = fainder_index
        self.hnsw_index = hnsw_index
        self.metadata = metadata
        self.write_groups = {}
        self.intermediate_results = IntermediateDataStore()
        self.read_groups = {}
        self.parent_write_group = {}
        self.min_usability_score = min_usability_score
        self.rank_by_usability = rank_by_usability

        self.reset(fainder_mode, enable_highlighting)

    def reset(
        self,
        fainder_mode: FainderMode,
        enable_highlighting: bool = False,
    ) -> None:
        logger.trace("reset")
        self.scores = defaultdict(float)
        self.fainder_mode = fainder_mode
        self.enable_highlighting = enable_highlighting
        self.intermediate_results = IntermediateDataStore()
        self.write_groups = {}
        self.read_groups = {}

    def updates_scores(self, doc_ids: Sequence[int], scores: Sequence[float]) -> None:
        logger.trace(f"Updating scores for {len(doc_ids)} documents")

        for doc_id, score in zip(doc_ids, scores, strict=True):
            self.scores[doc_id] += score

        for i, doc_id in enumerate(doc_ids):
            self.scores[doc_id] += scores[i]

    def _get_write_group(self, node: ParseTree | Token) -> int:
        """Get the write group for a node."""
        node_id = id(node)
        if node_id in self.write_groups:
            return self.write_groups[node_id]
        logger.warning(f"Node {node} does not have a write group with id {node_id}")
        logger.warning(f"Write groups: {self.write_groups}")
        raise ValueError("Node does not have a write group")

    def _get_read_groups(self, node: ParseTree | Token) -> list[int]:
        """Get the read groups for a node."""
        node_id = id(node)
        if node_id in self.read_groups:
            return self.read_groups[node_id]
        logger.warning(f"Node {node} does not have read groups")
        logger.warning(f"Read groups: {self.read_groups}")
        raise ValueError("Node does not have read groups")

    def _get_parent_write_group(self, write_group: int) -> int:
        """Get the parent write group for a write group."""
        if write_group in self.parent_write_group:
            return self.parent_write_group[write_group]
        logger.warning(f"Write group {write_group} does not have a parent write group")
        logger.warning(f"Parent write groups: {self.parent_write_group}")
        raise ValueError("Write group does not have a parent write group")

    def execute(self, tree: ParseTree) -> tuple[set[int], Highlights]:
        """Start processing the parse tree."""
        self.write_groups = {}
        self.read_groups = {}
        logger.trace(tree.pretty())
        groups = ResultGroupAnnotator()
        groups.apply(tree)
        self.write_groups = groups.write_groups
        self.read_groups = groups.read_groups
        self.parent_write_group = groups.parent_write_group
        logger.trace(f"Write groups: {self.write_groups}")
        logger.trace(f"Read groups: {self.read_groups}")
        logger.trace(f"Parent write groups: {self.parent_write_group}")
        return self.transform(tree)

    ### Operator implementations ###

    def keyword_op(self, items: list[Token]) -> tuple[set[int], Highlights, int]:
        logger.trace(f"Evaluating keyword term: {items}")

        result_docs, scores, highlights = self.tantivy_index.search(
            items[0], self.enable_highlighting, self.min_usability_score, self.rank_by_usability
        )
        self.updates_scores(result_docs, scores)

        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_doc_id_results(write_group, set(result_docs))

        parent_write_group = self._get_parent_write_group(write_group)

        return set(result_docs), (highlights, set()), parent_write_group

    def col_op(self, items: list[tuple[set[uint32], int]]) -> tuple[set[int], Highlights, int]:
        logger.trace(f"Evaluating column term: {items}")

        if len(items) != 1:
            raise ValueError("Column term must have exactly one item")
        col_ids = items[0][0]
        write_group = items[0][1]
        doc_ids = col_to_doc_ids(col_ids, self.metadata.col_to_doc)
        self.intermediate_results.add_col_id_results(write_group, col_ids)
        parent_write_group = self._get_parent_write_group(write_group)
        if self.enable_highlighting:
            return doc_ids, ({}, col_ids), parent_write_group

        return doc_ids, ({}, set()), parent_write_group

    def name_op(self, items: list[Token]) -> tuple[set[uint32], int]:
        logger.trace(f"Evaluating column term: {items}")

        column = items[0]
        k = int(items[1])

        result = self.hnsw_index.search(column, k, None)

        write_group = self._get_write_group(items[0])
        self.intermediate_results.add_col_id_results(write_group, result)
        parent_write_group = self._get_parent_write_group(write_group)
        return result, parent_write_group

    def percentile_op(self, items: list[Token]) -> tuple[set[uint32], int]:
        logger.trace(f"Evaluating percentile term: {items}")

        percentile = float(items[0])
        comparison: str = items[1]
        reference = float(items[2])
        hist_filter = self.intermediate_results.build_filter(
            self._get_read_groups(items[0]), self.metadata, self.fainder_mode
        )
        logger.trace(f"Hist filter: {hist_filter}")
        write_group = self._get_write_group(items[0])
        if hist_filter is not None and len(hist_filter) == 0:
            return set(), write_group
        result_hists = self.fainder_index.search(
            percentile, comparison, reference, self.fainder_mode, hist_filter
        )
        result = hist_to_col_ids(result_hists, self.metadata.hist_to_col)
        self.intermediate_results.add_col_id_results(write_group, result)
        parent_write_group = self._get_parent_write_group(write_group)
        return result, parent_write_group

    def conjunction(
        self, items: list[tuple[set[int], Highlights, int]] | list[tuple[set[uint32], int]]
    ) -> tuple[set[int], Highlights, int] | tuple[set[uint32], int]:
        logger.trace(f"Evaluating conjunction with items: {items}")

        clean_items: list[tuple[set[int], Highlights]] | list[set[uint32]] = []
        for item in items:
            if len(item) == 3:
                clean_items.append((item[0], item[1]))  # type: ignore
            else:
                clean_items.append(item[0])  # type: ignore

        result = junction(clean_items, and_, self.enable_highlighting, self.metadata.doc_to_cols)
        write_group = items[0][2] if len(items[0]) == 3 else items[0][1]
        if isinstance(result, tuple):
            self.intermediate_results.add_doc_id_results(write_group, result[0])
        else:
            self.intermediate_results.add_col_id_results(write_group, result)

        parent_write_group = self._get_parent_write_group(write_group)
        if isinstance(result, tuple):
            return result[0], result[1], parent_write_group
        return result, parent_write_group

    def disjunction(
        self, items: list[tuple[set[int], Highlights, int]] | list[tuple[set[uint32], int]]
    ) -> tuple[set[int], Highlights, int] | tuple[set[uint32], int]:
        logger.trace(f"Evaluating disjunction with items: {items}")

        clean_items: list[tuple[set[int], Highlights]] | list[set[uint32]] = []
        for item in items:
            if len(item) == 3:
                clean_items.append((item[0], item[1]))  # type: ignore
            else:
                clean_items.append(item[0])  # type: ignore

        result = junction(clean_items, or_, self.enable_highlighting, self.metadata.doc_to_cols)
        write_group = items[0][2] if len(items[0]) == 3 else items[0][1]

        if isinstance(result, tuple):
            self.intermediate_results.add_doc_id_results(write_group, result[0])
        else:
            self.intermediate_results.add_col_id_results(write_group, result)

        parent_write_group = self._get_parent_write_group(write_group)
        if isinstance(result, tuple):
            return result[0], result[1], parent_write_group
        return result, parent_write_group

    def negation(
        self, items: list[tuple[set[int], Highlights, int]] | list[tuple[set[uint32], int]]
    ) -> tuple[set[int], Highlights, int] | tuple[set[uint32], int]:
        logger.trace(f"Evaluating negation with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Negation term must have exactly one item")
        if len(items[0]) == 3:
            to_negate, _, write_group = items[0]
            all_docs = set(self.metadata.doc_to_cols.keys())
            # Result highlights are reset for negated results
            doc_highlights: DocumentHighlights = {}
            col_highlights: ColumnHighlights = set()
            parent_write_group = self._get_parent_write_group(write_group)
            result = (all_docs - to_negate, (doc_highlights, col_highlights), parent_write_group)
            self.intermediate_results.add_doc_id_results(write_group, result[0])
            return result
        if len(items[0]) == 2:
            to_negate_cols: set[uint32] = items[0][0]
            write_group_cols: int = items[0][1]
            # For column expressions, we negate using the set of all column IDs
            all_columns = {uint32(col_id) for col_id in range(len(self.metadata.col_to_doc))}
            result_col = all_columns - to_negate_cols
            self.intermediate_results.add_col_id_results(write_group_cols, result_col)
            parent_write_group_cols = self._get_parent_write_group(write_group_cols)
            return result_col, parent_write_group_cols

        raise ValueError("Negation term must have exactly one item")

    def query(self, items: list[tuple[set[int], Highlights, int]]) -> tuple[set[int], Highlights]:
        logger.trace(f"Evaluating query with {len(items)} items")

        if len(items) != 1:
            raise ValueError("Query must have exactly one item")
        return items[0][0], items[0][1]


def create_executor(
    executor_type: ExecutorType,
    tantivy_index: TantivyIndex,
    fainder_index: FainderIndex,
    hnsw_index: HnswIndex,
    metadata: Metadata,
    fainder_mode: FainderMode = FainderMode.LOW_MEMORY,
    enable_highlighting: bool = False,
    min_usability_score: float = 0.0,
    rank_by_usability: bool = True,
) -> Executor:
    """Factory function to create the appropriate executor based on the executor type."""
    match executor_type:
        case ExecutorType.SIMPLE:
            return SimpleExecutor(
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                metadata=metadata,
                fainder_mode=fainder_mode,
                enable_highlighting=enable_highlighting,
                min_usability_score=min_usability_score,
                rank_by_usability=rank_by_usability,
            )
        case ExecutorType.PREFILTERING:
            return PrefilteringExecutor(
                tantivy_index=tantivy_index,
                fainder_index=fainder_index,
                hnsw_index=hnsw_index,
                metadata=metadata,
                fainder_mode=fainder_mode,
                enable_highlighting=enable_highlighting,
                min_usability_score=min_usability_score,
                rank_by_usability=rank_by_usability,
            )
        case ExecutorType.PARALLEL:
            # TODO: Implement ParallelExecutor
            raise NotImplementedError("ParallelExecutor not implemented yet")
        case _:
            raise ValueError(f"Unknown executor type: {executor_type}")


def is_table_result(val: list[Any]) -> TypeGuard[list[tuple[set[int], Highlights]]]:
    """Check if a list contains table results (document IDs and highlights)."""
    return all(isinstance(item, tuple) for item in val)


def merge_highlights(
    left: Highlights, right: Highlights, doc_ids: set[int], doc_to_cols: dict[int, set[int]]
) -> Highlights:
    """Merge highlights for documents that are in the result set."""
    pattern = r"<mark>(.*?)</mark>"
    regex = re.compile(pattern, re.DOTALL)

    # Merge document highlights
    doc_highlights: DocumentHighlights = {}
    left_doc_highlights = left[0]
    right_doc_highlights = right[0]
    for doc_id in doc_ids:
        left_highlights = left_doc_highlights.get(doc_id, {})
        right_highlights = right_doc_highlights.get(doc_id, {})

        # Only process if either side has highlights
        if left_highlights or right_highlights:
            merged_highlights = {}

            # Process each field that appears in either highlight set
            all_keys = set(left_highlights.keys()) | set(right_highlights.keys())
            for key in all_keys:
                left_text = left_highlights.get(key, "")
                right_text = right_highlights.get(key, "")

                # If either text is empty, use the non-empty one
                if not left_text:
                    merged_highlights[key] = right_text
                    continue
                if not right_text:
                    continue

                # Both texts have content, merge their marks
                # Extract all marked words from right text
                right_marks = set(regex.findall(right_text))

                # Add marks from right text to left text
                for word in right_marks:
                    if f"<mark>{word}</mark>" not in left_text:
                        # Word isn't marked yet
                        left_text = left_text.replace(word, f"<mark>{word}</mark>")

                merged_highlights[key] = left_text

            doc_highlights[doc_id] = merged_highlights

    # Merge column highlights
    col_highlights = left[1] | right[1]
    col_highlights &= doc_to_col_ids(doc_ids, doc_to_cols)

    return doc_highlights, col_highlights


def junction(
    items: list[tuple[set[int], Highlights]] | list[set[uint32]],
    operator: Callable[[Any, Any], Any],
    enable_highlighting: bool = False,
    doc_to_cols: dict[int, set[int]] | None = None,
) -> tuple[set[int], Highlights] | set[uint32]:
    """Combine query results using a junction operator (AND/OR)."""
    if len(items) < 2:
        raise ValueError("Junction must have at least two items")

    # Items contains table results (i.e., tuple[set[int], Highlights])
    if is_table_result(items):
        if enable_highlighting and doc_to_cols is not None:
            # Initialize result with first item
            doc_ids: set[int] = items[0][0]
            highlights: Highlights = items[0][1]

            # Merge all other items
            for item in items[1:]:
                doc_ids = operator(doc_ids, item[0])
                highlights = merge_highlights(highlights, item[1], doc_ids, doc_to_cols)

            return doc_ids, highlights

        return reduce(operator, [item[0] for item in items]), ({}, set())

    # Items contains column results (i.e., set[uint32])
    return reduce(operator, items)  # type: ignore


def doc_to_col_ids(doc_ids: set[int], doc_to_cols: dict[int, set[int]]) -> set[uint32]:
    return {
        uint32(col_id)
        for doc_id in doc_ids
        if doc_id in doc_to_cols
        for col_id in doc_to_cols[doc_id]
    }


def col_to_doc_ids(col_ids: set[uint32], col_to_doc: NDArray[uint32]) -> set[int]:
    return {int(col_to_doc[col_id]) for col_id in col_ids}


def col_to_hist_ids(col_ids: set[uint32], col_to_hist: dict[int, int]) -> set[uint32]:
    return {uint32(col_to_hist[int(col_id)]) for col_id in col_ids if int(col_id) in col_to_hist}


def hist_to_col_ids(hist_ids: set[uint32], hist_to_col: NDArray[uint32]) -> set[uint32]:
    return {hist_to_col[hist_id] for hist_id in hist_ids}
