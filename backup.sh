#!/bin/bash
# Database backup script for LienDeadline
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups"

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR

# Backup main database
cp liendeadline.db "$BACKUP_DIR/liendeadline_$DATE.db"

# Backup admin database (if exists)
if [ -f "admin.db" ]; then
    cp admin.db "$BACKUP_DIR/admin_$DATE.db"
fi

# Keep only last 30 days of backups
find $BACKUP_DIR -name "*.db" -mtime +30 -delete

echo "✅ Backup completed: $DATE"
echo "   - liendeadline_$DATE.db"
if [ -f "admin.db" ]; then
    echo "   - admin_$DATE.db"
fi

