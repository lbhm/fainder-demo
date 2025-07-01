from typing import Literal, TypedDict

from backend.config import FainderMode


class FilteringStopPointsConfig(TypedDict):
    """Sizes at which point to stop prefiltering per Fainder mode."""

    num_doc_ids: int
    num_col_ids: int
    num_hist_ids: int


# coefficients from linear model for pp result size
INTERCEPT = 5.776e6
COEF_LOG_THRESHOLD = 3.575e5
COEF_PERCENTILE = -9.344e5

FILTERING_STOP_POINTS: dict[FainderMode, dict[int, FilteringStopPointsConfig]] = {
    FainderMode.LOW_MEMORY: {
        0: {
            "num_doc_ids": 1000,
            "num_col_ids": 10000,
            "num_hist_ids": 10000,
        },
    },
    FainderMode.FULL_PRECISION: {
        0: {
            "num_doc_ids": 1000,
            "num_col_ids": 10000,
            "num_hist_ids": 10000,
        },
    },
    FainderMode.FULL_RECALL: {
        0: {
            "num_doc_ids": 1000,
            "num_col_ids": 10000,
            "num_hist_ids": 10000,
        },
    },
    FainderMode.EXACT: {
        0: {
            "num_doc_ids": 30000,
            "num_col_ids": 900000,
            "num_hist_ids": 900000,
        },
        5: {
            "num_doc_ids": 75000,
            "num_col_ids": 3000000,
            "num_hist_ids": 3000000,
        },
        11: {
            "num_doc_ids": 75000,
            "num_col_ids": 3000000,
            "num_hist_ids": 3000000,
        },
        27: {
            "num_doc_ids": 75000,
            "num_col_ids": 3000000,
            "num_hist_ids": 3000000,
        },
    },
}


def get_filtering_stop_point(
    mode: FainderMode,
    num_workers: int,
    filter_type: Literal["num_doc_ids", "num_col_ids", "num_hist_ids"],
) -> int:
    """Get the filtering stop point for a given Fainder mode and number of workers."""
    if mode not in FILTERING_STOP_POINTS:
        raise ValueError(f"Invalid Fainder mode: {mode}")

    if num_workers not in FILTERING_STOP_POINTS[mode]:
        # get nearest smaller key
        available_keys = sorted(FILTERING_STOP_POINTS[mode].keys())
        for key in reversed(available_keys):
            if key <= num_workers:
                num_workers = key
                break
        else:
            raise ValueError(f"No available stop points for {mode} with {num_workers} workers")

    stop_points = FILTERING_STOP_POINTS[mode][num_workers]

    if filter_type not in stop_points:
        raise ValueError(f"Invalid type: {filter_type}")

    return stop_points[filter_type]
