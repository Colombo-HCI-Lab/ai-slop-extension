#!/bin/bash

# Database backup script for specified tables
# Creates SQL dump files with data only (no schema)

set -e

# Get the backend root directory (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to backend root to ensure consistent paths
cd "$BACKEND_ROOT"

# Tables to backup - modify this list as needed
TABLES_TO_BACKUP=(
    "post"
    "post_media"
)

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Database connection details
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-postgres}"
DB_PASSWORD="${DB_PASSWORD:-cats}"
DB_NAME="${DB_NAME:-ai_slop_extension}"

# Create backup directory with timestamp (always in backend root)
BACKUP_DIR="$BACKEND_ROOT/db_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "🔄 Starting database backup..."
echo "📂 Backup directory: $BACKUP_DIR"
echo "📋 Tables to backup: ${TABLES_TO_BACKUP[@]}"
echo ""

# Export password for pg_dump
export PGPASSWORD="$DB_PASSWORD"

# Backup each table
for TABLE in "${TABLES_TO_BACKUP[@]}"; do
    echo "📦 Backing up '$TABLE' table..."
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --table="$TABLE" \
        --data-only \
        --column-inserts \
        --no-owner \
        --no-privileges \
        --no-tablespaces \
        --no-unlogged-table-data \
        > "$BACKUP_DIR/${TABLE}.sql"
done

# Create metadata file with dynamic table counts
echo "📝 Creating metadata file..."

# Start metadata JSON
cat > "$BACKUP_DIR/metadata.json" <<EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "database": "$DB_NAME",
  "tables": [$(printf '"%s",' "${TABLES_TO_BACKUP[@]}" | sed 's/,$//')]",
  "table_counts": {
EOF

# Add count for each table
FIRST=true
for TABLE in "${TABLES_TO_BACKUP[@]}"; do
    COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM $TABLE;" 2>/dev/null || echo "0")
    if [ "$FIRST" = true ]; then
        FIRST=false
    else
        echo "," >> "$BACKUP_DIR/metadata.json"
    fi
    echo -n "    \"$TABLE\": $COUNT" >> "$BACKUP_DIR/metadata.json"
done

# Close metadata JSON
cat >> "$BACKUP_DIR/metadata.json" <<EOF

  }
}
EOF

# Create a latest symlink (in backend root)
ln -sfn "$BACKUP_DIR" "$BACKEND_ROOT/db_backups/latest"

echo ""
echo "✅ Backup completed successfully!"
echo "📍 Files created:"
for TABLE in "${TABLES_TO_BACKUP[@]}"; do
    echo "   - $BACKUP_DIR/${TABLE}.sql"
done
echo "   - $BACKUP_DIR/metadata.json"
echo ""
echo "💡 To restore this backup, run:"
echo "   ./scripts/restore-tables.sh $BACKUP_DIR"
echo "   or"
echo "   ./scripts/restore-tables.sh latest"

unset PGPASSWORD