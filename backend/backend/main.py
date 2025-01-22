import json
import sys
import time
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
from backend.scripts.generate_indices import (
    generate_embedding_index,
    generate_fainder_indices,
    load_metadata,
)

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
logger.info("starting to column index")
column_index = ColumnIndex(settings.hnsw_index_path, metadata, bypass_transformer=True)
logger.info("All indexes loaded successfully.")
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
    """Handle upload of JSON files."""
    try:
        for file in files:
            if not file.filename:
                raise HTTPException(status_code=400, detail="No file uploaded")
            if not file.filename.endswith(".json"):
                raise HTTPException(status_code=400, detail="Only .json files are accepted")
            file_content = await file.read()
            content = file_content.decode("utf-8")
            doc = json.loads(content)
            croissant_store.save_document(doc)
            logger.debug(f"Uploaded file: {file.filename}")

        logger.info("Files uploaded successfully")
        # TODO: Add the reindexing process

        base_path = settings.data_dir / settings.collection_name

        hists, name_to_vector, documents = load_metadata(base_path)
        # 1. generate indices
        _ = generate_embedding_index(name_to_vector, settings.embedding_path)
        generate_fainder_indices(hists, settings.fainder_path)

        # Recreate Lucene index
        await query_evaluator.recreate_lucene_index()

        # 2. update global variables
        croissant_store.replace_documents(documents)
        rebinning_index.update(settings.rebinning_index_path, metadata)
        conversion_index.update(settings.conversion_index_path, metadata)
        column_index.update(metadata)

        logger.info("Indices updated successfully")

        return {"message": "Files uploaded successfully"}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/cache_statistics")
async def cache_statistics() -> CacheInfo:
    """Return statistics about the query result cache."""
    return query_evaluator.cache_info()


# TODO: Recreate the alternative benchmarking endpoints with the new objects/approach
