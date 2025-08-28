#!/bin/bash

# Start the FastAPI backend server
cd "$(dirname "$0")/.."
uv run python -m uvicorn main:app --host 0.0.0.0 --port 4000 --workers 1
