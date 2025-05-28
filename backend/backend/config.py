import logging
import os
import sys
import warnings
from enum import Enum
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
    fainder_default: str = "default"

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
        return self.fainder_path / f"{config_name}_rebinning.zst"

    def fainder_conversion_path_for_config(self, config_name: str) -> Path:
        return self.fainder_path / f"{config_name}_conversion.zst"


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
    """Intercepts standard logging and routes it to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        """Route a record to loguru."""
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Traverse the stack to find the actual caller
        frame: FrameType | None
        frame, depth = logging.currentframe(), 1
        while frame:
            frame = frame.f_back
            if frame and frame.f_globals.get("__name__") not in {
                "logging",
                "loguru._handler",
                "loguru._logger",
            }:
                break
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(level: str) -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format=(
            "<green>{time:HH:mm:ss}</green> | <level>{level:.1}</level> | {name}:{line} | "
            "<level>{message}</level>"
        ),
        level=level,
    )

    # Intercept all standard logging
    logging.root.handlers = [InterceptHandler()]
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # Redirect warnings to Loguru
    warnings.showwarning = lambda msg, cat, fn, ln, *args: logger.warning(  # pyright: ignore[reportUnknownLambdaType]
        f"{cat.__name__}: {msg} ({fn}:{ln})"  # pyright: ignore[reportUnknownMemberType]
    )
