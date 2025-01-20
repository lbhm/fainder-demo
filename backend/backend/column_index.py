from pathlib import Path

import hnswlib  # type: ignore
from loguru import logger
from numpy import uint32
from sentence_transformers import SentenceTransformer

from backend.config import ColumnSearchError, Metadata


class ColumnIndex:
    def __init__(
        self,
        path: Path,
        metadata: Metadata,
        model: str = "all-MiniLM-L6-v2",
        ef: int = 50,
        disable_transforner: bool = False,
    ) -> None:
        self.name_to_vector = metadata.name_to_vector
        self.vector_to_name = {v: k for k, v in self.name_to_vector.items()}
        self.vector_to_cols = metadata.vector_to_cols

        if disable_transforner:
            return
        # Embedding model
        # TODO: Expose model and ef parameters in the settings
        self.embedder = SentenceTransformer(
            model, cache_folder=(path.parent / "model_cache").as_posix()
        )
        dimension = self.embedder.get_sentence_embedding_dimension()
        if dimension is None:
            raise ValueError("Dimension of the model is not known, cannot initialize HNSW index")

        # HNSW index
        self.index = hnswlib.Index(space="cosine", dim=dimension)
        self.index.load_index(str(path))
        self.index.set_ef(ef)

    def search(self, column_name: str, k: int, column_filter: set[uint32] | None) -> set[uint32]:
        if k < 0:
            raise ColumnSearchError(f"k must be a non-negative integer: {k}")

        result: set[uint32] = set()
        if k == 0:
            # Exact search
            vector_id = self.name_to_vector.get(column_name, None)
            if vector_id:
                col_ids = self.vector_to_cols.get(vector_id, set())
                result |= {uint32(col_id) for col_id in col_ids}
        else:
            if self.embedder is None:
                raise ColumnSearchError("Embedding model is not available for approximate search")

            # Nearest neighbor search
            embedding = self.embedder.encode(
                column_name, convert_to_numpy=True, normalize_embeddings=True
            )

            if column_name in self.name_to_vector:
                # If the column name exists in the index, it will be returned as the first result
                k += 1
            vector_ids, distances = self.index.knn_query(embedding, k=k)
            result |= {
                uint32(col_id)
                for vector_id in vector_ids[0]
                for col_id in self.vector_to_cols[vector_id]
            }
            logger.debug(
                f"Column search '{column_name}' returned neighbors "
                f"{[self.vector_to_name[vector_id] for vector_id in vector_ids[0]]} with "
                f"distances {distances[0]}"
            )
        # TODO: add column filter
        return result
