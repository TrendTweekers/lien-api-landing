#!/bin/bash
# PostgreSQL backup script for Railway Postgres
# Usage: ./backup_postgres.sh [DATABASE_URL]
# If DATABASE_URL is not provided, it will use the environment variable

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups"
BACKUP_FILE="$BACKUP_DIR/pre_cleanup_${DATE}.sql"

# Use provided DATABASE_URL or environment variable
if [ -n "$1" ]; then
    DATABASE_URL="$1"
elif [ -z "$DATABASE_URL" ]; then
    echo "❌ Error: DATABASE_URL not provided and not set in environment"
    echo "Usage: ./backup_postgres.sh [DATABASE_URL]"
    echo "   or: DATABASE_URL='your-url' ./backup_postgres.sh"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

echo "🔄 Starting PostgreSQL backup..."
echo "   Database: $(echo $DATABASE_URL | sed 's/:[^:]*@/:***@/')" # Hide password in output

# Perform pg_dump
if pg_dump "$DATABASE_URL" > "$BACKUP_FILE" 2>&1; then
    # Check if backup file was created and has content
    if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
        FILE_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        echo "✅ Backup completed successfully!"
        echo "   File: $BACKUP_FILE"
        echo "   Size: $FILE_SIZE"
        echo ""
        echo "💡 To restore this backup:"
        echo "   psql \"\$DATABASE_URL\" < $BACKUP_FILE"
    else
        echo "❌ Error: Backup file was not created or is empty"
        exit 1
    fi
else
    echo "❌ Error: pg_dump failed"
    echo "   Make sure pg_dump is installed and DATABASE_URL is correct"
    echo "   On Windows: Install PostgreSQL client tools"
    echo "   On Mac: brew install postgresql"
    echo "   On Linux: sudo apt-get install postgresql-client"
    exit 1
fi

