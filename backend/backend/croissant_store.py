from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from backend.config import CroissantError, CroissantStoreType
from backend.utils import dump_json, load_json

if TYPE_CHECKING:
    from collections.abc import Callable

Document = dict[str, Any]


class CroissantStore(ABC):
    """Abstract base class for storing a collection of Croissant files."""

    def __init__(
        self,
        base_path: Path,
        doc_to_path: list[str],
        *,
        dataset_slug: str,
        cache_size: int = 128,
        overwrite_docs: bool = False,
    ) -> None:
        self.base_path = base_path
        self.doc_to_path = self._rewrite_paths(doc_to_path)
        self.dataset_slug = dataset_slug
        self.overwrite_docs = overwrite_docs

        self.get_document: Callable[[int], Document] = (
            lru_cache(maxsize=cache_size)(self._get_document)
            if cache_size > 0
            else self._get_document
        )

    def __getitem__(self, index: int) -> Document:
        """Get a document by ID."""
        return self._get_document(index)

    @abstractmethod
    def __len__(self) -> int:
        """Get the number of documents in the store."""

    @abstractmethod
    def _get_document(self, doc_id: int) -> Document:
        """Get a document by ID."""

    def get_documents(self, doc_ids: list[int]) -> list[Document]:
        return [self._get_document(doc_id) for doc_id in doc_ids]

    def add_document(self, doc: Document) -> None:
        """Add a new document to the store."""
        if self.dataset_slug not in doc:
            raise CroissantError(
                f"Document does not have the specified dataset slug {self.dataset_slug}"
            )

        ref: str = doc[self.dataset_slug].replace("/", "_")
        file_path = (self.base_path / ref).with_suffix(".json")

        if file_path.exists():
            if self.overwrite_docs:
                logger.warning("Overwriting document with dataset slug {}", ref)
            else:
                raise CroissantError(f"Document with dataset slug {ref} already exists")

        # Update mapping
        self.doc_to_path[doc["id"]] = file_path

        # Save to file system
        dump_json(doc, file_path)

    @abstractmethod
    def replace_documents(self, doc_to_path: list[str]) -> None:
        """Replace all documents in the store."""

    def _rewrite_paths(self, doc_to_path: list[str]) -> list[Path]:
        return [self.base_path / path for path in doc_to_path]


class DictCroissantStore(CroissantStore):
    """Store a collection of Croissant files in an in-memory hash table."""

    def __init__(
        self,
        base_path: Path,
        doc_to_path: list[str],
        *,
        dataset_slug: str,
        overwrite_docs: bool = False,
    ) -> None:
        super().__init__(
            base_path,
            doc_to_path,
            dataset_slug=dataset_slug,
            cache_size=0,
            overwrite_docs=overwrite_docs,
        )
        self.documents = {doc_id: load_json(path) for doc_id, path in enumerate(self.doc_to_path)}

    def __len__(self) -> int:
        return len(self.documents)

    def _get_document(self, doc_id: int) -> Document:
        try:
            return self.documents[doc_id]
        except KeyError:
            logger.error("Document with id {} not found", doc_id)
            return {}

    def add_document(self, doc: Document) -> None:
        super().add_document(doc)
        self.documents[doc["id"]] = doc

    def replace_documents(self, doc_to_path: list[str]) -> None:
        self.doc_to_path = self._rewrite_paths(doc_to_path)
        del self.documents
        self.documents = {doc_id: load_json(path) for doc_id, path in enumerate(self.doc_to_path)}


class FileCroissantStore(CroissantStore):
    """Manage a collection of Croissant files, loading them only when requested."""

    def __init__(
        self,
        base_path: Path,
        doc_to_path: list[str],
        *,
        dataset_slug: str,
        cache_size: int = 128,
        overwrite_docs: bool = False,
    ) -> None:
        super().__init__(
            base_path,
            doc_to_path,
            dataset_slug=dataset_slug,
            cache_size=cache_size,
            overwrite_docs=overwrite_docs,
        )

    def __len__(self) -> int:
        return len(self.doc_to_path)

    def _get_document(self, doc_id: int) -> Document:
        try:
            return load_json(self.doc_to_path[doc_id])
        except KeyError:
            logger.error("Document with id {} not found", doc_id)
            return {}
        except (FileNotFoundError, ValueError) as e:
            logger.error("Error loading document with id {}: {}", doc_id, e)
            return {}

    def replace_documents(self, doc_to_path: list[str]) -> None:
        self.doc_to_path = self._rewrite_paths(doc_to_path)


def get_croissant_store(
    store_type: CroissantStoreType,
    base_path: Path,
    doc_to_path: list[str],
    dataset_slug: str,
    *,
    cache_size: int = 128,
    overwrite_docs: bool = False,
) -> CroissantStore:
    match store_type:
        case CroissantStoreType.DICT:
            return DictCroissantStore(
                base_path=base_path,
                doc_to_path=doc_to_path,
                dataset_slug=dataset_slug,
                overwrite_docs=overwrite_docs,
            )
        case CroissantStoreType.FILE:
            return FileCroissantStore(
                base_path=base_path,
                doc_to_path=doc_to_path,
                dataset_slug=dataset_slug,
                cache_size=cache_size,
                overwrite_docs=overwrite_docs,
            )
        case _:
            raise TypeError(
                f"Unsupported Croissant store type: {store_type}. "
                "Supported types are: 'dict', 'file'."
            )
