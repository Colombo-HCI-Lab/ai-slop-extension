#!/bin/bash

# Reset database schema script for FastAPI backend
# This script drops and recreates the database, then runs migrations

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔄 Resetting database schema...${NC}"

# Database configuration
DB_NAME="ai_slop_extension"
DB_USER="postgres"
DB_PASSWORD="cats"
DB_HOST="localhost"
DB_PORT="5432"

# Function to execute PostgreSQL commands
execute_psql() {
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -c "$1" 2>&1
}

# Function to execute PostgreSQL commands on specific database
execute_psql_db() {
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d "$1" -c "$2" 2>&1
}

echo -e "${YELLOW}Step 1: Terminating active connections...${NC}"
execute_psql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();" > /dev/null 2>&1 || true

echo -e "${YELLOW}Step 2: Dropping existing database...${NC}"
execute_psql "DROP DATABASE IF EXISTS $DB_NAME;" > /dev/null || {
    echo -e "${RED}Failed to drop database. It might not exist.${NC}"
}

echo -e "${YELLOW}Step 3: Creating new database...${NC}"
execute_psql "CREATE DATABASE $DB_NAME;" || {
    echo -e "${RED}Failed to create database!${NC}"
    exit 1
}

echo -e "${GREEN}✅ Database recreated successfully${NC}"

echo -e "${YELLOW}Step 4: Running Alembic migrations...${NC}"

# Change to the backend directory (parent of scripts directory)
cd "$(dirname "$0")/.."

# Check if we're in the backend directory
if [ ! -f "alembic.ini" ]; then
    echo -e "${RED}Error: alembic.ini not found. Cannot locate backend directory.${NC}"
    exit 1
fi

# Run migrations
uv run alembic upgrade head || {
    echo -e "${RED}Failed to run migrations!${NC}"
    exit 1
}

echo -e "${GREEN}✅ Migrations applied successfully${NC}"

# Optional: Show current database tables
echo -e "${YELLOW}Step 5: Verifying database structure...${NC}"
TABLES=$(execute_psql_db "$DB_NAME" "\dt" | grep -E '^\s+public\s+\|' | awk '{print $3}' | tr '\n' ', ' | sed 's/,$//')

if [ -n "$TABLES" ]; then
    echo -e "${GREEN}✅ Tables created: $TABLES${NC}"
else
    echo -e "${RED}Warning: No tables found in database${NC}"
fi

# Show migration status
echo -e "${YELLOW}Step 6: Current migration status:${NC}"
uv run alembic current

echo -e "${GREEN}✨ Database schema reset complete!${NC}"
echo -e "${GREEN}You can now start the server with: uv run python -m uvicorn main:app --reload --port 4000${NC}"