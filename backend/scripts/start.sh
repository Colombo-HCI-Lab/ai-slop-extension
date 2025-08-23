#!/bin/bash

# Start the FastAPI backend server
cd "$(dirname "$0")/.."
uv run python -m uvicorn main:app --reload --port 4000
