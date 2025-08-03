#!/bin/bash

# Migration script for running database migrations
# This script runs Prisma migrations to update the database schema

set -e

echo "🚀 Running database migrations..."

# Generate Prisma client
echo "📦 Generating Prisma client..."
npx prisma generate

# Run migrations
echo "🔄 Running migrations..."
npx prisma migrate dev

echo "✅ Migrations completed successfully!"
