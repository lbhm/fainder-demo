import copy
import time
import traceback
from typing import Any

import orjson
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from lark import UnexpectedInput
from loguru import logger

from backend.config import (
    CacheInfo,
    ColumnHighlights,
    ColumnSearchError,
    CroissantStoreType,
    DocumentHighlights,
    FainderError,
    IndexingError,
    MessageResponse,
    Metadata,
    QueryRequest,
    QueryResponse,
    Settings,
    configure_logging,
)
from backend.croissant_store import Document, get_croissant_store
from backend.engine import Engine
from backend.indexing import (
    generate_embedding_index,
    generate_fainder_indices,
    generate_metadata,
)
from backend.indices import FainderIndex, HnswIndex, TantivyIndex
from backend.util import load_json

logger.info("Starting backend")

# Load global variables to store persistent objects
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

logger.info("Loading metadata")
metadata = Metadata(**load_json(settings.metadata_path))

logger.info("Initializing Croissant store")
croissant_store = get_croissant_store(
    store_type=settings.croissant_store_type,
    base_path=settings.croissant_path,
    doc_to_path=metadata.doc_to_path,
    dataset_slug=settings.dataset_slug,
    cache_size=settings.croissant_cache_size,
)

logger.info("Initializing tantivy index")
tantivy_index = TantivyIndex(settings.tantivy_path)

logger.info("Initializing Fainder index")
fainder_index = FainderIndex(
    rebinning_path=settings.rebinning_index_path,
    conversion_path=settings.conversion_index_path,
    histogram_path=settings.histogram_path,
)

logger.info("Initializing HNSW index")
hnsw_index = HnswIndex(
    settings.hnsw_index_path,
    metadata,
    model=settings.embedding_model,
    use_embeddings=settings.use_embeddings,
    ef=settings.hnsw_ef,
)

logger.info("Initializing engine")
engine = Engine(
    tantivy_index=tantivy_index,
    fainder_index=fainder_index,
    hnsw_index=hnsw_index,
    metadata=metadata,
    cache_size=settings.query_cache_size,
)

logger.info("Initializing FastAPI app")
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
    logger.trace(f"Processing field: {field} and highlighting: {highlighted}")
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
        doc_ids, (doc_highlights, col_highlights) = engine.execute(
            query=request.query,
            fainder_mode=request.fainder_mode,
            enable_highlighting=request.enable_highlighting,
            min_usability_score=settings.min_usability_score,
            use_usability_score=settings.use_usability_score,
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
        logger.info(
            f"Bad user query:\n{e.get_context(request.query).strip()}\n"
            f"(line {e.line}, column {e.column})"
        )
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
    """Add new JSON documents to the Croissant store."""
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")
        if not file.filename.endswith(".json"):
            raise HTTPException(status_code=400, detail="Only .json files are accepted")

    try:
        for file in files:
            content = await file.read()
            croissant_store.add_document(orjson.loads(content))
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
        hists, name_to_vector, documents, tantivy_index = generate_metadata(
            croissant_path=settings.croissant_path,
            metadata_path=settings.metadata_path,
            tantivy_path=settings.tantivy_path,
            return_documents=settings.croissant_store_type == CroissantStoreType.DICT,
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

        # Delete metadata variables before we load the entire metadata again to save memory
        del hists, name_to_vector, documents

        # Update global variables
        metadata = Metadata(**load_json(settings.metadata_path))
        croissant_store.replace_documents(metadata.doc_to_path)

        fainder_index.update(
            rebinning_path=settings.rebinning_index_path,
            conversion_path=settings.conversion_index_path,
            histogram_path=settings.histogram_path,
        )
        hnsw_index.update(path=settings.hnsw_index_path, metadata=metadata)
        engine.update_indices(
            fainder_index=fainder_index,
            tantivy_index=tantivy_index,
            hnsw_index=hnsw_index,
            metadata=metadata,
        )

        logger.info("Indices updated successfully")
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
    return engine.cache_info()


@app.get("/clear_cache")
async def clear_cache() -> MessageResponse:
    """Clear the query result cache."""
    engine.clear_cache()
    logger.info("Cache cleared successfully")
    return MessageResponse(message="Cache cleared successfully")


# TODO: Recreate the alternative benchmarking endpoints with the new objects/approach
