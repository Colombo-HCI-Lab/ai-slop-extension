#!/bin/bash

# Schema reset script for completely updating the database schema from scratch
# WARNING: This will delete all data in the database

set -e

echo "⚠️  WARNING: This will completely reset the database and delete all data!"
read -p "Are you sure you want to continue? (y/N): " confirm

if [[ $confirm != [yY] && $confirm != [yY][eE][sS] ]]; then
    echo "❌ Operation cancelled"
    exit 0
fi

echo "🔥 Resetting database schema..."

# Reset the database (this will delete all data and recreate from schema)
echo "🗑️  Resetting database..."
npx prisma migrate reset --force

# Generate Prisma client
echo "📦 Generating Prisma client..."
npx prisma generate

echo "✅ Database schema reset completed successfully!"
echo "🚀 Database is now ready with a fresh schema"
