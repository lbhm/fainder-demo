from typing import Literal

import numpy as np
from numpy.typing import NDArray

class Index:
    def __init__(self, space: Literal["l2", "ip", "cosine"], dim: int) -> None: ...
    def init_index(
        self,
        max_elements: int,
        M: int = 16,  # noqa: N803
        ef_construction: int = 200,
        random_seed: int = 100,
        allow_replace_delete: bool = False,
    ) -> None: ...
    def add_items(
        self,
        data: NDArray[np.float32],
        ids: NDArray[np.uint64],
        num_threads: int = -1,
        replace_deleted: bool = False,
    ) -> None: ...
    def set_ef(self, ef: int) -> None: ...
    def knn_query(
        self,
        data: NDArray[np.float32],
        k: int = 1,
        num_threads: int = -1,
        filter: NDArray[np.uint64] | None = None,  # noqa: A002
    ) -> tuple[NDArray[np.uint64], NDArray[np.float32]]: ...
    def load_index(
        self, path_to_index: str, max_elements: int = 0, allow_replace_delete: bool = False
    ) -> None: ...
    def save_index(self, path_to_index: str) -> None: ...
