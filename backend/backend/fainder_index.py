from pathlib import Path

import numpy as np
from fainder.execution.runner import run
from fainder.typing import PercentileIndex, PercentileQuery
from fainder.utils import load_input
from loguru import logger

from backend.config import PredicateError


class FainderIndex:
    def __init__(
        self, path: Path, hist_to_doc: dict[int, int], column_to_hists: dict[str, set[int]]
    ) -> None:
        self.index: PercentileIndex = load_input(path, "index")
        self.hist_to_doc = hist_to_doc
        self.column_to_hists = column_to_hists

    def search(
        self,
        percentile: float,
        comparison: str,
        reference: float,
        identifier: str | None = None,
        hist_filter: set[np.uint32] | None = None,
    ) -> set[np.uint32]:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in ["ge", "gt", "le", "lt"]:
            raise PredicateError(f"{percentile};{comparison};{reference};{identifier}")

        # Filter creation
        if identifier:
            hist_ids = self._get_matching_histograms(identifier)
            if hist_ids is None:
                return set()
            if hist_filter:
                hist_filter &= hist_ids
            else:
                hist_filter = hist_ids

        # Convert hist_filter to uint32 if it exists
        uint32_hist_filter = (
            {np.uint32(h) for h in hist_filter} if hist_filter is not None else None
        )

        # Predicate evaluation
        query: PercentileQuery = (percentile, comparison, reference)  # type: ignore
        results, runtime = run(
            self.index,
            queries=[query],
            input_type="index",
            hist_filter=uint32_hist_filter,
        )
        result = results[0]
        logger.info(f"Query '{query}' returned {len(result)} histograms in {runtime:.2f} seconds.")

        return result

    def _get_matching_histograms(self, identifier: str) -> set[np.uint32] | None:
        """Return the set of histogram IDs whose column name matches the given identifier."""
        # TODO: Add fuzzy and semantic search functionality to this function
        hist_set = self.column_to_hists.get(identifier, None)
        return {np.uint32(h) for h in hist_set} if hist_set is not None else None
