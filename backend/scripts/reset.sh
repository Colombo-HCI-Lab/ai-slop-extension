#!/bin/bash

# Reset the entire backend: kill processes, reset database, and start fresh

# Change to backend directory
cd "$(dirname "$0")/.."

echo "🔄 Resetting backend..."

# Kill any running backend processes
echo "🛑 Killing existing backend processes..."
./scripts/kill.sh

# Reset the database schema
echo "🗄️ Resetting database schema..."
./scripts/reset-schema.sh

# Remove tmp data
rm -rf tmp

# Start the backend server
echo "🚀 Starting backend server..."
./scripts/start.sh
