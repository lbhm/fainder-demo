from typing import Any

import tantivy

DOCS_MAX = 1000000


class TantivyIndex:
    def __init__(self, index_path: str, recreate: bool = False) -> None:
        self.index_path = index_path
        self.schema = self._schema()
        self.index = self.load_index(self.schema, recreate)

    def _schema(self) -> tantivy.Schema:
        schema_builder = tantivy.SchemaBuilder()
        schema_builder.add_date_field("dateModified", stored=True)
        schema_builder.add_text_field("description", stored=True)
        schema_builder.add_text_field("name", stored=True)
        schema_builder.add_text_field("alternateName", stored=True)
        schema_builder.add_integer_field("id", stored=True)
        schema_builder.add_text_field("keywords", stored=True)
        schema_builder.add_text_field("creator.name", stored=True)  # nested field
        schema_builder.add_text_field("publisher.name", stored=True)  # nested field
        return schema_builder.build()

    def load_index(self, schema: tantivy.Schema, recreate: bool = False) -> tantivy.Index:
        """
        Load the index from the index path. If the index does not exist, create a new index.
        """
        return tantivy.Index(schema, self.index_path, not recreate)

    def add_document(self, index: tantivy.Index, doc: dict[str, Any]) -> None:
        writer = index.writer()
        # Add document to index
        writer.add_document(
            tantivy.Document(
                dateModified=doc["dateModified"],
                description=doc["description"],
                name=doc["name"],
                alternateName=doc["alternateName"],
                id=doc["id"],
                keywords=doc["keywords"],
                creator={"name": doc["creator"]["name"]},
                publisher={"name": doc["publisher"]["name"]},
            )
        )
        writer.commit()
        writer.wait_merging_threads()

    def search(
        self, query: str, enable_highlighting: bool = False
    ) -> tuple[list[int], list[float], dict[int, dict[str, str]]]:
        parsered_query = self.index.parse_query(
            query,
            ["name", "description", "keywords", "creator.name", "publisher.name", "alternateName"],
        )
        searcher = self.index.searcher()
        top_docs = searcher.search(parsered_query, DOCS_MAX).hits

        results: list[int] = []
        scores: list[float] = []
        highlights: dict[int, dict[str, str]] = {}

        for doc_results in top_docs:
            best_score, doc_address = doc_results
            doc = searcher.doc(doc_address)
            doc_id: int = doc["id"][0]  # type: ignore
            assert isinstance(doc_id, int)
            results.append(doc_id)

            scores.append(best_score)
            if enable_highlighting:
                pass

        return results, scores, highlights
