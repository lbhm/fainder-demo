import time
from collections.abc import Sequence

import grpc
from loguru import logger

from backend.config import IndexingError
from backend.proto.lucene_connector_pb2 import QueryRequest, RecreateIndexRequest  # type: ignore
from backend.proto.lucene_connector_pb2_grpc import LuceneConnectorStub


class LuceneConnector:
    channel: grpc.Channel | None

    def __init__(self, host: str, port: str) -> None:
        self.host = host
        self.port = port
        self.channel = None

    def __del__(self) -> None:
        self.close()

    def connect(self) -> None:
        self.channel = grpc.insecure_channel(f"{self.host}:{self.port}")
        self.stub = LuceneConnectorStub(self.channel)
        logger.debug(f"Connected to Lucene server with host: {self.host} and port: {self.port}")

    def close(self) -> None:
        if self.channel:
            self.channel.close()
            self.channel = None
            logger.debug("gRPC channel closed")

    def evaluate_query(
        self, query: str, doc_ids: set[int] | None = None
    ) -> tuple[Sequence[int], Sequence[float], Sequence[dict[str, str]]]:
        """
        Evaluates a keyword query using the Lucene server.

        Args:
            query: The query string to be evaluated by Lucene.
            doc_ids: A set of document IDs to consider as a filter (none by default).

        Returns:
            list[int]: A list of document IDs that match the query.
            list[float]: A list of scores for each document ID.
            list[dict[str, str]]: A list of dictionaries mapping field names to highlighted snippets.
        """
        start = time.perf_counter()
        if not self.channel:
            self.connect()

        try:
            logger.debug(f"Executing query: '{query}' with filter: {doc_ids}")
            response = self.stub.Evaluate(QueryRequest(query=query, doc_ids=doc_ids or []))

            # Group highlights by document
            highlights = []
            current_highlights: dict[str, str] = {}
            doc_count = len(response.results)
            entries_per_doc = len(response.highlights) // doc_count if doc_count > 0 else 0

            for i, entry in enumerate(response.highlights):
                if i > 0 and i % entries_per_doc == 0:
                    highlights.append(current_highlights)
                    current_highlights = {}
                current_highlights[entry.field] = entry.text

            # Don't forget the last document's highlights
            if current_highlights:
                highlights.append(current_highlights)

            logger.debug(f"Lucene query execution took {time.perf_counter() - start:.3f} seconds")
            logger.debug(f"Keyword query result: {response.results}")
            logger.debug(f"Found highlights: {highlights}")

            return response.results, response.scores, highlights
        except grpc.RpcError as e:
            logger.error(f"Calling Lucene raised an error: {e}")
            return [], [], []

    async def recreate_index(self) -> None:
        """Triggers the recreation of the Lucene index on the server side."""
        if not self.channel:
            self.connect()

        try:
            response = self.stub.RecreateIndex(RecreateIndexRequest())
            if not response.success:
                raise IndexingError(f"Failed to recreate Lucene index: {response.message}")
            logger.info("Lucene index recreation completed")
        except grpc.RpcError as e:
            logger.error(f"Lucene index recreation failed: {e}")
            raise IndexingError("Failed to recreate Lucene index") from e
