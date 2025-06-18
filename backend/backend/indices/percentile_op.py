import atexit
import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from fainder.execution.new_runner import run_approx, run_exact, run_exact_parallel
from fainder.execution.parallel_processing import FainderChunkLayout, ParallelHistogramProcessor
from fainder.utils import load_input
from loguru import logger

from backend.config import ColumnArray, FainderError, FainderMode

if TYPE_CHECKING:
    import numpy as np
    from fainder.typing import Histogram
    from fainder.typing import PercentileIndex as PctlIndex
    from fainder.typing import PercentileQuery as PctlQuery
    from numpy.typing import NDArray


class FainderIndex:
    def __init__(
        self,
        rebinning_paths: dict[str, Path] | None,
        conversion_paths: dict[str, Path] | None,
        histogram_path: Path | None,
        num_workers: int = (os.cpu_count() or 1) - 1,
        num_chunks: int = (os.cpu_count() or 1) - 1,
        chunk_layout: FainderChunkLayout = FainderChunkLayout.ROUND_ROBIN,
    ) -> None:
        self.rebinning_indexes: (
            dict[str, tuple[list[PctlIndex], list[NDArray[np.float64]]]] | None
        ) = None
        self.conversion_indexes: (
            dict[str, tuple[list[PctlIndex], list[NDArray[np.float64]]]] | None
        ) = None
        self.hists: list[tuple[np.uint32, Histogram]] | None = None

        if histogram_path is not None and histogram_path.exists():
            logger.info(f"Loading histograms from {histogram_path}")
            self.hists = load_input(histogram_path, "histograms")

        # load rebinning indexes
        if rebinning_paths:
            self.rebinning_indexes = {}
            for key, path in rebinning_paths.items():
                if path.exists():
                    logger.info(f"Loading rebinning index from {path}")
                    self.rebinning_indexes[key] = load_input(path, "rebinning index")
                else:
                    logger.warning(f"Rebinning index path {path} does not exist")
        else:
            logger.warning("No rebinning paths provided, rebinning index will not be loaded")
            self.rebinning_indexes = None

        # load conversion indexes
        if conversion_paths:
            self.conversion_indexes = {}
            for key, path in conversion_paths.items():
                if path.exists():
                    logger.info(f"Loading conversion index from {path}")
                    self.conversion_indexes[key] = load_input(path, "conversion index")
                else:
                    logger.warning(f"Conversion index path {path} does not exist")
        else:
            logger.warning("No conversion paths provided, conversion index will not be loaded")
            self.conversion_indexes = None

        self.parallel = num_workers > 1

        self.parallel_processor: ParallelHistogramProcessor | None = None

        if self.parallel and histogram_path is not None:
            # If parallel processing is enabled and histogram path is available,
            logger.info(f"Initializing parallel processor with histograms from: {histogram_path}")
            self.parallel_processor = ParallelHistogramProcessor(
                histogram_path=histogram_path,
                num_workers=num_workers,
                num_chunks=num_chunks,
                chunk_layout=chunk_layout,
            )

        atexit.register(self._cleanup_parallel_processor)

    def _cleanup_parallel_processor(self) -> None:
        """Clean up parallel processor when the program exits."""
        if self.parallel_processor is not None:
            logger.info("Shutting down parallel processor on exit")
            self.parallel_processor.shutdown()
            self.parallel_processor = None

    def search(  # noqa: C901
        self,
        percentile: float,
        comparison: str,
        reference: float,
        fainder_mode: FainderMode,
        index_name: str,
        hist_filter: ColumnArray | None = None,
    ) -> ColumnArray:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in {"ge", "gt", "le", "lt"}:
            raise FainderError(
                f"Invalid percentile predicate: {percentile};{comparison};{reference}"
            )

        result: ColumnArray

        query: PctlQuery = (percentile, comparison, reference)  # type: ignore[assignment]
        match fainder_mode:
            case FainderMode.LOW_MEMORY:
                if self.rebinning_indexes is None:
                    raise FainderError("Rebinning index must be loaded for low_memory mode.")

                rebinning_index = self.rebinning_indexes.get(index_name)
                if rebinning_index is None:
                    raise FainderError(f"Index '{index_name}' not found in rebinning indexes.")

                result, runtime = run_approx(
                    fainder_index=rebinning_index,
                    query=query,
                    index_mode="recall",
                    id_filter=hist_filter,
                )
            case FainderMode.FULL_PRECISION:
                if self.conversion_indexes is None:
                    raise FainderError("Conversion index must be loaded for full_precision mode.")

                conversion_index = self.conversion_indexes.get(index_name)
                if conversion_index is None:
                    raise FainderError(f"Index '{index_name}' not found in conversion indexes.")

                result, runtime = run_approx(
                    fainder_index=conversion_index,
                    query=query,
                    index_mode="precision",
                    id_filter=hist_filter,
                )
            case FainderMode.FULL_RECALL:
                if self.conversion_indexes is None:
                    raise FainderError("Conversion index must be loaded for full_recall mode.")

                conversion_index = self.conversion_indexes.get(index_name)
                if conversion_index is None:
                    raise FainderError(f"Index '{index_name}' not found in conversion indexes.")

                result, runtime = run_approx(
                    fainder_index=conversion_index,
                    query=query,
                    index_mode="recall",
                    id_filter=hist_filter,
                )
            case FainderMode.EXACT:
                if not self.parallel:
                    if self.conversion_indexes is None or self.hists is None:
                        raise FainderError(
                            "Conversion index and histograms must be loaded for exact mode."
                        )
                    conversion_index = self.conversion_indexes.get(index_name)
                    if conversion_index is None:
                        raise FainderError(
                            f"Index '{index_name}' not found in conversion indexes."
                        )

                    result, runtime = run_exact(
                        fainder_index=conversion_index,
                        hists=self.hists,
                        query=query,
                        id_filter=hist_filter,
                    )
                else:
                    if self.conversion_indexes is None:
                        raise FainderError("Conversion index must be loaded for exact mode.")

                    conversion_index = self.conversion_indexes.get(index_name)
                    if conversion_index is None:
                        raise FainderError(
                            f"Index '{index_name}' not found in conversion indexes."
                        )

                    if self.parallel_processor is None:
                        raise FainderError(
                            "Parallel processor is not initialized. "
                            "Cannot run exact mode in parallel."
                        )

                    result, runtime = run_exact_parallel(
                        fainder_index=conversion_index,
                        query=query,
                        parallel_processor=self.parallel_processor,
                        id_filter=hist_filter,
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
