from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from fainder.execution.new_runner import run_approx, run_exact
from fainder.utils import load_input
from loguru import logger

from backend.config import FainderError, FainderMode

if TYPE_CHECKING:
    from fainder.typing import Histogram
    from fainder.typing import PercentileIndex as PctlIndex
    from fainder.typing import PercentileQuery as PctlQuery
    from numpy.typing import NDArray


class FainderIndex:
    def __init__(
        self,
        rebinning_path: Path | None,
        conversion_path: Path | None,
        histogram_path: Path | None,
    ) -> None:
        self.rebinning_index: tuple[list[PctlIndex], list[NDArray[np.float64]]] | None = None
        self.conversion_index: tuple[list[PctlIndex], list[NDArray[np.float64]]] | None = None
        self.hists: list[tuple[np.uint32, Histogram]] | None = None

        # Load the indices if paths are provided
        self.update(rebinning_path, conversion_path, histogram_path)

    def update(
        self,
        rebinning_path: Path | None,
        conversion_path: Path | None,
        histogram_path: Path | None,
    ) -> None:
        """Update the Fainder indices with new files."""
        if rebinning_path and rebinning_path.exists():
            logger.info(f"Loading rebinning index from {rebinning_path}")
            self.rebinning_index = load_input(rebinning_path, "rebinning index")
        elif rebinning_path:
            logger.warning(f"Rebinning index path {rebinning_path} does not exist")

        if conversion_path and conversion_path.exists():
            logger.info(f"Loading conversion index from {conversion_path}")
            self.conversion_index = load_input(conversion_path, "conversion index")
        elif conversion_path:
            logger.warning(f"Conversion index path {conversion_path} does not exist")

        if histogram_path and histogram_path.exists():
            logger.info(f"Loading histograms from {histogram_path}")
            self.hists = load_input(histogram_path, "histograms")
        elif histogram_path:
            logger.warning(f"Histogram path {histogram_path} does not exist")

    def search(
        self,
        percentile: float,
        comparison: str,
        reference: float,
        fainder_mode: FainderMode,
        hist_filter: set[np.uint32] | None = None,
    ) -> set[np.uint32]:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in {"ge", "gt", "le", "lt"}:
            raise FainderError(
                f"Invalid percentile predicate: {percentile};{comparison};{reference}"
            )

        id_filter = np.array(list(hist_filter), dtype=np.uint32) if hist_filter else None

        # Predicate evaluation
        query: PctlQuery = (percentile, comparison, reference)  # type: ignore[assignment]
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
