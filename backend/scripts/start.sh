#!/bin/bash

# Change to backend directory
cd "$(dirname "$0")/.."

# Kill any running backend processes
echo "🛑 Killing existing backend processes..."
./scripts/kill.sh

echo "🔄 Starting backend..."
uv run python -m uvicorn main:app --host 0.0.0.0 --port 4000 --workers 1
