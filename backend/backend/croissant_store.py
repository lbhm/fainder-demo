import json
from pathlib import Path
from typing import Any

from loguru import logger

from backend.config import CroissantError

Document = dict[str, Any]


class CroissantStore:
    """Store a collection of Croissant files in memory."""

    def __init__(self, path: Path, overwrite_docs: bool = False) -> None:
        self.documents: dict[int, Document] = {}
        self.path = path
        self.overwrite_docs = overwrite_docs

    def __len__(self) -> int:
        return len(self.documents)

    def __getitem__(self, index: int) -> Document:
        return self.get_document(index)

    def load_documents(self) -> None:
        self.documents.clear()
        for file in self.path.iterdir():
            with file.open() as f:
                doc = json.load(f)
                # TODO: choose a more specific name and replace "id" with the field name of our ID
                self.documents[doc["id"]] = doc

    def get_document(self, doc_id: int) -> Document:
        try:
            return self.documents[doc_id]
        except KeyError:
            logger.error(f"Document with id {doc_id} not found")
            return {}

    def get_documents(self, doc_ids: list[int]) -> list[Document]:
        return [self.get_document(doc_id) for doc_id in doc_ids]

    def add_document(self, doc: Document) -> None:
        if "kaggleRef" not in doc:
            raise CroissantError("Document does not have a kaggleRef field")

        ref: str = doc["kaggleRef"].replace("/", "_")
        file_path = self.path / f"{ref}.json"

        if file_path.exists():
            if self.overwrite_docs:
                logger.warning(f"Overwriting document with kaggleRef {ref}")
            else:
                raise CroissantError(f"Document with kaggleRef {ref} already exists")

        with file_path.open("w") as file:
            json.dump(doc, file)

    def replace_documents(self, docs: dict[int, Document]) -> None:
        self.documents = docs
