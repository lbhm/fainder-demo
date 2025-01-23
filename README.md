<!-- markdownlint-disable MD033 -->
<p align="center">
  <picture>
    <img alt="Fainder logo" src="https://github.com/user-attachments/assets/41686649-f1c1-4b60-824e-80c322c5da85" width="300">
  </picture>
</p>

# Fainder Demo

![Python Version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Flbhm%2Ffainder-demo%2Fmain%2Fpyproject.toml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![GitHub License](https://img.shields.io/github/license/lbhm/fainder-demo)

This repository contains the source code for our demonstration of Fainder, a fast and accurate
index for distibution-aware dataset search. The demo consists of three components:

- **Frontend**: Web-based user interface for interacting with the search engine.
- **Backend**: Responsible for query parsing and processing [percentile predicates](https://doi.org/10.14778/3681954.3681999).
- **Lucene**: An extension of [Apache Lucene](https://lucene.apache.org/) for handling keyword predicates.

The repository is structured as follows:

```bash
fainder/
├── backend  # main component for query parsing and execution (Python)
├── data  # placeholder for dataset profiles and index files
├── lucene  # Lucene extension for executing keyword queries (Java)
├── scripts  # scripts for installing and starting components (Bash)
└── ui  # user interface (JavaScript)
```

## Getting Started

### Environment Configuration

The demo uses environment variables to configure its components. You can export these variables
in your shell or create a `.env` file in the directory from where you start each component. The
following variables are available (no default means it must be set):

```bash
# Frontend
NUXT_API_BASE=http://localhost:8000  # Backend API base URL

# General backend
DATA_DIR=                    # Directory containing dataset collections
COLLECTION_NAME=             # Name of the dataset collection (subdirectoy in DATA_DIR)
CROISSANT_DIR=croissant      # Subdirectory containing the Croissant files of a collection
EMBEDDING_DIR=embeddings     # Subdirectory containing a HNSW index with column names
FAINDER_DIR=fainder          # Subdirectory containing Fainder indices for a collection
LUCENE_DIR=lucene            # Subdirectory containing a Lucene index for keyword predicates
METADATA_FILE=metadata.json  # JSON or Pickle file with metadata about a collection
QUERY_CACHE_SIZE=128         # Maximum number of query resuls to cache

# Lucene
LUCENE_HOST=127.0.0.1        # Hostname of the Lucene service
LUCENE_PORT=8001             # Port of the Lucene service
LUCENE_MAX_RESULTS=100       # Maximum number of results returned by Lucene for a keyword predicate
LUCENE_MIN_SCORE=1.0         # Minimum score for a keyword predicate to be considered

# Fainder
FAINDER_N_CLUSTERS=50
FAINDER_BIN_BUDGET=1000
FAINDER_ALPHA=1.0
FAINDER_TRANSFORM=None
FAINDER_CLUSTER_ALGORITHM=kmeans

# Embeddings
USE_EMBEDDINGS=True
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_BATCH_SIZE=32
HNSW_EF_CONSTRUCTION=400
HNSW_N_BIDIRECTIONAL_LINKS=64
HNSW_EF=50
```

### Data Preparation

You only need to bring a collection of Croissant files enriched with statistical information to
use our demo. All index datastructures are generated automatically by the backend. For that, you
must place your Croissant files into a folder and set the `DATA_DIR` and `COLLECTION_NAME`
accordingly (see above, we recommend `./data/<collection_name/croissant` if you want to use the
Docker setup).

**Note:** Currently, you have to manually have to trigger the intial index creation. To do so, you
have to install the `backend` dependencies and run the following command:

```bash
python -m backend.indexing
```

<!-- The backend automtically generates the necessary index files for Fainder, HNSW, and Lucene if
the respective folders do not exist. In order to recreate the indices, delete the folders and
restart the apllication or call the `/update_indices` endpoint. -->

### Run with Docker

You need a recent version of Docker including `docker compose` to run the demo.

Build and start the demo:

```bash
docker compose up --build
```

To stop the containers, hit `Ctrl+C` or run:

```bash
docker compose down
```

### Run Locally

#### Prerequisites

- Python 3.11 or greater
- Java 21 or greater
- Node.js 18 or greater
- `maven` (Java build tool)
- `npm` (Node.js package manager)
- `pip` (Python package manager)

#### Installation

TODO

#### Developer Setup

```bash
# Follow the steps above until you have activated your virtual environment
pip install -e ".[dev]"
pre-commit install
```

## Generating gRPC Code

The Fainder backend uses gRPC to communicate with the Lucene service. To generate the necessary
code, install the development dependencies in `backend/` and run `scripts/gen_proto.sh`.
