import logging
import os
import sys
import warnings
from enum import StrEnum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

import numpy as np
from fainder.execution.parallel_processing import FainderChunkLayout
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

from backend.utils import load_json

if TYPE_CHECKING:
    from types import FrameType

DocumentHighlights = dict[int | np.uint32, dict[str, str]]
ColumnHighlights = NDArray[np.uint32]
Highlights = tuple[DocumentHighlights, ColumnHighlights]
IntegerArray = Annotated[
    NDArray[np.uint32],
    BeforeValidator(lambda data: np.array(data, dtype=np.uint32)),
    PlainSerializer(lambda data: data.tolist()),
]
DocumentArray = NDArray[np.uint32]
ColumnArray = NDArray[np.uint32]


class ExecutorType(StrEnum):
    """Enum representing different executor types for query execution."""

    SIMPLE = auto()
    PREFILTERING = auto()
    THREADED = auto()
    THREADED_PREFILTERING = auto()


class CroissantStoreType(StrEnum):
    DICT = auto()
    FILE = auto()


class FainderMode(StrEnum):
    LOW_MEMORY = auto()
    FULL_PRECISION = auto()
    FULL_RECALL = auto()
    EXACT = auto()


class Metadata(BaseModel):
    doc_to_cols: list[IntegerArray]
    doc_to_path: list[str]
    col_to_doc: IntegerArray
    name_to_vector: dict[str, int]
    vector_to_cols: dict[int, set[int]]
    num_hists: int

    model_config = ConfigDict(arbitrary_types_allowed=True)


class FainderConfig(BaseModel):
    n_clusters: int
    bin_budget: int
    alpha: float
    transform: Literal["standard", "robust", "quantile", "power"] | None = None
    algorithm: Literal["agglomerative", "hdbscan", "kmeans"] = "kmeans"
    rebinning_file: Path
    conversion_file: Path


class FainderConfigs(BaseModel):
    configs: dict[str, FainderConfig]


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
    fainder_chunk_layout: FainderChunkLayout = FainderChunkLayout.CONTIGUOUS
    fainder_num_workers: int = (os.cpu_count() or 1) - 1
    fainder_num_chunks: int = (os.cpu_count() or 1) - 1

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

    _fainder_configs: FainderConfigs | None = None

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

    @computed_field  # type: ignore[prop-decorator]
    @property
    def fainder_configs(self) -> FainderConfigs:
        """Load Fainder configurations from the JSON file with caching."""
        if self._fainder_configs is None:
            config_data = load_json(self.fainder_config_path)
            self._fainder_configs = FainderConfigs(configs=config_data)
        return self._fainder_configs
        return FainderConfigs(configs=config_data)

    def fainder_rebinning_path_for_config(self, config_name: str) -> Path:
        config = self.fainder_configs.configs.get(config_name)
        if not config:
            raise ValueError(f"Configuration '{config_name}' not found in Fainder configs.")
        return self.fainder_path / config.rebinning_file

    def fainder_conversion_path_for_config(self, config_name: str) -> Path:
        config = self.fainder_configs.configs.get(config_name)
        if not config:
            raise ValueError(f"Configuration '{config_name}' not found in Fainder configs.")
        return self.fainder_path / config.conversion_file


class QueryRequest(BaseModel):
    query: str
    page: int = 1
    per_page: int = 10
    fainder_mode: FainderMode = FainderMode.LOW_MEMORY
    result_highlighting: bool = False
    fainder_index_name: str = "default"


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
