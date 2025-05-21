import logging
import os
import sys
from collections.abc import Sequence
from enum import Enum
from itertools import chain
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

import numpy as np
from loguru import logger
from numpy.typing import NDArray
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    DirectoryPath,
    PlainSerializer,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from types import FrameType

DocumentHighlights = dict[int, dict[str, str]]
ColumnHighlights = set[np.uint32]
Highlights = tuple[DocumentHighlights, ColumnHighlights]
IntegerArray = Annotated[
    NDArray[np.uint32],
    BeforeValidator(lambda data: np.array(data, dtype=np.uint32)),
    PlainSerializer(lambda data: data.tolist()),
]


class ExecutorType(str, Enum):
    """Enum representing different executor types for query execution."""

    SIMPLE = "simple"
    PREFILTERING = "prefiltering"
    THREADED = "threaded"
    THREADED_PREFILTERING = "threaded_prefiltering"


class CroissantStoreType(str, Enum):
    DICT = "dict"
    FILE = "file"


class FainderMode(str, Enum):
    LOW_MEMORY = "low_memory"
    FULL_PRECISION = "full_precision"
    FULL_RECALL = "full_recall"
    EXACT = "exact"


class Metadata(BaseModel):
    doc_to_cols: dict[int, set[int]]
    doc_to_path: list[str]
    col_to_doc: IntegerArray
    name_to_vector: dict[str, int]
    vector_to_cols: dict[int, set[int]]
    num_hists: int

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Settings(BaseSettings):
    # Path settings
    data_dir: DirectoryPath
    collection_name: str
    croissant_dir: Path = Path("croissant")
    embedding_dir: Path = Path("embeddings")
    fainder_dir: Path = Path("fainder")
    tantivy_dir: Path = Path("tantivy")
    metadata_file: Path = Path("metadata.json")
    dataset_slug: str = "kaggleRef"

    # Croissant store settings
    croissant_store_type: CroissantStoreType = CroissantStoreType.DICT
    croissant_cache_size: int = 128

    # Engine settings
    query_cache_size: int = 128
    min_usability_score: float = 0.0
    rank_by_usability: bool = True
    executor_type: ExecutorType = ExecutorType.SIMPLE
    max_workers: int = os.cpu_count() or 1

    # Fainder settings
    fainder_n_clusters: int = 50
    fainder_bin_budget: int = 1000
    fainder_alpha: float = 1.0
    fainder_transform: Literal["standard", "robust", "quantile", "power"] | None = None
    fainder_cluster_algorithm: Literal["agglomerative", "hdbscan", "kmeans"] = "kmeans"

    # Embedding/HNSW settings
    use_embeddings: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = 32
    hnsw_ef_construction: int = 400
    hnsw_n_bidirectional_links: int = 64
    hnsw_ef: int = 50

    # Misc
    log_level: Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    @field_validator("metadata_file", mode="after")
    def metadata_file_type(cls, value: Path) -> Path:
        if value.suffix != ".json":
            raise ValueError("metadata_file must point to a .json file")
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def croissant_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.croissant_dir

    @computed_field  # type: ignore[prop-decorator]
    @property
    def embedding_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.embedding_dir

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tantivy_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.tantivy_dir

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fainder_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.fainder_dir

    @computed_field  # type: ignore[prop-decorator]
    @property
    def hnsw_index_path(self) -> Path:
        return self.embedding_path / "index.bin"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rebinning_index_path(self) -> Path:
        return self.fainder_path / "rebinning.zst"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def conversion_index_path(self) -> Path:
        return self.fainder_path / "conversion.zst"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def histogram_path(self) -> Path:
        return self.fainder_path / "histograms.zst"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def metadata_path(self) -> Path:
        return self.data_dir / self.collection_name / self.metadata_file

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fainder_config_path(self) -> Path:
        return self.fainder_path / "configs.json"

    def fainder_rebinning_path_for_config(self, config_name: str) -> Path:
        return self.fainder_path / f"rebinning_{config_name}.zst"

    def fainder_conversion_path_for_config(self, config_name: str) -> Path:
        return self.fainder_path / f"conversion_{config_name}.zst"


class QueryRequest(BaseModel):
    query: str
    page: int = 1
    per_page: int = 10
    fainder_mode: FainderMode = FainderMode.LOW_MEMORY
    result_highlighting: bool = False


class QueryResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]
    search_time: float
    result_count: int
    page: int
    total_pages: int


class MessageResponse(BaseModel):
    message: str


class CacheInfo(BaseModel):
    hits: int
    misses: int
    max_size: int | None
    curr_size: int


class ColumnSearchError(Exception):
    pass


class CroissantError(Exception):
    pass


class IndexingError(Exception):
    pass


class FainderError(Exception):
    pass


class FainderConfigRequest(BaseModel):
    config_name: str


class FainderConfigsResponse(BaseModel):
    configs: list[str]
    current: str


class InterceptHandler(logging.Handler):
    """Logs to loguru from Python logging module.

    See https://github.com/MatthewScholefield/loguru-logging-intercept"""

    def emit(self, record: logging.LogRecord) -> None:
        """Route a record to loguru."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Find caller from where the logged message originated
        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger_with_opts = logger.opt(depth=depth, exception=record.exc_info)
        try:
            logger_with_opts.log(level, record.getMessage())
        except Exception as e:
            safe_msg = getattr(record, "msg", None) or str(record)
            logger_with_opts.warning(
                f"Exception logging the following native logger message: {safe_msg}, {e}"
            )


def configure_logging(level: str, modules: Sequence[str] = ()) -> None:
    # TODO: Maybe move from loguru to standard logging (in case of performance problems)
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time:HH:mm:ss} | {level: >5} | {file}:{line} | <level>{message}</level>",
        level=level,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for logger_name in chain(("",), modules):
        if logger_name:
            # Undocumented way of getting a logger without creating it:
            mod_logger = logging.Logger.manager.loggerDict.get(logger_name)
        else:
            # Root logger is not contained in loggerDict
            mod_logger = logging.getLogger()
        if (mod_logger) and (isinstance(mod_logger, logging.Logger)):
            mod_logger.handlers = [InterceptHandler(level=0)]
            mod_logger.propagate = False
            logger.trace(f"InterceptHandler in place for logger {logger_name}")
        else:
            logger.debug(f"No logger found named {logger_name}")

    # NOTE: This is a helper to list all loggers in the system
    # for k, _ in logging.Logger.manager.loggerDict.items():
    #     if "transformer" in k or "torch" in k:
    #         continue
    #     print(k)
