# Fainder (rebinning and coversion)
# Mappings from metadata.json
# HNSW index and column name embeddings

import argparse

# hists: dict[int, Any] maps to fileID and columnName
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Literal

import numpy as np
from fainder.preprocessing.clustering import cluster_histograms
from fainder.preprocessing.percentile_index import create_index
from fainder.typing import Histogram
from fainder.utils import save_output, unlink_pointers
from loguru import logger


def generate_indices(base_path: Path) -> None:
    doc_ids: set[int] = set()
    column_to_hists: dict[str, set[int]] = defaultdict(set)
    hist_to_doc: dict[int, int] = {}
    doc_to_hists: dict[int, set[int]] = defaultdict(set)
    path = base_path / "croissant"

    # read hists from croissant directory and update the mappings

    hist_id = 0

    hists: list[tuple[np.uint32, Histogram]] = []

    logger.info("Reading histograms")

    for record_number, file in enumerate(sorted(path.iterdir())):
        if file.is_file():
            # read the file and add record_number as id to it
            with open(file, "r") as f:
                metadata = json.load(f)

            if "jsonld" in metadata:
                metadata = metadata["jsonld"]
            
            metadata["id"] = record_number
            # replace the file with the updated metadata
            with open(file, "w") as f:
                json.dump(metadata, f)

            

            doc_ids.add(record_number)
            doc_to_hists[record_number] = set()

            try:
                # loop through all the files
                for record_set in metadata["recordSet"]:
                    for column in record_set["field"]:
                        if "histogram" in column:
                            column_name = column["name"]
                            column_to_hists[column_name].add(hist_id)
                            doc_to_hists[record_number].add(hist_id)
                            hist_to_doc[hist_id] = record_number
                            hist_id += 1

                            bins = column["histogram"]["bins"]
                            densities = column["histogram"]["densities"]

                            bins = np.array(bins, dtype=np.float64)
                            densities = np.array(densities, dtype=np.float32)

                            hists.append((np.uint32(record_number), (densities, bins)))
            except KeyError:
                logger.error(f"KeyError reading file {file}")

    logger.info(f"Clustering histograms: {len(hists)}")

    # cluster the histograms
    quantile_range = (0.25, 0.75)
    algorithm: Literal["agglomerative", "hdbscan", "kmeans"] = "kmeans"
    n_cluster_range = (2, 5)
    bin_budget = 1000
    alpha = 0.0
    seed = 42
    # TODO: None does not work
    transform: Literal["standard", "robust", "quantile", "power"] = "standard"
    clustered_hists, cluster_bins, features = cluster_histograms(
        hists,
        transform,
        quantile_range,
        True,
        algorithm,
        n_cluster_range,
        bin_budget,
        alpha,
        seed,
        os.cpu_count(),
        True,
    )

    # create the rebinning index
    rebinning: Literal["rebinning", "rebinning-shm", "conversion", "conversion-shm"] = "rebinning"
    conversion: Literal["rebinning", "rebinning-shm", "conversion", "conversion-shm"] = (
        "conversion"
    )
    index_precision: Literal["float16", "float32", "float64", "float128"] = "float16"
    bin_estimation: Literal["continuous_value", "cubic_spline"] = "continuous_value"
    try:
        pctl_index_rebinning, _, shm_pointers = create_index(
            clustered_hists,
            cluster_bins,
            rebinning,
            index_precision,
            bin_estimation,
            os.cpu_count(),
        )

        pctl_index_conversion, _, shm_pointers2 = create_index(
            clustered_hists,
            cluster_bins,
            conversion,
            index_precision,
            bin_estimation,
            os.cpu_count(),
        )

    finally:
        if shm_pointers is not None:
            unlink_pointers(shm_pointers)

        if shm_pointers2 is not None:
            unlink_pointers(shm_pointers2)

    # save the mappings and indices
    with open(base_path / "metadata.json", "w") as f:
        new_column_to_hists = {k: list(v) for k, v in column_to_hists.items()}
        new_doc_to_hists = {k: list(v) for k, v in doc_to_hists.items()}

        json.dump(
            {
                "doc_ids": list(doc_ids),
                "column_to_hists": new_column_to_hists,
                "hist_to_doc": hist_to_doc,
                "doc_to_hists": new_doc_to_hists,
            },
            f,
        )

    save_output(
        base_path / "fainder" / "conversion.zst",
        (pctl_index_rebinning, cluster_bins),
        name="index",
    )

    save_output(
        base_path / "fainder" / "rebinning.zst",
        (pctl_index_conversion, cluster_bins),
        name="index",
    )


def parse_args():
    parser = argparse.ArgumentParser(description="Generate indices for the histograms")
    parser.add_argument(
        "-p", "--path", type=Path, help="Path to the directory containing the croissant directory"
    )
    return parser.parse_args()


if __name__ == "__main__":
    # read path from
    args = parse_args()
    generate_indices(args.path)
