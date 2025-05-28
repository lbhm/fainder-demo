from typing import TypedDict

from backend.config import FainderMode


class FilteringStopPointsConfig(TypedDict):
    """Sizes at which point to stop prefiltering per Fainder mode."""

    num_doc_ids: int
    num_col_ids: int
    num_hist_ids: int


FILTERING_STOP_POINTS: dict[FainderMode, FilteringStopPointsConfig] = {
    FainderMode.LOW_MEMORY: {
        "num_doc_ids": 50000,
        "num_col_ids": 500000,
        "num_hist_ids": 500000,
    },
    FainderMode.FULL_PRECISION: {
        "num_doc_ids": 50000,
        "num_col_ids": 500000,
        "num_hist_ids": 500000,
    },
    FainderMode.FULL_RECALL: {
        "num_doc_ids": 50000,
        "num_col_ids": 500000,
        "num_hist_ids": 500000,
    },
    FainderMode.EXACT: {
        "num_doc_ids": 100000,
        "num_col_ids": 1000000,
        "num_hist_ids": 1000000,
    },
}
