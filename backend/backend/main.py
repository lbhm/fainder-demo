import copy
import time
import traceback
from typing import Any

import orjson
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from lark import UnexpectedInput
from loguru import logger

from backend.app_state import ApplicationState
from backend.config import (
    CacheInfo,
    ColumnHighlights,
    ColumnSearchError,
    DocumentHighlights,
    FainderConfigRequest,
    FainderConfigsResponse,
    FainderError,
    IndexingError,
    MessageResponse,
    QueryRequest,
    QueryResponse,
)
from backend.croissant_store import Document
from backend.utils import load_json

logger.info("Starting backend")
app_state = ApplicationState()
app_state.initialize()

logger.info("Starting FastAPI app")
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    logger.info("Received query: {}", request)

    try:
        start_time = time.perf_counter()
        doc_ids, (doc_highlights, col_highlights) = app_state.engine.execute(
            query=request.query,
            fainder_mode=request.fainder_mode,
            enable_highlighting=request.result_highlighting,
        )

        # Calculate pagination
        start_idx = (request.page - 1) * request.per_page
        end_idx = start_idx + request.per_page
        paginated_doc_ids = doc_ids[start_idx:end_idx]
        total_pages = (len(doc_ids) + request.per_page - 1) // request.per_page

        docs = app_state.croissant_store.get_documents(paginated_doc_ids)
        if request.result_highlighting:
            # Make a deep copy of the documents to avoid modifying the original
            docs = copy.deepcopy(docs)
            # Only add highlights if enabled and they exist for the document
            docs = _apply_highlighting(docs, doc_highlights, col_highlights, paginated_doc_ids)

        search_time = time.perf_counter() - start_time
        logger.info(
            "Query '{}' returned {} results and {} paginated documents in {:.4f} seconds.",
            request.query,
            len(doc_ids),
            len(docs),
            search_time,
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
        logger.info(
            "Bad user query:\n{}\n(line {}, column {})",
            e.get_context(request.query).strip(),
            e.line,
            e.column,
        )
        raise HTTPException(
            status_code=400, detail=f"Invalid query: {e.get_context(request.query)}"
        ) from e
    except FainderError as e:
        logger.info("Error executing percentile predicate: {}", e)
        raise HTTPException(
            status_code=400, detail=f"Error executing percentile predicate: {e}"
        ) from e
    except ColumnSearchError as e:
        logger.info("Column search error: {}", e)
        raise HTTPException(status_code=400, detail=f"Column search error: {e}") from e
    # TODO: Add other known errors for specific error handling
    except Exception as e:
        logger.error("Unknown query execution error: {}", e)
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/upload")
async def upload_files(files: list[UploadFile]) -> MessageResponse:
    """Add new JSON documents to the Croissant store."""
    for file in files:
        if file.filename is None:
            raise HTTPException(status_code=400, detail="No file uploaded")
        if not file.filename.endswith(".json"):
            raise HTTPException(status_code=400, detail="Only .json files are accepted")

    try:
        for file in files:
            content = await file.read()
            app_state.croissant_store.add_document(orjson.loads(content))
            logger.debug("Uploaded file: {}", file.filename)

        logger.info("{} files uploaded successfully", len(files))
        return MessageResponse(message=f"{len(files)} files uploaded successfully")
    except Exception as e:
        logger.error("Upload error: {}", e)
        logger.debug("Upload error traceback: {}", e.__traceback__)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/update_indices")
async def update_indices() -> MessageResponse:
    """Recreate all indices from the current state of the Croissant store."""
    try:
        # NOTE: Our approach increases memory usage since we load the new indices without deleting
        # the old ones, we should consider optimizing this in the future

        # Get the current configuration name for logging
        current_config = app_state.current_fainder_config
        logger.info(f"Updating indices with configuration '{current_config}'")

        # This now uses the current configuration internally
        app_state.update_indices()
        logger.info(f"Indices updated successfully with configuration '{current_config}'")
        return MessageResponse(
            message=f"Indices updated successfully with configuration '{current_config}'"
        )
    except IndexingError as e:
        logger.error("Indexing error: {}", e)
        raise HTTPException(status_code=500, detail="Indexing error") from e
    except Exception as e:
        logger.error("Unknown indexing error: {}, {}", e, e.args)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.post("/change_fainder")
async def change_fainder_config(request: FainderConfigRequest) -> MessageResponse:
    """Change the Fainder configuration to use a different index."""
    try:
        # Check if it's the same as the current config
        if request.config_name == app_state.current_fainder_config:
            return MessageResponse(
                message=f"Already using Fainder configuration '{request.config_name}'"
            )

        app_state.update_fainder_index(request.config_name)
        logger.info(f"Fainder configuration changed to '{request.config_name}' successfully")
        return MessageResponse(
            message=f"Fainder configuration changed to '{request.config_name}' successfully"
        )
    except FileNotFoundError as e:
        logger.error(f"Fainder configuration error: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unknown error changing Fainder configuration: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/fainder_configs")
async def get_fainder_configs() -> FainderConfigsResponse:
    """Get the list of available Fainder configurations and the current active one."""
    try:
        config_path = app_state.settings.fainder_config_path
        current_config = app_state.current_fainder_config

        if not config_path.exists():
            return FainderConfigsResponse(configs=["default"], current=current_config)

        configs = load_json(config_path)
        return FainderConfigsResponse(configs=list(configs.keys()), current=current_config)
    except Exception as e:
        logger.error(f"Error getting Fainder configurations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@app.get("/cache_statistics")
async def cache_statistics() -> CacheInfo:
    """Return statistics about the query result cache."""
    return app_state.engine.cache_info()


@app.get("/clear_cache")
async def clear_cache() -> MessageResponse:
    """Clear the query result cache."""
    app_state.engine.clear_cache()
    logger.info("Cache cleared successfully")
    return MessageResponse(message="Cache cleared successfully")


# TODO: Recreate the alternative benchmarking endpoints with the new objects/approach
