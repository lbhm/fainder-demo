# implements search by column name

from numpy import uint32

from backend.config import ColumnSearchError, Metadata


class ColumnSearch:
    def __init__(self, metdata: Metadata) -> None:
        self.metadata = metdata

    def search(
        self, column_name: str, mode: str, filter_column: set[uint32] | None
    ) -> set[uint32]:
        if mode == "exact":
            vector_id = self.metadata.name_to_vector.get(column_name, None)
            if vector_id:
                r = self.metadata.vector_to_cols.get(vector_id, set())
                # return filtered by filter_column and converted to set[uin32]
                result = {uint32(x) for x in r}
                return result if filter_column is None else result.intersection(filter_column)
            return set()
        if mode == "fuzzy":
            raise NotImplementedError("Fuzzy search not implemented yet")

        if mode == "semantic":
            raise NotImplementedError("Semantic search not implemented yet")

        raise ColumnSearchError(f"Invalid search mode: {mode}")
