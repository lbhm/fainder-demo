from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from fainder.execution.new_runner import run_approx, run_exact
from fainder.utils import load_input
from loguru import logger

from backend.config import FainderError, FainderMode, Metadata

if TYPE_CHECKING:
    from fainder.typing import Histogram
    from fainder.typing import PercentileIndex as PctlIndex
    from fainder.typing import PercentileQuery as PctlQuery
    from numpy.typing import NDArray


class FainderIndex:
    def __init__(
        self,
        metadata: Metadata,
        rebinning_path: Path | None,
        conversion_path: Path | None,
        histogram_path: Path | None,
    ) -> None:
        self.doc_to_cols = metadata.doc_to_cols
        self.col_to_doc = metadata.col_to_doc
        self.col_to_hist = metadata.col_to_hist
        self.hist_to_col = metadata.hist_to_col

        self.rebinning_index: tuple[list[PctlIndex], list[NDArray[np.float64]]] | None = (
            load_input(rebinning_path, "rebinning index") if rebinning_path else None
        )
        self.conversion_index: tuple[list[PctlIndex], list[NDArray[np.float64]]] | None = (
            load_input(conversion_path, "conversion index") if conversion_path else None
        )
        self.hists: list[tuple[np.uint32, Histogram]] | None = (
            load_input(histogram_path, "histograms") if histogram_path else None
        )

    def update(
        self,
        metadata: Metadata,
        rebinning_path: Path | None,
        conversion_path: Path | None,
        histogram_path: Path | None,
    ) -> None:
        self.doc_to_cols = metadata.doc_to_cols
        self.col_to_doc = metadata.col_to_doc
        self.col_to_hist = metadata.col_to_hist
        self.hist_to_col = metadata.hist_to_col

        self.rebinning_index = (
            load_input(rebinning_path, "rebinning index") if rebinning_path else None
        )
        self.conversion_index = (
            load_input(conversion_path, "conversion index") if conversion_path else None
        )
        self.hists = load_input(histogram_path, "histograms") if histogram_path else None

    def search(
        self,
        percentile: float,
        comparison: str,
        reference: float,
        fainder_mode: FainderMode,
        hist_filter: set[np.uint32] | None = None,
    ) -> set[np.uint32]:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in ["ge", "gt", "le", "lt"]:
            raise FainderError(
                f"Invalid percentile predicate: {percentile};{comparison};{reference}"
            )

        id_filter = np.array(list(hist_filter), dtype=np.uint32) if hist_filter else None

        # Predicate evaluation
        query: PctlQuery = (percentile, comparison, reference)  # type: ignore
        match fainder_mode:
            case FainderMode.LOW_MEMORY:
                if self.rebinning_index is None:
                    raise FainderError("Rebinning index must be loaded for low_memory mode.")
                result, runtime = run_approx(
                    fainder_index=self.rebinning_index,
                    query=query,
                    index_mode="recall",
                    id_filter=id_filter,
                )
            case FainderMode.FULL_PRECISION:
                if self.conversion_index is None:
                    raise FainderError("Conversion index must be loaded for full_precision mode.")
                result, runtime = run_approx(
                    fainder_index=self.conversion_index,
                    query=query,
                    index_mode="precision",
                    id_filter=id_filter,
                )
            case FainderMode.FULL_RECALL:
                if self.conversion_index is None:
                    raise FainderError("Conversion index must be loaded for full_recall mode.")
                result, runtime = run_approx(
                    fainder_index=self.conversion_index,
                    query=query,
                    index_mode="recall",
                    id_filter=id_filter,
                )
            case FainderMode.EXACT:
                if self.conversion_index is None or self.hists is None:
                    raise FainderError(
                        "Conversion index and histograms must be loaded for exact mode."
                    )
                result, runtime = run_exact(
                    fainder_index=self.conversion_index,
                    hists=self.hists,
                    query=query,
                    id_filter=id_filter,
                )

        logger.trace(f"Results: {result}")
        logger.info(
            f"Query '{query}' ({fainder_mode} mode) returned {len(result)} histograms in "
            f"{runtime:.2f} seconds."
        )

        return result
