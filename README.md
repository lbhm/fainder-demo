<!-- markdownlint-disable MD028 -->
<!-- markdownlint-disable MD033 -->
<p align="center">
  <picture>
    <img alt="Fainder logo" src="https://github.com/user-attachments/assets/41686649-f1c1-4b60-824e-80c322c5da85" width="300">
  </picture>
</p>

# Fainder Demo

![Python Version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Flbhm%2Ffainder-demo%2Fmain%2Fpyproject.toml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![GitHub License](https://img.shields.io/github/license/lbhm/fainder-demo)

This repository contains the source code for our demonstration of Fainder, a fast and accurate
index for distibution-aware dataset search. The demo consists of two components:

- **Frontend**: Web-based user interface for interacting with the search engine.
- **Backend**: Responsible for query parsing, optimization, and execution (including [percentile predicates](https://doi.org/10.14778/3681954.3681999)).

The repository is structured as follows:

```bash
fainder/
├── backend  # main component for query parsing, optimization, and execution (Python)
├── data  # placeholder for dataset profiles and index files
├── scripts  # scripts for installing and starting components (Bash)
└── ui  # user interface (Vue)
```

## Getting Started

### Environment Configuration

Our system uses environment variables to configure its components. You can export these variables
in your shell or create a `.env` file in the directory from where you start the components. The
following variables are available (no default means it must be set):

```bash
# Backend
DATA_DIR=                    # Directory containing dataset collections
COLLECTION_NAME=             # Name of the dataset collection (subdirectoy in DATA_DIR)
CROISSANT_DIR=croissant      # Subdirectory containing the Croissant files of a collection
EMBEDDING_DIR=embeddings     # Subdirectory containing a HNSW index with column names
FAINDER_DIR=fainder          # Subdirectory containing Fainder indices for a collection
TANTIVY_DIR=tantivy          # Subdirectory containing a keyword index for a collection
METADATA_FILE=metadata.json  # JSON file with metadata about a collection
QUERY_CACHE_SIZE=128         # Maximum number of query resuls to cache
DATASET_SLUG=kaggleRef       # Document field with a unique dataset identifier

# Fainder
FAINDER_N_CLUSTERS=50               # Number of index clusters
FAINDER_BIN_BUDGET=1000             # Bin/storage budget
FAINDER_ALPHA=1.0                   # Float value for additive smoothing
FAINDER_TRANSFORM=None              # None, standard, robust, quantile, or power
FAINDER_CLUSTER_ALGORITHM=kmeans    # kmeans, hdbscan, or agglomerative

# Embeddings
USE_EMBEDDINGS=True                 # Boolean to enable/disable embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2    # Name of the embedding model on Hugging Face
EMBEDDING_BATCH_SIZE=32             # Batch size for embedding generation (during indexing)
HNSW_EF_CONSTRUCTION=400            # Construction parameter for HNSW
HNSW_N_BIDIRECTIONAL_LINKS=64       # Number of bidirectional links for HNSW
HNSW_EF=50                          # Search parameter for HNSW

# Frontend
NUXT_API_BASE=http://localhost:8000 # Backend API base URL

# Misc
LOG_LEVEL=INFO                      # Logging level (TRACE, DEBUG, INFO, WARNING, ERROR)
```

### Data Preparation

You only need to bring a collection of Croissant files enriched with statistical information to
use our demo. All index datastructures are generated automatically by the backend. For that, you
must place your Croissant files into a folder and set the `DATA_DIR` and `COLLECTION_NAME`
accordingly (see above, we recommend `./data/<collection_name/croissant` if you want to use the
Docker setup).

> [!NOTE]
> Currently, you have to manually trigger the intial index creation. To do so, install the
> `backend` dependencies and run the following command:

```bash
python -m backend.indexing
```

<!-- The backend automtically generates the necessary index files for Fainder, HNSW, and Lucene if
the respective folders do not exist. In order to recreate the indices, delete the folders and
restart the apllication or call the `/update_indices` endpoint. -->

### Run with Docker

You need a recent version of Docker including Docker Compose 2.22 or later to run the demo.

Build and start the demo:

```bash
docker compose up --build
```

To stop the containers, hit `Ctrl+C` or run:

```bash
docker compose down
```

### Run Locally / Developer Setup

#### Prerequisites

- Python 3.11 or greater
- Node.js 18 or greater
- `pip` (Python package manager)
- `npm` (Node.js package manager)

#### Installation

We recommend using [`uv`](https://docs.astral.sh/uv/) to manage the development environment of the
backend component. You just have to run:

```bash
scripts/install.sh
```

> [!NOTE]
> The `pre-commit` configuration expects that you installed the Python dependencies in a virtual
> environment at `backend/.venv`. If you use a different location, you have to adjust the
> configuration accordingly.

> [!NOTE]
> `eslint` and `vue-tsc` are currently not integrated into the `pre-commit` hooks.
> Therefore, you should run `npm run lint` and `npm run typecheck` before committing UI changes.

#### Docker Development

If you want to use Docker for development, you can use the following command to start the
components in development mode:

```bash
FASTAPI_MODE=dev NUXT_MODE=dev docker compose up --build --watch
```
