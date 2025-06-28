import re
from collections.abc import Sequence
from typing import Any, Literal, TypeGuard, TypeVar

import numpy as np
from lark import ParseTree, Token
from lark.visitors import Visitor_Recursive
from loguru import logger
from numpy.typing import NDArray

from backend.config import ColumnArray, DocumentArray, DocumentHighlights, FainderMode, Highlights
from backend.engine.constants import get_filtering_stop_point
from backend.engine.conversion import doc_to_col_ids

DocResult = tuple[DocumentArray, Highlights]
ColResult = ColumnArray
TResult = TypeVar("TResult", DocResult, ColResult)
TArray = TypeVar("TArray", ColumnArray, DocumentArray)


class ResultGroupAnnotator(Visitor_Recursive[Token]):
    """This visitor adds numbers for intermediate result groups to each node.

    A node has a write group and a list of read groups.
    """

    def __init__(self) -> None:
        super().__init__()
        # Use dictionaries to store attributes for both Tree and Token objects
        self.write_groups: dict[int, int] = {}
        self.read_groups: dict[int, list[int]] = {}
        self.parent_write_group: dict[int, int] = {}  # node write group to parent write group
        self.write_groups_used: dict[int, int] = {}
        self.current_write_group = 0

    def apply(self, tree: ParseTree, parallel: bool = False) -> None:
        """Apply the visitor to the parse tree.

        For parallel processing, col_op is treated as a disjunction to
        allow for parallel exceution of percentile predicates.

        Args:
            tree: The parse tree to visit.
            parallel: True if the query will be excuted in parallel.
        """
        self.parallel = parallel
        self.visit_topdown(tree)

    def _create_group_id(self) -> int:
        """Create a new group ID."""
        logger.trace("new group id: {}", self.current_write_group + 1)
        self.current_write_group += 1
        return self.current_write_group

    def __default__(self, tree: ParseTree) -> None:  # noqa: PLW3201
        # Set attributes for all children using the parent's values
        logger.trace("Processing default node: {}", tree)
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            write_group = self.write_groups[id(tree)]
            read_groups = self.read_groups[id(tree)]

            for child in tree.children:
                # Store in our dictionaries rather than on the objects directly
                self.write_groups[id(child)] = write_group
                self.read_groups[id(child)] = read_groups
                logger.trace(
                    "Child {} has write group {} and read group {}",
                    child,
                    write_group,
                    read_groups,
                )
        else:
            raise ValueError(f"Node {tree} does not have write or read groups")

    def query(self, tree: ParseTree) -> None:
        logger.trace("Processing query node: {}", tree)
        # Set attributes for query node and children
        self.write_groups[id(tree)] = 0
        self.read_groups[id(tree)] = [0]
        self.parent_write_group[0] = 0
        self.write_groups_used[0] = 0

        # Set same attributes for all children
        for child in tree.children:
            self.write_groups[id(child)] = 0
            self.read_groups[id(child)] = [0]

    def conjunction(self, tree: ParseTree) -> None:
        logger.trace("Processing conjunction node: {}", tree)
        # For conjunction, all children read and write to the same groups
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            write_group = self.write_groups[id(tree)]
            read_group = self.read_groups[id(tree)]

            for child in tree.children:
                self.write_groups[id(child)] = write_group
                self.read_groups[id(child)] = read_group
                self.parent_write_group[write_group] = write_group
        else:
            raise ValueError("Node {} does not have write or read groups", tree)

    def disjunction(self, tree: ParseTree) -> None:
        logger.trace("Processing disjunction node: {}", tree)
        # For disjunction, give each child a new write group and add to read groups
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            parent_write_group = self.write_groups[id(tree)]
            parent_read_groups = self.read_groups[id(tree)].copy()

            for child in tree.children:
                current_write_group = self._create_group_id()
                self.write_groups_used[current_write_group] = 0
                self.write_groups[id(child)] = current_write_group
                self.read_groups[id(child)] = [current_write_group, *parent_read_groups]
                self.parent_write_group[current_write_group] = parent_write_group
        else:
            raise ValueError("Node {} does not have write or read groups", tree)

    def negation(self, tree: ParseTree) -> None:
        logger.trace("Processing negation node: {}", tree)
        # For negation, increment the write group and add to read groups
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            parent_group = self.write_groups[id(tree)]
            new_group = self._create_group_id()
            read_group = self.read_groups[id(tree)].copy()
            read_groups = [new_group, *read_group]
            self.parent_write_group[new_group] = parent_group
            self.write_groups_used[new_group] = 0

            for child in tree.children:
                self.write_groups[id(child)] = new_group
                self.read_groups[id(child)] = read_groups

        else:
            raise ValueError("Node {} does not have write or read groups", tree)

    def col_op(self, tree: ParseTree) -> None:
        # Set attributes for all children using the parent's values
        logger.trace("Processing col node: {}", tree)
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            if self.parallel:
                # For parallel processing, treat col_op as a disjunction
                parent_write_group = self.write_groups[id(tree)]
                parent_read_groups = self.read_groups[id(tree)].copy()

                for child in tree.children:
                    current_write_group = self._create_group_id()
                    self.write_groups_used[current_write_group] = 0
                    self.write_groups[id(child)] = current_write_group
                    self.read_groups[id(child)] = [current_write_group, *parent_read_groups]
                    self.parent_write_group[current_write_group] = parent_write_group
            else:
                # For sequential processing, all children read and write to the same groups
                write_group = self.write_groups[id(tree)]
                read_groups = self.read_groups[id(tree)]
                self.write_groups_used[write_group] = 0

                for child in tree.children:
                    # Store in our dictionaries rather than on the objects directly
                    self.write_groups[id(child)] = write_group
                    self.read_groups[id(child)] = read_groups
                    logger.trace(
                        "Child {} has write group {} and read group {}",
                        child,
                        write_group,
                        read_groups,
                    )
        else:
            raise ValueError(f"Node {tree} does not have write or read groups")

    def percentile_op(self, tree: ParseTree) -> None:
        # Set attributes for all children using the parent's values
        logger.trace("Processing percentile node: {}", tree)
        if id(tree) in self.write_groups and id(tree) in self.read_groups:
            write_group = self.write_groups[id(tree)]
            read_groups = self.read_groups[id(tree)]

            for read_group in read_groups:
                if read_group not in self.write_groups_used:
                    raise ValueError(f"Read group {read_group} not found in write groups")
                self.write_groups_used[read_group] += 1

            for child in tree.children:
                # Store in our dictionaries rather than on the objects directly
                self.write_groups[id(child)] = write_group
                self.read_groups[id(child)] = read_groups
                logger.trace(
                    "Child {} has write group {} and read group {}",
                    child,
                    write_group,
                    read_groups,
                )
        else:
            raise ValueError(f"Node {tree} does not have write or read groups")


def exceeds_filtering_limit(
    ids: DocumentArray | ColumnArray,
    id_type: Literal["num_hist_ids", "num_col_ids", "num_doc_ids"],
    fainder_mode: FainderMode,
    num_workers: int,
) -> bool:
    """Check if the number of IDs exceeds the filtering limit for the current mode."""
    return ids.size > get_filtering_stop_point(fainder_mode, num_workers, id_type)


def is_doc_result(val: Sequence[Any]) -> TypeGuard[Sequence[DocResult]]:
    """Check if a list contains document results (document IDs and highlights)."""
    return all(isinstance(item, tuple) for item in val)


def merge_highlights(
    left: Highlights,
    right: Highlights,
    doc_ids: DocumentArray,
    doc_to_cols: list[NDArray[np.uint32]],
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
    col_highlights = union_arrays(left[1], right[1])
    col_highlights = intersect_arrays(col_highlights, doc_to_col_ids(doc_ids, doc_to_cols))

    return doc_highlights, col_highlights


def intersect_arrays(a: DocumentArray, b: DocumentArray) -> DocumentArray:
    mask = np.isin(a, b)
    return a[mask]


def union_arrays(a: DocumentArray, b: DocumentArray) -> DocumentArray:
    return np.union1d(a, b)


def reduce_arrays(
    arrays: Sequence[TArray],
    operator: Literal["and", "or"],
) -> TArray:
    if operator == "and":
        intersection = arrays[0]
        for arr in arrays[1:]:
            intersection = np.intersect1d(intersection, arr, assume_unique=True)
        return intersection.view(type(arrays[0]))
    if operator == "or":
        union = arrays[0]
        for arr in arrays[1:]:
            union = np.union1d(union, arr)
        return union.view(type(arrays[0]))
    raise ValueError(f"Invalid operator: {operator}")


def negate_array(
    item: TArray,
    number_of_ids: int,
) -> TArray:
    # Create a mask for the negation
    dtype = item.dtype
    mask = np.isin(np.arange(number_of_ids), item, invert=True)
    result = np.arange(number_of_ids, dtype=dtype)[mask]
    return result.view(type(item))


def junction(
    items: Sequence[TResult],
    operator: Literal["and", "or"],
    enable_highlighting: bool = False,
    doc_to_cols: list[NDArray[np.uint32]] | None = None,
) -> TResult:
    """Combine query results using a junction operator (AND/OR)."""
    if len(items) < 2:  # noqa: PLR2004
        raise ValueError("Junction must have at least two items")

    # Items contains document results (i.e., DocResult)
    if is_doc_result(items):
        if enable_highlighting and doc_to_cols is not None:
            # Initialize result with first item
            doc_ids: DocumentArray = items[0][0]
            highlights: Highlights = items[0][1]

            # Merge all other items
            for item in items[1:]:
                if operator == "and":
                    doc_ids = intersect_arrays(doc_ids, item[0])
                else:
                    doc_ids = union_arrays(doc_ids, item[0])
                highlights = merge_highlights(highlights, item[1], doc_ids, doc_to_cols)

            return doc_ids, highlights  # type: ignore[return-value]
        doc_ids_list = [item[0] for item in items]
        return reduce_arrays(doc_ids_list, operator), ({}, np.array([], dtype=np.uint32))  # type: ignore[return-value]

    # Items contains column results (i.e., ColResult)
    return reduce_arrays(items, operator)  # type: ignore[type-var]
