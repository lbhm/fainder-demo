#!/bin/bash

set -euxo pipefail
cd "$(git rev-parse --show-toplevel)"

# Backend setup
(
    cd backend || exit
    uv sync
    uv run pre-commit install
)

# UI setup
(
    cd ui || exit
    npm install
)
