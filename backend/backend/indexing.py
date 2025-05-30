import argparse
import os
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import hnswlib
import numpy as np
import tantivy
from fainder.preprocessing.clustering import cluster_histograms
from fainder.preprocessing.percentile_index import create_index
from fainder.typing import Histogram
from fainder.utils import configure_run, save_output
from loguru import logger
from sentence_transformers import SentenceTransformer

from backend.config import Settings
from backend.indices import TantivyIndex, get_tantivy_schema
from backend.utils import dump_json, load_json

if TYPE_CHECKING:
    from numpy.typing import NDArray


def _prepare_document_for_tantivy(json_doc: dict[str, Any]) -> None:
    """Modify the document to be ingested by Tantivy."""
    if "keywords" in json_doc:
        keywords: list[Any] = json_doc["keywords"]
        json_doc["keywords"] = "; ".join(str(keyword) for keyword in keywords)

    if (
        "creator" in json_doc
        and isinstance(json_doc["creator"], dict)
        and "name" in json_doc["creator"]
    ):
        json_doc["creator"] = json_doc["creator"]["name"]

    if (
        "publisher" in json_doc
        and isinstance(json_doc["publisher"], dict)
        and "name" in json_doc["publisher"]
    ):
        json_doc["publisher"] = json_doc["publisher"]["name"]


def generate_metadata(
    croissant_path: Path, metadata_path: Path, tantivy_path: Path, return_documents: bool = True
) -> tuple[
    list[tuple[np.uint32, Histogram]], dict[str, int], dict[int, dict[str, Any]], TantivyIndex
]:
    """Load Croissant files and generate metadata.

    While loading the files, assign unique IDs to documents, columns, histograms, and vectors.
    This function also creates and stores mappings between entities that are needed for
    downstream processing.
    """
    # Initialize mappings
    # NOTE: We need the vector_id intermediate step because hnswlib requires int IDs for vectors
    doc_to_cols: dict[int, set[int]] = defaultdict(set)
    doc_to_path: list[str] = []
    name_to_vector: dict[str, int] = {}
    vector_to_cols: dict[int, set[int]] = defaultdict(set)

    json_docs: dict[int, dict[str, Any]] = {}
    tantivy_docs: list[tantivy.Document] = []
    tantivy_schema = get_tantivy_schema()

    # First pass: count the number of histograms
    logger.info("Counting histograms")
    num_hists = 0
    num_cols = 0
    for path in croissant_path.iterdir():
        json_doc = load_json(path)
        for record_set in json_doc.get("recordSet", []):
            fields = record_set.get("field", [])
            num_hists += sum(1 for col in fields if "histogram" in col)
            num_cols += len(fields)

    logger.info("Found {} histograms and {} columns", num_hists, num_cols)

    # We need to pre-allocate the column ID mapping since we insert at different indices
    col_to_doc: list[int] = [-1] * num_cols

    # Second pass: process the documents with the updated column IDs
    logger.info("Processing documents")
    hists: list[tuple[np.uint32, Histogram]] = []
    vector_id = 0
    col_id_hist = 0
    col_id_no_hist = num_hists

    for doc_id, path in enumerate(sorted(croissant_path.iterdir())):
        # Read the file and add a document ID to it
        json_doc = load_json(path)
        json_doc["id"] = doc_id
        if return_documents:
            json_docs[doc_id] = json_doc

        # Ingest histograms and assign unique ids to columns
        try:
            for record_set in json_doc["recordSet"]:
                for col in record_set["field"]:
                    if "histogram" in col:
                        col_id = col_id_hist
                        densities = np.array(col["histogram"]["densities"], dtype=np.float32)
                        bins = np.array(col["histogram"]["bins"], dtype=np.float64)
                        hists.append((np.uint32(col_id_hist), (densities, bins)))
                        col["histogram"]["id"] = col_id_hist
                        col_id_hist += 1
                    else:
                        col_id = col_id_no_hist
                        col_id_no_hist += 1

                    col["id"] = col_id
                    doc_to_cols[doc_id].add(col_id)
                    col_to_doc[col_id] = doc_id

                    col_name = col["name"]
                    if col_name not in name_to_vector:
                        name_to_vector[col_name] = vector_id
                        vector_id += 1
                    vector_to_cols[name_to_vector[col_name]].add(col_id)
        except KeyError as e:
            logger.error("KeyError {} reading file {}", e, path)

        # Store the document path for file-based Croissant stores
        doc_to_path.append(path.name)

        # Replace the original file with the extended document
        dump_json(json_doc, path)

        # Prepare document for Tantivy indexing
        _prepare_document_for_tantivy(json_doc)
        tantivy_docs.append(tantivy.Document.from_dict(json_doc, tantivy_schema))  # pyright: ignore[reportUnknownMemberType]

    logger.info(
        "Found {} documents with {} columns and {} histograms.",
        len(doc_to_cols),
        len(col_to_doc),
        num_hists,
    )

    # Index the documents in Tantivy (we index all documents at once to increase performance)
    logger.info("Initializing Tantivy index")
    tantivy_index = TantivyIndex(tantivy_path, recreate=True)
    tantivy_index.add_documents(tantivy_docs)

    # Save the mappings and indices
    logger.info("Saving metadata")
    dump_json(
        {
            "doc_to_cols": {str(k): list(v) for k, v in doc_to_cols.items()},
            "doc_to_path": doc_to_path,
            "col_to_doc": col_to_doc,
            "num_hists": num_hists,
            "name_to_vector": name_to_vector,
            "vector_to_cols": {str(k): list(v) for k, v in vector_to_cols.items()},
        },
        metadata_path,
    )

    return hists, name_to_vector, json_docs, tantivy_index


def generate_fainder_indices(
    hists: Sequence[tuple[int | np.integer[Any], Histogram]],
    output_path: Path,
    config_name: str = "default",
    n_clusters: int = 27,
    bin_budget: int = 270,
    alpha: float = 1,
    transform: Literal["standard", "robust", "quantile", "power"] | None = None,
    algorithm: Literal["agglomerative", "hdbscan", "kmeans"] = "kmeans",
    seed: int = 42,
    workers: int | None = os.cpu_count(),
) -> None:
    logger.info(f"Starting Fainder index generation with config '{config_name}'")

    logger.info("Clustering {} histograms", len(hists))
    clustered_hists, cluster_bins, _ = cluster_histograms(
        hists=hists,
        transform=transform,
        quantile_range=(0.25, 0.75),
        algorithm=algorithm,
        n_cluster_range=(n_clusters, n_clusters),
        n_global_bins=bin_budget,
        alpha=alpha,
        seed=seed,
        workers=workers,
        verbose=False,
    )

    logger.info("Creating rebinning index")
    rebinning_index, _, _ = create_index(
        clustered_hists=clustered_hists,
        cluster_bins=cluster_bins,
        index_method="rebinning",
        workers=workers,
    )

    logger.info("Creating conversion index")
    conversion_index, _, _ = create_index(
        clustered_hists=clustered_hists,
        cluster_bins=cluster_bins,
        index_method="conversion",
        workers=workers,
    )

    # Save indices with config name in the filename
    rebinning_file = f"{config_name}_rebinning.zst"
    conversion_file = f"{config_name}_conversion.zst"

    save_output(
        output_path / rebinning_file,
        (rebinning_index, cluster_bins),
        name=f"rebinning index ({config_name})",
    )
    save_output(
        output_path / conversion_file,
        (conversion_index, cluster_bins),
        name=f"conversion index ({config_name})",
    )

    # Save or update the config information in a JSON file
    config_file = output_path / "configs.json"
    configs = {}
    if config_file.exists():
        configs = load_json(config_file)

    # Add or update the config
    configs[config_name] = {
        "n_clusters": n_clusters,
        "bin_budget": bin_budget,
        "alpha": alpha,
        "transform": transform,
        "algorithm": algorithm,
        "rebinning_file": rebinning_file,
        "conversion_file": conversion_file,
    }

    dump_json(configs, config_file)

    # For the default config, also save with the default filenames for backward compatibility
    if config_name == "default":
        save_output(
            output_path / "rebinning.zst", (rebinning_index, cluster_bins), name="rebinning index"
        )
        save_output(
            output_path / "conversion.zst",
            (conversion_index, cluster_bins),
            name="conversion index",
        )

    save_output(output_path / "histograms.zst", hists, name="histograms")


def generate_embedding_index(
    name_to_vector: dict[str, int],
    output_path: Path,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 32,
    show_progress_bar: bool = True,
    precision: Literal["float32", "int8", "uint8", "binary", "ubinary"] = "float32",
    normalize_embeddings: bool = True,
    ef_construction: int = 400,
    n_bidirectional_links: int = 64,
    seed: int = 42,
) -> None:
    strings = list(name_to_vector.keys())
    ids = np.array(list(name_to_vector.values()), dtype=np.uint64)

    logger.info("Generating embeddings")
    embedder = SentenceTransformer(
        model_name_or_path=model_name,
        cache_folder=(output_path / "model_cache").as_posix(),
        # Possibly use ONNX, see: https://github.com/lbhm/fainder-demo/issues/102
        # backend="onnx",
        # model_kwargs={"file_name": "onnx/model_O2.onnx"},
    )
    # Maybe remove the module compilation if it does not help with performance
    embedder.compile()  # type: ignore[no-untyped-call]
    embeddings: NDArray[np.float32] = embedder.encode(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        sentences=strings,
        batch_size=batch_size,
        show_progress_bar=show_progress_bar,
        convert_to_numpy=True,
        precision=precision,
        normalize_embeddings=normalize_embeddings,
    )

    logger.info("Creating HNSW index")
    index = hnswlib.Index(space="cosine", dim=embeddings.shape[1])
    index.init_index(
        max_elements=embeddings.shape[0],
        ef_construction=ef_construction,
        M=n_bidirectional_links,
        random_seed=seed,
    )
    index.add_items(embeddings, ids)

    logger.info("Saving HNSW index")
    index.save_index((output_path / "index.bin").as_posix())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate metadata and indices for a collection of dataset profiles"
    )
    parser.add_argument(
        "--no-fainder", action="store_true", help="Skip generating Fainder indices"
    )
    parser.add_argument(
        "--no-embeddings", action="store_true", help="Skip generating embedding index"
    )
    parser.add_argument(
        "--log-level",
        default=None,
        type=str,
        choices=["DEBUG", "INFO", "WARNING"],
        help="Set the logging level",
    )
    parser.add_argument(
        "--config-name",
        default="default",
        type=str,
        help="Configuration name for the Fainder indices",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    try:
        settings = Settings()  # type: ignore[call-arg]
        if args.log_level is None:
            configure_run(settings.log_level)
        else:
            configure_run(args.log_level)
        logger.debug(settings.model_dump())
    except Exception as e:  # noqa: BLE001
        logger.error("Error loading settings: {}", e)
        sys.exit(1)

    hists, name_to_vector, _, _ = generate_metadata(  # type: ignore[assignment]
        settings.croissant_path,
        settings.metadata_path,
        settings.tantivy_path,
        return_documents=False,
    )

    if not args.no_fainder:
        generate_fainder_indices(
            hists=hists,
            output_path=settings.fainder_path,
            config_name=args.config_name,
            n_clusters=settings.fainder_n_clusters,
            bin_budget=settings.fainder_bin_budget,
            alpha=settings.fainder_alpha,
            transform=settings.fainder_transform,
            algorithm=settings.fainder_cluster_algorithm,
        )

    if not args.no_embeddings:
        generate_embedding_index(
            name_to_vector=name_to_vector,
            output_path=settings.embedding_path,
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
            ef_construction=settings.hnsw_ef_construction,
            n_bidirectional_links=settings.hnsw_n_bidirectional_links,
        )
