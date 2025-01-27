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
        self, query: str, doc_ids: set[int] | None = None, enable_highlighting: bool = True
    ) -> tuple[Sequence[int], Sequence[float], dict[int, dict[str, str]]]:
        """
        Evaluates a keyword query using the Lucene server.

        Args:
            query: The query string to be evaluated by Lucene.
            doc_ids: A set of document IDs to consider as a filter (none by default).
            enable_highlighting: Whether to enable highlighting (default True).

        Returns:
            list[int]: A list of document IDs that match the query.
            list[float]: A list of scores for each document ID.
            list[dict[str, str]]: A list of dictionaries mapping field names
            to highlighted snippets.
        """
        if not self.channel:
            self.connect()

        try:
            logger.debug(f"Executing query: '{query}' with filter: {doc_ids}")
            # Clear any previous state by creating a fresh request
            request = QueryRequest(
                query=query, doc_ids=doc_ids or [], enable_highlighting=enable_highlighting
            )
            response = self.stub.Evaluate(request)

            # Create a fresh highlights list for each query result
            highlights: dict[int, dict[str, str]] = {}  # Initialize empty dicts

            # Only process highlights if enabled
            if enable_highlighting:
                for doc_id in response.results:
                    if doc_id in response.highlights:
                        highlights[doc_id] = dict(response.highlights[doc_id].fields)

            return response.results, response.scores, highlights

        except grpc.RpcError as e:
            logger.error(f"Calling Lucene raised an error: {e}")
            return [], [], {}

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
