from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from fainder.execution.runner import run
from fainder.utils import load_input
from loguru import logger

from backend.config import Metadata, PercentileError

if TYPE_CHECKING:
    from fainder.typing import PercentileIndex, PercentileQuery
    from numpy.typing import NDArray


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
            raise PercentileError(f"{percentile};{comparison};{reference}")

        filter_array = np.array(list(hist_filter), dtype=np.uint32) if hist_filter else None

        # Predicate evaluation
        query: PercentileQuery = (percentile, comparison, reference)  # type: ignore
        results, runtime = run(
            self.index,
            queries=[query],
            input_type="index",
            index_mode="recall",
            hist_filter=filter_array,
        )
        result = results[0]
        logger.debug(f"Results: {result}")
        logger.info(f"Query '{query}' returned {len(result)} histograms in {runtime:.2f} seconds.")

        return result
