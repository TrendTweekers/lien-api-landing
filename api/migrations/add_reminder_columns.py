"""
Migration script to add reminder_1day and reminder_7days columns to calculations table
Run this once to add the reminder columns that were temporarily removed from queries.

Usage:
    # Via Railway CLI:
    railway run python api/migrations/add_reminder_columns.py
    
    # Or locally:
    python api/migrations/add_reminder_columns.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def add_reminder_columns():
    """Add reminder_1day and reminder_7days columns to calculations table"""
    print("=" * 80)
    print("🔄 ADDING REMINDER COLUMNS TO CALCULATIONS TABLE")
    print("=" * 80)
    
    try:
        # Try PostgreSQL first (Railway production)
        DATABASE_URL = os.getenv('DATABASE_URL')
        if DATABASE_URL and (DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')):
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            print("Connecting to PostgreSQL database...")
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            print("Adding reminder_1day column...")
            try:
                cursor.execute("""
                    ALTER TABLE calculations 
                    ADD COLUMN IF NOT EXISTS reminder_1day BOOLEAN DEFAULT FALSE;
                """)
                print("  ✅ reminder_1day column added")
            except Exception as e:
                print(f"  ⚠️ Error adding reminder_1day: {e}")
                # Check if column already exists
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'calculations' AND column_name = 'reminder_1day';
                """)
                if cursor.fetchone():
                    print("  ℹ️ Column reminder_1day already exists, skipping")
                else:
                    raise
            
            print("Adding reminder_7days column...")
            try:
                cursor.execute("""
                    ALTER TABLE calculations 
                    ADD COLUMN IF NOT EXISTS reminder_7days BOOLEAN DEFAULT FALSE;
                """)
                print("  ✅ reminder_7days column added")
            except Exception as e:
                print(f"  ⚠️ Error adding reminder_7days: {e}")
                # Check if column already exists
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'calculations' AND column_name = 'reminder_7days';
                """)
                if cursor.fetchone():
                    print("  ℹ️ Column reminder_7days already exists, skipping")
                else:
                    raise
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("✅ Reminder columns added successfully (PostgreSQL)")
            return True
            
        else:
            # SQLite fallback (local development)
            import sqlite3
            from api.database import BASE_DIR
            
            print("Connecting to SQLite database...")
            db_path = BASE_DIR / "lien_deadline.db"
            if not db_path.exists():
                db_path = BASE_DIR / "liendeadline.db"
            
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            print("Adding reminder_1day column...")
            try:
                cursor.execute("""
                    ALTER TABLE calculations 
                    ADD COLUMN reminder_1day INTEGER DEFAULT 0;
                """)
                print("  ✅ reminder_1day column added")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print("  ℹ️ Column reminder_1day already exists, skipping")
                else:
                    raise
            
            print("Adding reminder_7days column...")
            try:
                cursor.execute("""
                    ALTER TABLE calculations 
                    ADD COLUMN reminder_7days INTEGER DEFAULT 0;
                """)
                print("  ✅ reminder_7days column added")
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print("  ℹ️ Column reminder_7days already exists, skipping")
                else:
                    raise
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("✅ Reminder columns added successfully (SQLite)")
            return True
            
    except Exception as e:
        print(f"❌ Error adding reminder columns: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = add_reminder_columns()
    sys.exit(0 if success else 1)

