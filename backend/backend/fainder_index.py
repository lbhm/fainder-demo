from pathlib import Path

from fainder.execution.runner import run
from fainder.typing import PercentileIndex, PercentileQuery
from fainder.utils import load_input
from loguru import logger

from backend.config import PredicateError


class FainderIndex:
    def __init__(
        self, path: Path, hist_to_doc: dict[int, int], column_to_hists: dict[str, set[int]]
    ) -> None:
        self.index: PercentileIndex = load_input(path, "index")
        self.hist_to_doc = hist_to_doc
        self.column_to_hists = column_to_hists

        # TODO: Move this to the offline index building process
        self.doc_to_hists: dict[int, set[int]] = {}
        for hist, doc in hist_to_doc.items():
            if doc not in self.doc_to_hists:
                self.doc_to_hists[doc] = set()
            self.doc_to_hists[doc].add(hist)

    def search(
        self,
        percentile: float,
        comparison: str,
        reference: float,
        identifier: str | None = None,
        doc_filter: set[int] | None = None,
    ) -> set[int]:
        # Data validation
        if not (0 < percentile <= 1) or comparison not in ["ge", "gt", "le", "lt"]:
            raise PredicateError(f"{percentile};{comparison};{reference};{identifier}")

        # Filter creation
        hist_filter: set[int] | None = None
        if doc_filter:
            if len(doc_filter) == 0:
                return set()
            hist_filter = {hist for doc in doc_filter for hist in self.doc_to_hists[doc]}
        if identifier:
            hist_ids = self._get_matching_histograms(identifier)
            if hist_ids is None:
                return set()
            if hist_filter:
                hist_filter &= hist_ids
            else:
                hist_filter = hist_ids

        # Predicate evaluation
        query: PercentileQuery = (percentile, comparison, reference)  # type: ignore
        results, runtime = run(
            self.index,
            queries=[query],
            input_type="index",
            hist_filter=list(hist_filter) if hist_filter else None,
        )
        result = results[0]
        logger.info(f"Query '{query}' returned {len(result)} histograms in {runtime:.2f} seconds.")

        return {self.hist_to_doc[int(hist)] for hist in result}

    def _get_matching_histograms(self, identifier: str) -> set[int] | None:
        """Return the set of histogram IDs whose column name matches the given identifier."""
        # TODO: Add fuzzy and semantic search functionality to this function
        return self.column_to_hists.get(identifier, None)
