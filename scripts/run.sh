#!/bin/bash

set -euxo pipefail
cd "$(git rev-parse --show-toplevel)"

# Start backend
(
    cd backend || exit
    fastapi dev main.py
)

# Start UI
(
    cd ui || exit
    npm run dev
)
