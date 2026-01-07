"""
Migration: Drop QuickBooks integration tables
Removes quickbooks_tokens and quickbooks_oauth_states tables

Run manually via: python api/migrations/cleanup_unused_integrations.py
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import database module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.database import get_db, DB_TYPE

def run_cleanup():
    """Drop QuickBooks tables (idempotent - safe to run multiple times)"""
    
    tables_to_drop = [
        'quickbooks_tokens',
        'quickbooks_oauth_states'
    ]
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            print("🔄 Starting QuickBooks tables cleanup...")
            print(f"   Database type: {DB_TYPE}")
            
            for table_name in tables_to_drop:
                try:
                    # Check if table exists first
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = %s
                            )
                        """, (table_name,))
                        table_exists = cursor.fetchone()[0]
                    else:
                        cursor.execute("""
                            SELECT name FROM sqlite_master 
                            WHERE type='table' AND name=?
                        """, (table_name,))
                        table_exists = cursor.fetchone() is not None
                    
                    if table_exists:
                        # Drop table with CASCADE to handle foreign keys
                        print(f"   Dropping table: {table_name}...")
                        cursor.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                        print(f"   ✅ Dropped {table_name}")
                    else:
                        print(f"   ⏭️  Table {table_name} does not exist (skipping)")
                        
                except Exception as e:
                    print(f"   ⚠️  Error dropping {table_name}: {e}")
                    # Continue with other tables even if one fails
            
            conn.commit()
            print("✅ Cleanup completed successfully")
            return True
            
    except Exception as e:
        print(f"❌ Cleanup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧹 QuickBooks Integration Cleanup")
    print("=" * 60)
    print("This will drop the following tables:")
    print("  - quickbooks_tokens")
    print("  - quickbooks_oauth_states")
    print("")
    print("⚠️  Make sure you have a database backup before proceeding!")
    print("=" * 60)
    print("")
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response != 'yes':
        print("❌ Cleanup cancelled")
        sys.exit(0)
    
    success = run_cleanup()
    sys.exit(0 if success else 1)

