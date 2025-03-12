import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import orjson
from loguru import logger

from backend.config import CroissantError, JsonEncoding

Document = dict[str, Any]


class CroissantStore(ABC):
    """Abstract base class for storing a collection of Croissant files."""

    def __init__(
        self,
        path: Path,
        dataset_slug: str,
        overwrite_docs: bool = False,
        json_encoding: JsonEncoding = JsonEncoding.orjson,
    ) -> None:
        self.path = path
        self.dataset_slug = dataset_slug
        self.overwrite_docs = overwrite_docs
        self.json_encoding = json_encoding

    def __getitem__(self, index: int) -> Document:
        return self.get_document(index)

    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def load_documents(self) -> None:
        """Load documents into the store."""

    @abstractmethod
    def get_document(self, doc_id: int) -> Document:
        """Get a document by ID."""

    def get_documents(self, doc_ids: list[int]) -> list[Document]:
        return [self.get_document(doc_id) for doc_id in doc_ids]

    @abstractmethod
    def add_document(self, doc: Document) -> None:
        """Add a new document to the store."""

    @abstractmethod
    def replace_documents(self, docs: dict[int, Document]) -> None:
        """Replace all documents in the store."""


class MemoryCroissantStore(CroissantStore):
    """Store a collection of Croissant files in memory."""

    def __init__(
        self,
        path: Path,
        dataset_slug: str,
        overwrite_docs: bool = False,
        json_encoding: JsonEncoding = JsonEncoding.orjson,
    ) -> None:
        super().__init__(path, dataset_slug, overwrite_docs, json_encoding)
        self.documents: dict[int, Document] = {}

    def __len__(self) -> int:
        return len(self.documents)

    def load_documents(self) -> None:
        self.documents.clear()
        for file in self.path.iterdir():
            if self.json_encoding == JsonEncoding.json:
                with file.open("r") as f:
                    doc = json.load(f)
            else:
                with file.open("rb") as f:
                    doc = orjson.loads(f.read())
                    # TODO: choose a more specific name and
                    # replace "id" with the field name of our ID
                    self.documents[doc["id"]] = doc

    def get_document(self, doc_id: int) -> Document:
        try:
            return self.documents[doc_id]
        except KeyError:
            logger.error(f"Document with id {doc_id} not found")
            return {}

    def add_document(self, doc: Document) -> None:
        if self.dataset_slug not in doc:
            raise CroissantError(
                f"Document does not have the specified dataset slug {self.dataset_slug}"
            )

        ref: str = doc[self.dataset_slug].replace("/", "_")
        file_path = self.path / f"{ref}.json"

        if file_path.exists():
            if self.overwrite_docs:
                logger.warning(f"Overwriting document with dataset slug {ref}")
            else:
                raise CroissantError(f"Document with dataset slug {ref} already exists")

        if self.json_encoding == JsonEncoding.json:
            with file_path.open("w") as file:
                json.dump(doc, file)
        else:
            with file_path.open("wb") as file:
                file.write(orjson.dumps(doc))

        # Add to in-memory collection
        # TODO: choose a more specific name and replace "id" with the field name of our ID
        self.documents[doc["id"]] = doc

    def replace_documents(self, docs: dict[int, Document]) -> None:
        self.documents = docs


class DiskCroissantStore(CroissantStore):
    """Store a collection of Croissant files on disk, loading them only when requested."""

    def __init__(self, path: Path, dataset_slug: str, overwrite_docs: bool = False) -> None:
        super().__init__(path, dataset_slug, overwrite_docs)
        self.document_ids: set[int] = set()
        self.file_mapping: dict[int, Path] = {}

    def __len__(self) -> int:
        return len(self.document_ids)

    def load_documents(self) -> None:
        """Load document IDs and file mappings but not the documents themselves."""
        self.document_ids.clear()
        self.file_mapping.clear()
        for file in self.path.iterdir():
            try:
                if self.json_encoding == JsonEncoding.json:
                    with file.open("r") as f:
                        doc = json.load(f)
                else:
                    with file.open("rb") as f:
                        doc = orjson.loads(f.read())
                # TODO: choose a more specific name
                # and replace "id" with the field name of our ID
                doc_id = doc["id"]
                self.document_ids.add(doc_id)
                self.file_mapping[doc_id] = file
            except (ValueError, KeyError):
                logger.error(f"Error loading document from {file}")

    def get_document(self, doc_id: int) -> Document:
        if doc_id not in self.document_ids:
            logger.error(f"Document with id {doc_id} not found")
            return {}

        try:
            with self.file_mapping[doc_id].open("rb") as f:
                return orjson.loads(f.read())
        except (KeyError, FileNotFoundError, ValueError) as e:
            logger.error(f"Error loading document with id {doc_id}: {e}")
            return {}

    def add_document(self, doc: Document) -> None:
        if self.dataset_slug not in doc:
            raise CroissantError(
                f"Document does not have the specified dataset slug {self.dataset_slug}"
            )

        ref: str = doc[self.dataset_slug].replace("/", "_")
        file_path = self.path / f"{ref}.json"

        if file_path.exists():
            if self.overwrite_docs:
                logger.warning(f"Overwriting document with dataset slug {ref}")
            else:
                raise CroissantError(f"Document with dataset slug {ref} already exists")

        # TODO: choose a more specific name and replace "id" with the field name of our ID
        doc_id = doc["id"]
        if self.json_encoding == JsonEncoding.json:
            with file_path.open("w") as file:
                json.dump(doc, file)
        else:
            with file_path.open("wb") as file:
                file.write(orjson.dumps(doc))

        # Update mapping
        self.document_ids.add(doc_id)
        self.file_mapping[doc_id] = file_path

    def replace_documents(self, docs: dict[int, Document]) -> None:
        # Clear existing files
        for file in self.path.iterdir():
            file.unlink()

        # Clear mappings
        self.document_ids.clear()
        self.file_mapping.clear()

        # Write new documents
        for doc in docs.values():
            self.add_document(doc)
