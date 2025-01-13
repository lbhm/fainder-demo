from pathlib import Path

import numpy as np
from fainder.execution.runner import run
from fainder.typing import PercentileIndex, PercentileQuery
from fainder.utils import load_input
from loguru import logger
from numpy.typing import NDArray

from backend.config import Metadata, PredicateError


class FainderIndex:
    def __init__(self, path: Path, metadata: Metadata) -> None:
        self.index: tuple[list[PercentileIndex], list[NDArray[np.float64]]] = load_input(
            path, "index"
        )
        self.doc_to_cols = metadata.doc_to_cols
        self.col_to_doc = metadata.col_to_doc
        self.col_to_hist = metadata.col_to_hist
        self.hist_to_col = metadata.hist_to_col

        # NOTE: These two mappings can be removed once we have a dedicated column operator
        self.name_to_vector = metadata.name_to_vector
        self.vector_to_cols = metadata.vector_to_cols

    def search(
        self,
        percentile: float,
        comparison: str,
        reference: float,
        identifier: str | None = None,
        doc_filter: set[int] | None = None,
    ) -> set[int]:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in ["ge", "gt", "le", "lt"]:
            raise PredicateError(f"{percentile};{comparison};{reference};{identifier}")

        # Filter creation
        hist_filter: set[int] | None = None
        if doc_filter:
            if len(doc_filter) == 0:
                return set()
            hist_filter = {
                self.col_to_hist[col]
                for doc in doc_filter
                for col in self.doc_to_cols[doc]
                if col in self.col_to_hist
            }
        if identifier:
            hist_ids = self._get_matching_histograms(identifier)
            if hist_ids is None:
                return set()
            if hist_filter:
                hist_filter &= hist_ids
            else:
                hist_filter = hist_ids

        # Predicate evaluation
        query: PercentileQuery = (percentile, comparison, reference)  # type: ignore
        results, runtime = run(
            self.index,
            queries=[query],
            input_type="index",
            index_mode="recall",
            hist_filter=list(hist_filter) if hist_filter else None,
        )
        result = results[0]
        logger.info(f"Query '{query}' returned {len(result)} histograms in {runtime:.2f} seconds.")

        return {self.col_to_doc[self.hist_to_col[int(hist)]] for hist in result}

    def _get_matching_histograms(self, identifier: str) -> set[int] | None:
        """Return the set of histogram IDs whose column name matches the given identifier."""
        # TODO: Add fuzzy and semantic search functionality to this function
        vector_id = self.name_to_vector.get(identifier, None)
        if vector_id:
            return self.vector_to_cols.get(vector_id, None)
        return None
