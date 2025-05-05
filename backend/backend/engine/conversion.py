from numpy import uint32
from numpy.typing import NDArray

from backend.config import COLUMN_RESULTS


def doc_to_col_ids(doc_ids: set[int], doc_to_cols: dict[int, set[int]]) -> COLUMN_RESULTS:
    return {
        uint32(col_id)
        for doc_id in doc_ids
        if doc_id in doc_to_cols
        for col_id in doc_to_cols[doc_id]
    }


def col_to_doc_ids(col_ids: COLUMN_RESULTS, col_to_doc: NDArray[uint32]) -> set[int]:
    return {int(col_to_doc[col_id]) for col_id in col_ids}


def col_to_hist_ids(col_ids: COLUMN_RESULTS, col_to_hist: dict[int, int]) -> COLUMN_RESULTS:
    return {uint32(col_to_hist[int(col_id)]) for col_id in col_ids if int(col_id) in col_to_hist}


def hist_to_col_ids(hist_ids: COLUMN_RESULTS, hist_to_col: NDArray[uint32]) -> COLUMN_RESULTS:
    return {hist_to_col[hist_id] for hist_id in hist_ids}
