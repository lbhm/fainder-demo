import shutil
import time
from pathlib import Path
from typing import Any

import tantivy
from loguru import logger

DOCS_MAX = 1000000

FIELDS: list[str] = ["name", "description", "keywords", "creator", "publisher", "alternateName"]


class TantivyIndex:
    def __init__(self, index_path: str, recreate: bool = False) -> None:
        self.index_path = index_path
        self.schema = self._schema()
        self.index = self.load_index(self.schema, recreate)

    def _schema(self) -> tantivy.Schema:
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_date_field("dateModified", stored=True)
        schema_builder.add_text_field("description", stored=True, tokenizer_name="en_stem")
        schema_builder.add_text_field("name", stored=True, tokenizer_name="en_stem")
        schema_builder.add_text_field("alternateName", stored=True, tokenizer_name="en_stem")
        schema_builder.add_integer_field("id", stored=True)
        schema_builder.add_text_field("keywords", stored=True, tokenizer_name="en_stem")
        schema_builder.add_text_field("creator", stored=True, tokenizer_name="en_stem")
        schema_builder.add_text_field("publisher", stored=True, tokenizer_name="en_stem")
        return schema_builder.build()

    def load_index(self, schema: tantivy.Schema, recreate: bool = False) -> tantivy.Index:
        """
        Load the index from the index path. If the index does not exist, create a new index.
        """
        tantivy_path = Path(self.index_path)
        if recreate and tantivy_path.exists():
            # delete the index if it already exists to make sure we start from scratch
            shutil.rmtree(tantivy_path, ignore_errors=True)
        tantivy_path.mkdir(parents=True, exist_ok=True)
        return tantivy.Index(schema, self.index_path, not recreate)

    def add_document(self, index: tantivy.Index, doc: dict[str, Any]) -> None:
        writer = index.writer()
        # Add document to index
        keywords = "; ".join(doc["keywords"])
        writer.add_document(
            tantivy.Document(
                dateModified=doc["dateModified"],
                description=doc["description"],
                name=doc["name"],
                alternateName=doc["alternateName"],
                id=doc["id"],
                keywords=keywords,
                creator=doc["creator"]["name"],
                publisher=doc["publisher"]["name"],
            )
        )
        writer.commit()
        writer.wait_merging_threads()

    def search(
        self, query: str, enable_highlighting: bool = False
    ) -> tuple[list[int], list[float], dict[int, dict[str, str]]]:
        parsered_query = self.index.parse_query(query)
        searcher = self.index.searcher()
        start_time = time.perf_counter()
        top_docs = searcher.search(parsered_query, DOCS_MAX).hits
        logger.info(f"Search took {time.perf_counter() - start_time} seconds")

        results: list[int] = []
        scores: list[float] = []
        highlights: dict[int, dict[str, str]] = {}

        start_time = time.perf_counter()
        for doc_results in top_docs:
            best_score, doc_address = doc_results
            doc = searcher.doc(doc_address)
            doc_id: int = doc["id"][0]  # type: ignore
            assert isinstance(doc_id, int)
            results.append(doc_id)

            scores.append(best_score)
            if enable_highlighting:
                for field in FIELDS:
                    snippet_generator = tantivy.SnippetGenerator.create(
                        searcher, parsered_query, self.schema, field
                    )
                    snippet = snippet_generator.snippet_from_doc(doc)
                    highlighted = snippet.highlighted()
                    if len(highlighted) == 0:
                        continue

                    html_snippet: str = str(doc[field][0]) if doc[field] and doc[field][0] else ""  # type: ignore

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

                    if doc_id not in highlights:
                        highlights[doc_id] = {}
                    field_name = field
                    if field in ["creator", "publisher"]:
                        field_name += "-name"
                    highlights[doc_id][field_name] = html_snippet

        logger.info(f"Processing results took {time.perf_counter() - start_time} seconds")

        return results, scores, highlights
