import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from lark import UnexpectedInput
from loguru import logger

from backend.column_search import ColumnSearch
from backend.config import PredicateError, QueryRequest, QueryResponse, Settings
from backend.croissant_store import CroissantStore
from backend.fainder_index import FainderIndex
from backend.lucene_connector import LuceneConnector
from backend.query_evaluator import QueryEvaluator

try:
    settings = Settings()  # type: ignore
    metadata = settings.metadata
except Exception as e:
    logger.error(f"Error loading settings: {e}")
    sys.exit(1)

# TODO: Maybe move from loguru to standard logging to be compatible with FastAPI
logger.remove()
logger.add(sys.stdout, level="DEBUG")

# Global variables to store persistent objects
croissant_store = CroissantStore(settings.croissant_path)
lucene_connector = LuceneConnector(settings.lucene_host, settings.lucene_port)
rebinning_index = FainderIndex(
    settings.rebinning_index_path, metadata.hist_to_doc, metadata.column_to_hists
)
conversion_index = FainderIndex(
    settings.conversion_index_path, metadata.hist_to_doc, metadata.column_to_hists
)
column_search = ColumnSearch(metadata.column_to_hists)
query_evaluator = QueryEvaluator(
    lucene_connector, rebinning_index, conversion_index, column_search, metadata
)

cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[Any, Any]:
    # Startup
    croissant_store.load_documents()
    query_evaluator.lucene_connector.connect()
    # TODO: Add a language model and HNSW index here

    yield

    # Shutdown
    query_evaluator.lucene_connector.connect()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/query")
async def query(request: QueryRequest) -> QueryResponse:
    """Execute a query and return the results."""
    # TODO: Add pagination to query results
    # TODO: Add caching of query results
    logger.info(f"Received query: {request}")

    try:
        doc_ids = await query_evaluator.execute(request.query)
        logger.info(f"Query '{request.query}' returned document IDs: {doc_ids}")

        docs = croissant_store.get_documents(doc_ids)
        return QueryResponse(query=request.query, results=docs)
    except UnexpectedInput as e:
        logger.info(f"Bad user query: {e.get_context(request.query)}")
        raise HTTPException(
            status_code=400, detail=f"Invalid query: {e.get_context(request.query)}"
        ) from e
    except PredicateError as e:
        logger.info(f"Invalid percentile predicate: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid percentile predicate: {e}") from e
    # TODO: Add other known errors for specific error handling
    except Exception as e:
        logger.error(f"Unknown query execution error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


# TODO: Recreate the alternative benchmarking endpoints with the new objects/approach
