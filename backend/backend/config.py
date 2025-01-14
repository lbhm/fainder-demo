import json
import pickle
from pathlib import Path
from typing import Any

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
    data_dir: DirectoryPath
    collection_name: str
    croissant_dir: Path = Path("croissant")
    embedding_dir: Path = Path("embeddings")
    fainder_dir: Path = Path("fainder")
    metadata_file: Path = Path("metadata.json")

    lucene_host: str = "127.0.0.1"
    lucene_port: str = "8001"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @classmethod
    @field_validator("metadata_file", mode="after")
    def metadata_file_type(cls, value: Path) -> Path:
        if value.suffix not in {".json", ".pkl"}:
            raise ValueError("metadata_file must point to a .json or .pkl file")
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
    def metadata(self) -> Metadata:
        if self.metadata_file.suffix == ".json":
            with open(self.data_dir / self.collection_name / self.metadata_file, "r") as f:
                data = json.load(f)
        elif self.metadata_file.suffix == ".pkl":
            with open(self.data_dir / self.collection_name / self.metadata_file, "rb") as f:
                data = pickle.load(f)
        else:
            raise ValueError("Unsupported file type for metadata_path")

        return Metadata(**data)


class PercentileError(Exception):
    pass


class ColumnSearchError(Exception):
    pass


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]
