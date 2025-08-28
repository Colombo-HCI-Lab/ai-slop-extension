#!/bin/bash

# Database restore/seed script for backed up tables
# Replaces existing data with backup/seed data

set -e

# Get the backend root directory (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Change to backend root to ensure consistent paths
cd "$BACKEND_ROOT"

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

# Check if backup directory is provided
if [ -z "$1" ]; then
    echo "❌ Error: Please provide a backup directory or 'latest'"
    echo "Usage: $0 <backup_directory|latest>"
    echo ""
    echo "Examples:"
    echo "  $0 db_backups/20240101_120000"
    echo "  $0 latest"
    echo "  $0 seeds/initial"
    exit 1
fi

BACKUP_DIR="$1"

# Handle 'latest' argument
if [ "$BACKUP_DIR" = "latest" ]; then
    if [ -L "$BACKEND_ROOT/db_backups/latest" ]; then
        BACKUP_DIR="$BACKEND_ROOT/db_backups/latest"
    else
        echo "❌ Error: No 'latest' backup found"
        exit 1
    fi
fi

# Convert to absolute path if relative
if [[ ! "$BACKUP_DIR" = /* ]]; then
    BACKUP_DIR="$BACKEND_ROOT/$BACKUP_DIR"
fi

# Check if backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ Error: Backup directory '$BACKUP_DIR' not found"
    exit 1
fi

# Read metadata to get list of tables
if [ -f "$BACKUP_DIR/metadata.json" ]; then
    # Extract tables array from metadata.json using python
    TABLES=$(python3 -c "import json; data=json.load(open('$BACKUP_DIR/metadata.json')); print(' '.join(data['tables']))" 2>/dev/null || echo "")
    if [ -z "$TABLES" ]; then
        # Fallback: look for .sql files
        TABLES=$(cd "$BACKUP_DIR" && ls -1 *.sql 2>/dev/null | grep -v combined | sed 's/.sql$//' | tr '\n' ' ')
    fi
else
    # No metadata, look for .sql files
    TABLES=$(cd "$BACKUP_DIR" && ls -1 *.sql 2>/dev/null | grep -v combined | sed 's/.sql$//' | tr '\n' ' ')
fi

if [ -z "$TABLES" ]; then
    echo "❌ Error: No backup files found in '$BACKUP_DIR'"
    exit 1
fi

echo "🔄 Starting database restore..."
echo "📂 Backup directory: $BACKUP_DIR"
echo "📋 Tables to restore: $TABLES"

# Export password for psql
export PGPASSWORD="$DB_PASSWORD"

# Show current data counts
echo ""
echo "📊 Current database state:"
declare -A CURRENT_COUNTS
for TABLE in $TABLES; do
    COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM $TABLE;" 2>/dev/null || echo "0")
    CURRENT_COUNTS[$TABLE]=$COUNT
    echo "   $TABLE: $COUNT"
done

# Ask for confirmation
echo ""
echo "⚠️  WARNING: This will DELETE all existing data in the following tables:"
echo "   $TABLES"
read -p "Are you sure you want to continue? (yes/no): " -n 3 -r
echo
if [[ ! $REPLY =~ ^[Yy]es$ ]]; then
    echo "❌ Restore cancelled"
    exit 1
fi

# Create transaction script
TRANSACTION_FILE="/tmp/restore_transaction_$$.sql"
cat > "$TRANSACTION_FILE" <<EOF
BEGIN;

-- Disable foreign key checks temporarily
SET session_replication_role = 'replica';

EOF

# Delete existing data in reverse order to handle dependencies
# Convert TABLES string to array and reverse it
TABLES_ARRAY=($TABLES)
for ((i=${#TABLES_ARRAY[@]}-1; i>=0; i--)); do
    TABLE="${TABLES_ARRAY[$i]}"
    echo "DELETE FROM $TABLE;" >> "$TRANSACTION_FILE"
done

# Re-enable foreign key checks
echo "SET session_replication_role = 'origin';" >> "$TRANSACTION_FILE"
echo "" >> "$TRANSACTION_FILE"

# Add data from backup files in forward order
echo "📦 Restoring data from backup files..."
for TABLE in $TABLES; do
    if [ -f "$BACKUP_DIR/${TABLE}.sql" ]; then
        echo "   - Adding data from ${TABLE}.sql"
        cat "$BACKUP_DIR/${TABLE}.sql" >> "$TRANSACTION_FILE"
    else
        echo "   ⚠️  Warning: No backup file found for table '$TABLE'"
    fi
done

# Complete transaction
echo "COMMIT;" >> "$TRANSACTION_FILE"

# Execute restore
echo ""
echo "🗄️ Executing restore..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$TRANSACTION_FILE" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Restore completed successfully!"
    
    # Show new data counts
    echo ""
    echo "📊 New database state:"
    for TABLE in $TABLES; do
        NEW_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM $TABLE;" 2>/dev/null || echo "0")
        OLD_COUNT=${CURRENT_COUNTS[$TABLE]}
        echo "   $TABLE: $NEW_COUNT (was $OLD_COUNT)"
    done
    
    # Show metadata if available
    if [ -f "$BACKUP_DIR/metadata.json" ]; then
        echo ""
        echo "📝 Backup metadata:"
        cat "$BACKUP_DIR/metadata.json" | python3 -m json.tool 2>/dev/null || cat "$BACKUP_DIR/metadata.json"
    fi
else
    echo "❌ Error: Restore failed!"
    echo "Database has been rolled back to its original state."
    exit 1
fi

# Cleanup
rm -f "$TRANSACTION_FILE"
unset PGPASSWORD

echo ""
echo "💡 Tips:"
echo "   - To create a new backup: ./scripts/backup-tables.sh"
echo "   - To view all backups: ls -la db_backups/"