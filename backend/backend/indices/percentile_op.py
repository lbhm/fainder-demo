import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from fainder.execution.new_runner import run_approx, run_exact, run_exact_parallel
from fainder.execution.parallel_processing import ParallelHistogramProcessor
from fainder.utils import load_input
from loguru import logger

from backend.config import ColumnArray, FainderError, FainderMode

if TYPE_CHECKING:
    import numpy as np
    from fainder.typing import Histogram
    from fainder.typing import PercentileIndex as PctlIndex
    from fainder.typing import PercentileQuery as PctlQuery
    from numpy.typing import NDArray
import atexit


class FainderIndex:
    def __init__(
        self,
        rebinning_path: Path | None,
        conversion_path: Path | None,
        histogram_path: Path | None,
        parallel: bool = True,
        num_workers: int = os.cpu_count() or 1,
        contiguous: bool = True,
    ) -> None:
        self.rebinning_index: tuple[list[PctlIndex], list[NDArray[np.float64]]] | None = None
        self.conversion_index: tuple[list[PctlIndex], list[NDArray[np.float64]]] | None = None
        self.histogram_path: Path | None = histogram_path
        self.hists: list[tuple[np.uint32, Histogram]] | None = None
        self.parallel = parallel
        self.parallel_processor: ParallelHistogramProcessor | None = None

        atexit.register(self._cleanup_parallel_processor)

        self.update(
            rebinning_path=rebinning_path,
            conversion_path=conversion_path,
            histogram_path=histogram_path,
            parallel=parallel,
            num_workers=num_workers,
            contiguous=contiguous,
        )

    def _cleanup_parallel_processor(self) -> None:
        """Clean up parallel processor when the program exits."""
        if hasattr(self, "parallel_processor") and self.parallel_processor is not None:
            logger.info("Shutting down parallel processor on exit")
            self.parallel_processor.shutdown()
            self.parallel_processor = None

    def update(
        self,
        rebinning_path: Path | None,
        conversion_path: Path | None,
        histogram_path: Path | None,
        parallel: bool = True,
        num_workers: int = os.cpu_count() or 1,
        contiguous: bool = True,
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
            self.histogram_path = histogram_path
            self.hists = load_input(histogram_path, "histograms")
        elif histogram_path:
            logger.warning(f"Histogram path {histogram_path} does not exist")

        self.parallel = parallel

        # Clean up existing parallel processor if it exists
        if hasattr(self, "parallel_processor") and self.parallel_processor is not None:
            logger.info("Shutting down existing parallel processor")
            self.parallel_processor.shutdown()
            self.parallel_processor = None

        self.parallel_processor = None

        if parallel and histogram_path is not None:
            # If parallel processing is enabled and histogram path is available,
            logger.info(
                f"Initializing parallel processor with histograms from: {self.histogram_path}"
            )
            self.parallel_processor = ParallelHistogramProcessor(
                histogram_path=histogram_path,
                num_workers=num_workers,
                contiguous=contiguous,
            )

    def search(  # noqa: C901
        self,
        percentile: float,
        comparison: str,
        reference: float,
        fainder_mode: FainderMode,
        hist_filter: ColumnArray | None = None,
    ) -> ColumnArray:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in {"ge", "gt", "le", "lt"}:
            raise FainderError(
                f"Invalid percentile predicate: {percentile};{comparison};{reference}"
            )

        result: ColumnArray

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
                    id_filter=hist_filter,
                )
            case FainderMode.FULL_PRECISION:
                if self.conversion_index is None:
                    raise FainderError("Conversion index must be loaded for full_precision mode.")
                result, runtime = run_approx(
                    fainder_index=self.conversion_index,
                    query=query,
                    index_mode="precision",
                    id_filter=hist_filter,
                )
            case FainderMode.FULL_RECALL:
                if self.conversion_index is None:
                    raise FainderError("Conversion index must be loaded for full_recall mode.")
                result, runtime = run_approx(
                    fainder_index=self.conversion_index,
                    query=query,
                    index_mode="recall",
                    id_filter=hist_filter,
                )
            case FainderMode.EXACT:
                if hist_filter is not None or not self.parallel:
                    if self.conversion_index is None or self.hists is None:
                        raise FainderError(
                            "Conversion index and histograms must be loaded for exact mode."
                        )

                    result, runtime = run_exact(
                        fainder_index=self.conversion_index,
                        hists=self.hists,
                        query=query,
                        id_filter=hist_filter,
                    )
                else:
                    if self.conversion_index is None or self.histogram_path is None:
                        raise FainderError(
                            "Conversion index and histogram path must be loaded for exact mode."
                        )

                    if self.parallel_processor is None:
                        raise FainderError(
                            "Parallel processor is not initialized. "
                            "Cannot run exact mode in parallel."
                        )

                    result, runtime = run_exact_parallel(
                        fainder_index=self.conversion_index,
                        query=query,
                        parallel_processor=self.parallel_processor,
                    )

        logger.info(
            "Query '{}' ({} mode) returned {} histograms in {} seconds. With filter size: {}",
            query,
            fainder_mode,
            len(result),
            f"{runtime:.2f}",
            hist_filter.size if hist_filter is not None else "no filter",
        )

        return result
