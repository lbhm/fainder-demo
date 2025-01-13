# implements search by column name

from numpy import uint32

from backend.config import ColumnSearchError


class ColumnSearch:
    column_to_hists: dict[str, set[int]]

    def __init__(self, column_to_hists: dict[str, set[int]]) -> None:
        self.column_to_hists = column_to_hists

    def search(
        self, column_name: str, mode: str, filter_column: set[uint32] | None
    ) -> set[uint32]:
        if mode == "exact":
            r = self.column_to_hists.get(column_name, set())
            if filter_column:
                r = r & filter_column
            return {uint32(x) for x in r}
        if mode == "fuzzy":
            raise NotImplementedError("Fuzzy search not implemented yet")

        if mode == "semantic":
            raise NotImplementedError("Semantic search not implemented yet")

        raise ColumnSearchError(f"Invalid search mode: {mode}")
