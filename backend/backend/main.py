import copy
import json
import time
import traceback
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
    FainderError,
    IndexingError,
    MessageResponse,
    Metadata,
    QueryRequest,
    QueryResponse,
    Settings,
    configure_logging,
)
from backend.croissant_store import CroissantStore, Document
from backend.fainder_index import FainderIndex
from backend.indexing import (
    generate_embedding_index,
    generate_fainder_indices,
    generate_metadata,
)
from backend.lucene_connector import LuceneConnector
from backend.query_evaluator import ColumnHighlights, DocumentHighlights, QueryEvaluator

# Global variables to store persistent objects
settings = Settings()  # type: ignore
# NOTE: Potentially add more modules here if they are not intercepted by loguru
configure_logging(
    settings.log_level,
    modules=[
        "fastapi",
        "fastapi_cli",
        "fastapi_cli.cli",
        "fastapi_cli.discover",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
    ],
)
with settings.metadata_path.open() as file:
    metadata = Metadata(**json.load(file))

croissant_store = CroissantStore(settings.croissant_path)
lucene_connector = LuceneConnector(settings.lucene_host, settings.lucene_port)
fainder_index = FainderIndex(
    metadata=metadata,
    rebinning_path=settings.rebinning_index_path,
    conversion_path=settings.conversion_index_path,
)
column_index = ColumnIndex(
    settings.hnsw_index_path,
    metadata,
    model=settings.embedding_model,
    use_embeddings=settings.use_embeddings,
    ef=settings.hnsw_ef,
)
query_evaluator = QueryEvaluator(
    lucene_connector=lucene_connector,
    fainder_index=fainder_index,
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

    yield

    # Shutdown
    query_evaluator.lucene_connector.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _apply_field_highlighting(doc: Document, field: str, highlighted: str) -> None:
    """Apply highlighting to a specific field in the document."""
    field_split = field.split("_")
    helper = doc
    for i in range(len(field_split)):
        if i == len(field_split) - 1:
            helper[field_split[i]] = highlighted
        else:
            helper = helper[field_split[i]]


def _apply_column_highlighting(
    record_set: list[dict[str, Any]], col_highlights: ColumnHighlights
) -> None:
    """Apply highlighting to column names in the record set."""
    for record in record_set:
        fields: list[dict[str, Any]] | None = record.get("field", None)
        if fields is None:
            continue
        for field_dict in fields:
            field_id: int | None = field_dict.get("id", None)
            if field_id is not None and field_id in col_highlights:
                field_dict["marked_name"] = "<mark>" + field_dict["name"] + "</mark>"


def _apply_highlighting(
    docs: list[Document],
    doc_highlights: DocumentHighlights,
    col_highlights: ColumnHighlights,
    paginated_doc_ids: list[int],
) -> list[Document]:
    """Apply highlighting to the documents."""
    for doc, doc_id in zip(docs, paginated_doc_ids, strict=True):
        if doc_id in doc_highlights:
            for field, highlighted in doc_highlights[doc_id].items():
                _apply_field_highlighting(doc, field, highlighted)

        record_set: list[dict[str, Any]] | None = doc.get("recordSet", None)
        if record_set is not None:
            _apply_column_highlighting(record_set, col_highlights)

    return docs


@app.post("/query")
async def query(request: QueryRequest) -> QueryResponse:
    """Execute a query and return the results."""
    logger.info(f"Received query: {request}")

    try:
        start_time = time.perf_counter()
        doc_ids, (doc_highlights, col_highlights) = query_evaluator.execute(
            query=request.query,
            fainder_mode=request.fainder_mode,
            enable_highlighting=request.enable_highlighting,
        )

        # Calculate pagination
        start_idx = (request.page - 1) * request.per_page
        end_idx = start_idx + request.per_page
        paginated_doc_ids = doc_ids[start_idx:end_idx]
        total_pages = (len(doc_ids) + request.per_page - 1) // request.per_page

        docs = croissant_store.get_documents(paginated_doc_ids)
        if request.enable_highlighting:
            # Make a deep copy of the documents to avoid modifying the original
            docs = copy.deepcopy(docs)
            # Only add highlights if enabled and they exist for the document
            docs = _apply_highlighting(docs, doc_highlights, col_highlights, paginated_doc_ids)

        search_time = time.perf_counter() - start_time
        logger.info(
            f"Query '{request.query}' returned {len(doc_ids)} results and {len(docs)} paginated "
            f"documents in {search_time:.4f} seconds."
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
    except FainderError as e:
        logger.info(f"Error executing percentile predicate: {e}")
        raise HTTPException(
            status_code=400, detail=f"Error executing percentile predicate: {e}"
        ) from e
    except ColumnSearchError as e:
        logger.info(f"Column search error: {e}")
        raise HTTPException(status_code=400, detail=f"Column search error: {e}") from e
    # TODO: Add other known errors for specific error handling
    except Exception as e:
        logger.error(f"Unknown query execution error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/upload")
async def upload_files(files: list[UploadFile]) -> MessageResponse:
    """Handle upload of JSON files."""
    try:
        for file in files:
            if not file.filename:
                raise HTTPException(status_code=400, detail="No file uploaded")
            if not file.filename.endswith(".json"):
                raise HTTPException(status_code=400, detail="Only .json files are accepted")
            content = await file.read()
            doc = json.loads(content.decode("utf-8"))
            croissant_store.add_document(doc)
            logger.debug(f"Uploaded file: {file.filename}")

        logger.info(f"{len(files)} files uploaded successfully")
        return MessageResponse(message=f"{len(files)} files uploaded successfully")
    except Exception as e:
        logger.error(f"Upload error: {e}")
        logger.debug(f"Upload error traceback: {e.__traceback__}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/update_indices")
async def update_indices() -> MessageResponse:
    """Recreate all indices from the current state of the Croissant store."""
    try:
        # NOTE: Our approach increases memory usage since we load the new indices without deleting
        # the old ones, we should consider optimizing this in the future

        # Generate indices
        hists, name_to_vector, documents = generate_metadata(
            croissant_path=settings.croissant_path, metadata_path=settings.metadata_path
        )
        generate_embedding_index(
            name_to_vector=name_to_vector,
            output_path=settings.embedding_path,
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
            ef_construction=settings.hnsw_ef_construction,
            n_bidirectional_links=settings.hnsw_n_bidirectional_links,
        )
        generate_fainder_indices(
            hists=hists,
            output_path=settings.fainder_path,
            n_clusters=settings.fainder_n_clusters,
            bin_budget=settings.fainder_bin_budget,
            alpha=settings.fainder_alpha,
            transform=settings.fainder_transform,
            algorithm=settings.fainder_cluster_algorithm,
        )

        # Update global variables
        croissant_store.replace_documents(documents)
        fainder_index.update(
            metadata=metadata,
            rebinning_path=settings.rebinning_index_path,
            conversion_path=settings.conversion_index_path,
        )
        column_index.update(path=settings.hnsw_index_path, metadata=metadata)
        query_evaluator.update_indices(
            fainder_index=fainder_index, hnsw_index=column_index, metadata=metadata
        )

        # Recreate Lucene index
        await lucene_connector.recreate_index()

        logger.info("Indices update successfully")
        return MessageResponse(message="Indices updated successfully")
    except IndexingError as e:
        logger.error(f"Indexing error: {e}")
        raise HTTPException(status_code=500, detail="Indexing error") from e
    except Exception as e:
        logger.error(f"Unknown indexing error: {e}, {e.args}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/cache_statistics")
async def cache_statistics() -> CacheInfo:
    """Return statistics about the query result cache."""
    return query_evaluator.cache_info()


@app.get("/clear_cache")
async def clear_cache() -> MessageResponse:
    """Clear the query result cache."""
    query_evaluator.clear_cache()
    logger.info("Cache cleared successfully")
    return MessageResponse(message="Cache cleared successfully")


# TODO: Recreate the alternative benchmarking endpoints with the new objects/approach
