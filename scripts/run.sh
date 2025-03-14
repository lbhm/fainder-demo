#!/bin/bash

set -euxo pipefail
cd "$(git rev-parse --show-toplevel)"

# Fainder service
(
    cd backend || exit
    fastapi dev main.py
)

# UI
(
    cd ui || exit
    npm run dev
)
