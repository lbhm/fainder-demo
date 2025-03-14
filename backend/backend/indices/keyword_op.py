import shutil
import time
from collections import defaultdict
from pathlib import Path

import tantivy
from loguru import logger

from backend.config import DocumentHighlights

MAX_DOCS = 1000000
DOC_FIELDS: list[str] = [
    "name",
    "description",
    "keywords",
    "creator",
    "publisher",
    "alternateName",
]


def get_tantivy_schema() -> tantivy.Schema:
    """Construct the schema for the Tantivy index.

    See https://docs.rs/tantivy/latest/tantivy/schema/index.html for how to configure fields.
    """
    schema_builder = tantivy.SchemaBuilder()
    schema_builder.add_unsigned_field("id", stored=True, indexed=True, fast=True)
    schema_builder.add_text_field("name", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("description", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("keywords", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("creator", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("publisher", stored=True, tokenizer_name="en_stem")
    schema_builder.add_text_field("alternateName", stored=True, tokenizer_name="en_stem")
    return schema_builder.build()


class TantivyIndex:
    def __init__(self, index_path: str | Path, recreate: bool = False) -> None:
        self.index_path = str(index_path)
        self.schema = get_tantivy_schema()
        self.index = self.load_index(self.schema, recreate)

    def load_index(self, schema: tantivy.Schema, recreate: bool = False) -> tantivy.Index:
        """
        Load the index from the index path. If the index does not exist, create a new index.
        """
        tantivy_path = Path(self.index_path)
        if recreate and tantivy_path.exists():
            # Delete the index if it already exists to make sure we start from scratch
            shutil.rmtree(tantivy_path, ignore_errors=True)
        tantivy_path.mkdir(parents=True, exist_ok=True)

        return tantivy.Index(schema=schema, path=self.index_path, reuse=not recreate)

    def add_documents(self, docs: list[tantivy.Document]) -> None:
        writer = self.index.writer()
        for doc in docs:
            writer.add_document(doc)
        writer.commit()
        writer.wait_merging_threads()

    def search(
        self, query: str, enable_highlighting: bool = False
    ) -> tuple[list[int], list[float], DocumentHighlights]:
        parsed_query = self.index.parse_query(query, default_field_names=DOC_FIELDS)
        searcher = self.index.searcher()

        search_start = time.perf_counter()
        search_result = searcher.search(parsed_query, limit=MAX_DOCS).hits
        logger.info(f"Tantivy search took {time.perf_counter() - search_start:.5f}s")

        results: list[int] = []
        scores: list[float] = []
        highlights: DocumentHighlights = defaultdict(dict)

        process_start = time.perf_counter()
        for score, doc_address in search_result:
            doc = searcher.doc(doc_address)
            doc_id: int | None = doc.get_first("id")
            if doc_id is None:
                logger.error(f"Tantivy document with address {doc_address} has no id field")
                continue
            results.append(doc_id)
            scores.append(score)

            if enable_highlighting:
                for field in DOC_FIELDS:
                    # NOTE: Recreating the snippet generators for each result doc is inefficient
                    snippet_generator = tantivy.SnippetGenerator.create(
                        searcher, parsed_query, self.schema, field
                    )
                    snippet = snippet_generator.snippet_from_doc(doc)
                    highlighted = snippet.highlighted()
                    if len(highlighted) == 0:
                        continue

                    html_snippet: str = doc.get_first(field) or ""
                    offset = 0
                    for fragment in highlighted:
                        start = fragment.start
                        end = fragment.end
                        html_snippet = (
                            html_snippet[: start + offset]
                            + "<mark>"
                            + html_snippet[start + offset : end + offset]
                            + "</mark>"
                            + html_snippet[end + offset :]
                        )
                        offset += len("<mark></mark>")

                    field_name = field
                    if field in ["creator", "publisher"]:
                        field_name += "-name"
                    highlights[doc_id][field_name] = html_snippet

        logger.info(f"Processing results took {time.perf_counter() - process_start:.5f}s")

        return results, scores, highlights
