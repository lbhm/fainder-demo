#!/bin/bash

set -euxo pipefail
cd "$(git rev-parse --show-toplevel)"

(
    cd backend || exit
    python -m grpc_tools.protoc \
        -I proto \
        --python_out=. \
        --grpc_python_out=. \
        --mypy_out=. \
        --mypy_grpc_out=. \
        proto/backend/proto/lucene_connector.proto

)
(
    cd lucene || exit
    mvn clean compile
)
