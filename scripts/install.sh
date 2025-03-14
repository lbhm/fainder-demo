#!/bin/bash

# UI setup
(
    cd ui || exit
    npm install
)

# Backend setup
(
    cd backend || exit
    uv sync
    uv run pre-commit install
)
