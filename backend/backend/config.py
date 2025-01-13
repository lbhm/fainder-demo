import json
import pickle
from pathlib import Path
from typing import Any

from pydantic import BaseModel, DirectoryPath, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Metadata(BaseModel):
    doc_ids: set[int]
    column_to_hists: dict[str, set[int]]
    hist_to_doc: dict[int, int]
    doc_to_hists: dict[int, set[int]]  # TODO: Update names and type to uint32 if possible


class Settings(BaseSettings):
    data_dir: DirectoryPath
    collection_name: str
    croissant_dir: Path = Path("croissant")
    faider_dir: Path = Path("fainder")
    metadata_file: Path = Path("metadata.json")

    lucene_host: str = "127.0.0.1"
    lucene_port: str = "8001"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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
    def fainder_path(self) -> DirectoryPath:
        return self.data_dir / self.collection_name / self.faider_dir

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


class PredicateError(Exception):
    pass


class ColumnSearchError(Exception):
    pass


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    results: list[dict[str, Any]]
