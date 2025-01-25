from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, DirectoryPath, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Metadata(BaseModel):
    doc_to_cols: dict[int, set[int]]
    col_to_doc: dict[int, int]
    col_to_hist: dict[int, int]
    hist_to_col: dict[int, int]
    name_to_vector: dict[str, int]
    vector_to_cols: dict[int, set[int]]


class Settings(BaseSettings):
    # Path settings
    data_dir: DirectoryPath
    collection_name: str
    croissant_dir: Path = Path("croissant")
    embedding_dir: Path = Path("embeddings")
    fainder_dir: Path = Path("fainder")
    metadata_file: Path = Path("metadata.json")

    # QueryEvaluator settings
    query_cache_size: int = 128
    highlights_cache_size: int = 128  # Add highlight cache size setting

    # Lucene settings
    lucene_host: str = "127.0.0.1"
    lucene_port: str = "8001"

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    @field_validator("metadata_file", mode="after")
    def metadata_file_type(cls, value: Path) -> Path:
        if value.suffix != ".json":
            raise ValueError("metadata_file must point to a .json file")
        return value

    @computed_field  # type: ignore[misc]
    @property
    def croissant_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.croissant_dir

    @computed_field  # type: ignore[misc]
    @property
    def embedding_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.embedding_dir

    @computed_field  # type: ignore[misc]
    @property
    def fainder_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.fainder_dir

    @computed_field  # type: ignore[misc]
    @property
    def hnsw_index_path(self) -> Path:
        return self.embedding_path / "index.bin"

    @computed_field  # type: ignore[misc]
    @property
    def rebinning_index_path(self) -> Path:
        return self.fainder_path / "rebinning.zst"

    @computed_field  # type: ignore[misc]
    @property
    def conversion_index_path(self) -> Path:
        return self.fainder_path / "conversion.zst"

    @computed_field  # type: ignore[misc]
    @property
    def metadata_path(self) -> Path:
        return self.data_dir / self.collection_name / self.metadata_file


class QueryRequest(BaseModel):
    query: str
    page: int = 1
    per_page: int = 10
    fainder_mode: Literal["low_memory", "full_precision", "full_recall", "exact"] = "low_memory"


class QueryResponse(BaseModel):
    """Response for a query request."""

    query: str
    results: list[dict[str, Any]]
    search_time: float
    result_count: int
    page: int
    total_pages: int  # Add highlights field


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


class PercentileError(Exception):
    pass
