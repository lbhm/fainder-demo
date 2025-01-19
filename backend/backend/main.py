import io
import sys
import time
import zipfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from lark import UnexpectedInput
from loguru import logger

from backend.column_index import ColumnIndex
from backend.config import (
    CacheInfo,
    ColumnSearchError,
    PercentileError,
    QueryRequest,
    QueryResponse,
    Settings,
)
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
rebinning_index = FainderIndex(settings.rebinning_index_path, metadata)
conversion_index = FainderIndex(settings.conversion_index_path, metadata)
column_index = ColumnIndex(settings.hnsw_index_path, metadata)
query_evaluator = QueryEvaluator(
    lucene_connector=lucene_connector,
    rebinning_index=rebinning_index,
    conversion_index=conversion_index,
    hnsw_index=column_index,
    metadata=metadata,
    cache_size=settings.query_cache_size,
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
    logger.info(f"Received query: {request}")

    try:
        start_time = time.perf_counter()
        # Pass index type to execute
        doc_ids = query_evaluator.execute(request.query, fainder_mode=request.fainder_mode)

        # Calculate pagination
        start_idx = (request.page - 1) * request.per_page
        end_idx = start_idx + request.per_page  # end_idx is exclusive in Python slicing
        paginated_doc_ids = doc_ids[start_idx:end_idx]
        total_pages = (len(doc_ids) + request.per_page - 1) // request.per_page

        docs = croissant_store.get_documents(paginated_doc_ids)
        end_time = time.perf_counter()
        search_time = end_time - start_time
        logger.info(
            f"Query '{request.query}' returned {len(docs)} documents in {search_time:.4f} seconds."
        )

        return QueryResponse(
            query=request.query,
            results=docs,
            search_time=search_time,
            result_count=len(doc_ids),
            page=request.page,
            total_pages=total_pages,
        )
    except UnexpectedInput as e:
        logger.info(f"Bad user query: {e.get_context(request.query)}")
        raise HTTPException(
            status_code=400, detail=f"Invalid query: {e.get_context(request.query)}"
        ) from e
    except PercentileError as e:
        logger.info(f"Invalid percentile predicate: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid percentile predicate: {e}") from e
    except ColumnSearchError as e:
        logger.info(f"Column search error: {e}")
        raise HTTPException(status_code=400, detail=f"Column search error: {e}") from e
    # TODO: Add other known errors for specific error handling
    except Exception as e:
        logger.error(f"Unknown query execution error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/upload")
async def upload_files(files: list[UploadFile]):
    """Handle upload of JSON files or ZIP containing JSON files."""
    try:
        for file in files:
            if not file.filename:
                raise HTTPException(status_code=400, detail="No file uploaded")
            if file.filename.endswith(".zip"):
                # Handle ZIP file
                zip_contents = await file.read()
                with zipfile.ZipFile(io.BytesIO(zip_contents)) as zip_file:
                    for json_file in zip_file.namelist():
                        if json_file.endswith(".json"):
                            json_content = zip_file.read(json_file)
                            # Process JSON content
                            # TODO: Add a function to handle JSON content
            elif file.filename.endswith(".json"):
                # Handle JSON file
                content = await file.read()
                # TODO: Add a function to handle JSON content
            else:
                raise HTTPException(
                    status_code=400, detail="Only .json and .zip files are accepted"
                )

        # TODO: Add the reindexing process
        return {"message": "Files uploaded successfully"}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache_statistics")
async def cache_statistics() -> CacheInfo:
    """Return statistics about the query result cache."""
    return query_evaluator.cache_info()


# TODO: Recreate the alternative benchmarking endpoints with the new objects/approach
