#!/bin/bash

# Database migration script for FastAPI backend
# This script handles database migrations and schema updates

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 FastAPI Backend Database Migration Tool${NC}"
echo "=========================================="

# Check if we're in the backend directory
if [ ! -f "alembic.ini" ]; then
    echo -e "${RED}Error: alembic.ini not found. Please run this script from the backend directory.${NC}"
    exit 1
fi

# Parse command line arguments
COMMAND=${1:-status}

# Function to show help
show_help() {
    echo "Usage: ./migrate.sh [command] [options]"
    echo ""
    echo "Commands:"
    echo "  status       Show current migration status (default)"
    echo "  upgrade      Apply all pending migrations"
    echo "  downgrade    Rollback last migration"
    echo "  history      Show migration history"
    echo "  create       Create a new migration"
    echo "  heads        Show current head revisions"
    echo "  clean        Remove all migration files (dangerous!)"
    echo "  help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./migrate.sh                    # Show current status"
    echo "  ./migrate.sh upgrade            # Apply all migrations"
    echo "  ./migrate.sh downgrade          # Rollback one migration"
    echo "  ./migrate.sh create \"Add user table\"  # Create new migration"
}

# Function to check database connection
check_db_connection() {
    echo -e "${YELLOW}Checking database connection...${NC}"
    uv run python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from core.config import settings

async def check():
    try:
        engine = create_async_engine(
            settings.database_url.replace('postgresql://', 'postgresql+asyncpg://'),
            echo=False
        )
        async with engine.connect() as conn:
            from sqlalchemy import text
            await conn.execute(text('SELECT 1'))
        await engine.dispose()
        print('✅ Database connection successful')
        return True
    except Exception as e:
        print(f'❌ Database connection failed: {e}')
        return False

asyncio.run(check())
" || {
    echo -e "${RED}Cannot connect to database. Please check your configuration.${NC}"
    exit 1
}
}

case "$COMMAND" in
    status)
        echo -e "${YELLOW}📊 Current migration status:${NC}"
        check_db_connection
        uv run alembic current --verbose
        echo ""
        echo -e "${YELLOW}📝 Pending migrations:${NC}"
        uv run alembic history --verbose | head -10
        ;;
    
    upgrade)
        echo -e "${YELLOW}⬆️  Applying migrations...${NC}"
        check_db_connection
        
        # Show current status first
        echo -e "${BLUE}Current status:${NC}"
        uv run alembic current
        
        # Apply migrations
        uv run alembic upgrade head
        
        echo -e "${GREEN}✅ Migrations applied successfully!${NC}"
        echo -e "${BLUE}New status:${NC}"
        uv run alembic current
        ;;
    
    downgrade)
        echo -e "${YELLOW}⬇️  Rolling back last migration...${NC}"
        check_db_connection
        
        # Show current status first
        echo -e "${BLUE}Current status:${NC}"
        uv run alembic current
        
        # Rollback one migration
        uv run alembic downgrade -1
        
        echo -e "${GREEN}✅ Rollback successful!${NC}"
        echo -e "${BLUE}New status:${NC}"
        uv run alembic current
        ;;
    
    history)
        echo -e "${YELLOW}📜 Migration history:${NC}"
        uv run alembic history --verbose
        ;;
    
    create)
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please provide a migration message${NC}"
            echo "Usage: ./migrate.sh create \"Your migration message\""
            exit 1
        fi
        
        MESSAGE="$2"
        echo -e "${YELLOW}✨ Creating new migration: $MESSAGE${NC}"
        check_db_connection
        
        # Create migration with autogenerate
        uv run alembic revision --autogenerate -m "$MESSAGE"
        
        echo -e "${GREEN}✅ Migration created successfully!${NC}"
        echo -e "${YELLOW}Review the generated migration file and run './migrate.sh upgrade' to apply it.${NC}"
        ;;
    
    heads)
        echo -e "${YELLOW}🎯 Current head revisions:${NC}"
        uv run alembic heads
        ;;
    
    clean)
        echo -e "${RED}⚠️  WARNING: This will remove all migration files!${NC}"
        echo -n "Are you sure you want to continue? (yes/no): "
        read CONFIRM
        
        if [ "$CONFIRM" = "yes" ]; then
            echo -e "${YELLOW}Cleaning migration files...${NC}"
            rm -f db/migrations/versions/*.py
            echo -e "${GREEN}✅ Migration files removed${NC}"
            echo -e "${YELLOW}Run './migrate.sh create \"Initial migration\"' to create a new initial migration${NC}"
        else
            echo -e "${BLUE}Operation cancelled${NC}"
        fi
        ;;
    
    help)
        show_help
        ;;
    
    *)
        echo -e "${RED}Unknown command: $COMMAND${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

echo ""
echo -e "${BLUE}Done!${NC}"