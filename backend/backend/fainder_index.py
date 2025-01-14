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

    def search(
        self,
        percentile: float,
        comparison: str,
        reference: float,
        hist_filter: set[np.uint32] | None = None,
    ) -> set[np.uint32]:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in ["ge", "gt", "le", "lt"]:
            raise PredicateError(f"{percentile};{comparison};{reference}")

        hist_filter_list = [int(x) for x in hist_filter] if hist_filter else None

        # Predicate evaluation
        query: PercentileQuery = (percentile, comparison, reference)  # type: ignore
        results, runtime = run(
            self.index,
            queries=[query],
            input_type="index",
            index_mode="recall",
            hist_filter=hist_filter_list,
        )
        result = results[0]
        logger.debug(f"Results: {result}")
        logger.info(f"Query '{query}' returned {len(result)} histograms in {runtime:.2f} seconds.")

        return result
