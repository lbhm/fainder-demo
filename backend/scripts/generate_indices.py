import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Literal

import hnswlib  # type: ignore
import numpy as np
from fainder.preprocessing.clustering import cluster_histograms
from fainder.preprocessing.percentile_index import create_index
from fainder.typing import Histogram
from fainder.utils import configure_run, save_output
from loguru import logger
from sentence_transformers import SentenceTransformer


def load_metadata(base_path: Path) -> tuple[list[tuple[np.uint32, Histogram]], dict[str, int]]:
    """Load Croissant files and generate metadata.

    While loading the files, assign unique IDs to documents and columns. The function also creates
    and stores mappings between document IDs, columns IDs, and column names that are needed for
    downstream processing.
    """
    croissant_dir = base_path / "croissant"
    metadata_file = base_path / "metadata.json"

    # Initialize mappings
    # NOTE: We need the vector_id intermediate step because annoy and faiss require integer IDs
    doc_to_cols: dict[int, set[int]] = defaultdict(set)
    col_to_doc: dict[int, int] = {}
    col_to_hist: dict[int, int] = {}
    hist_to_col: dict[int, int] = {}
    name_to_vector: dict[str, int] = {}
    vector_to_cols: dict[int, set[int]] = defaultdict(set)

    # Ingest Croissant files and assign unique ids to datasets and columns
    hists: list[tuple[np.uint32, Histogram]] = []
    col_id = 0
    hist_id = 0
    vector_id = 0

    logger.info("Reading croissant files")
    # NOTE: Remove the sorting if it becomes a bottleneck
    for doc_id, path in enumerate(sorted(croissant_dir.iterdir())):
        if path.is_file():
            # Read the file and add a document ID to it
            with path.open("r") as file:
                metadata = json.load(file)

            metadata["id"] = doc_id

            # Ingest histograms and assign unique ids to columns
            try:
                for record_set in metadata["recordSet"]:
                    for col in record_set["field"]:
                        col_name = col["name"]
                        doc_to_cols[doc_id].add(col_id)
                        col_to_doc[col_id] = doc_id
                        col["id"] = col_id

                        if "histogram" in col:
                            densities = np.array(col["histogram"]["densities"], dtype=np.float32)
                            bins = np.array(col["histogram"]["bins"], dtype=np.float64)

                            hists.append((np.uint32(hist_id), (densities, bins)))
                            col_to_hist[col_id] = hist_id
                            hist_to_col[hist_id] = col_id
                            col["histogram"]["id"] = hist_id
                            hist_id += 1

                        if col_name not in name_to_vector:
                            name_to_vector[col_name] = vector_id
                            vector_id += 1
                        vector_to_cols[name_to_vector[col_name]].add(col_id)

                        col_id += 1
            except KeyError as e:
                logger.error(f"KeyError {e} reading file {path}")

            # Replace the file with the updated metadata
            with path.open("w") as file:
                json.dump(metadata, file)

    logger.info(
        f"Found {len(doc_to_cols)} documents with {len(col_to_doc)} columns and "
        f"{len(hist_to_col)} histograms."
    )

    # Save the mappings and indices
    logger.info("Saving metadata")
    with metadata_file.open("w") as file:
        json.dump(
            {
                "doc_to_cols": {k: list(v) for k, v in doc_to_cols.items()},
                "col_to_doc": col_to_doc,
                "col_to_hist": col_to_hist,
                "hist_to_col": hist_to_col,
                "name_to_vector": name_to_vector,
                "vector_to_cols": {k: list(v) for k, v in vector_to_cols.items()},
            },
            file,
        )

    return hists, name_to_vector


def generate_fainder_indices(
    hists: list[tuple[np.uint32, Histogram]],
    output_path: Path,
    n_clusters: int = 27,
    bin_budget: int = 270,
    alpha: float = 1,
    transform: Literal["standard", "robust", "quantile", "power"] | None = None,
    algorithm: Literal["agglomerative", "hdbscan", "kmeans"] = "kmeans",
    seed: int = 42,
    workers: int | None = os.cpu_count(),
) -> None:
    logger.info("Starting Fainder index generation")

    logger.info(f"Clustering {len(hists)} histograms")
    clustered_hists, cluster_bins, _ = cluster_histograms(
        hists=hists,
        transform=transform,  # type: ignore
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

    save_output(
        output_path / "rebinning.zst",
        (rebinning_index, cluster_bins),
        name="rebinning index",
    )
    save_output(
        output_path / "conversion.zst",
        (conversion_index, cluster_bins),
        name="conversion index",
    )


def generate_embedding_index(
    name_to_vector: dict[str, int],
    output_path: Path,
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 32,
    show_progress_bar: bool = True,
    precision: Literal["float32", "int8", "uint8", "binary", "ubinary"] = "float32",
    normalize_embeddings: bool = True,
    ef_construction: int = 400,
    n_bidirectional_links: int = 64,
    seed: int = 42,
) -> None:
    strings = list(name_to_vector.keys())
    ids = list(name_to_vector.values())

    logger.info("Generating embeddings")
    embedder = SentenceTransformer(
        model_name, cache_folder=(output_path / "model_cache").as_posix()
    )
    embedder.compile()  # Maybe remove this
    embeddings = embedder.encode(
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


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate metadata and indices for a collection of dataset profiles"
    )
    parser.add_argument(
        "-p", "--path", type=Path, help="Path to the root directory of a dataset collection"
    )
    parser.add_argument(
        "--no-fainder",
        action="store_true",
        help="Skip generating Fainder indices",
    )
    parser.add_argument(
        "--no-embeddigs",
        action="store_true",
        help="Skip generating embedding index",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        type=str,
        choices=["DEBUG", "INFO", "WARNING"],
        help="Set the logging level",
    )

    # TODO: add more params: bin budget, n_clusters, alpha, seed, workers, etc
    # TODO: add all the params from HNSW creation

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    configure_run(args.log_level)
    hists, name_to_vector = load_metadata(args.path)

    if not args.no_fainder:
        generate_fainder_indices(
            hists=hists,
            output_path=args.path / "fainder",
        )

    if not args.no_embeddigs:
        generate_embedding_index(name_to_vector, output_path=args.path / "embeddings")
