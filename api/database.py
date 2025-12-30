"""
Database connection module - PostgreSQL/SQLite compatible
This module breaks circular import dependencies by providing database functions
that can be imported by both api/main.py and api/analytics.py
"""
import os
from pathlib import Path
from contextlib import contextmanager
import logging

# Configure logger
logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database connection - PostgreSQL on Railway, SQLite locally
DATABASE_URL = os.getenv('DATABASE_URL')

# Check if DATABASE_URL is a PostgreSQL connection string
# PostgreSQL URLs start with postgres:// or postgresql://
# SQLite URLs start with sqlite://
if DATABASE_URL and (DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')):
    # PostgreSQL (Railway production)
    import psycopg2
    from psycopg2.extras import RealDictCursor
    
    @contextmanager
    def get_db():
        """Get PostgreSQL database connection"""
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(autocommit=False)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_db_cursor(conn):
        """Get PostgreSQL cursor with dict-like row access"""
        return conn.cursor(cursor_factory=RealDictCursor)
    
    DB_TYPE = 'postgresql'
else:
    # SQLite (local development or if DATABASE_URL is SQLite)
    import sqlite3
    
    @contextmanager
    def get_db():
        """Get SQLite database connection"""
        # If DATABASE_URL is set but is SQLite, use it
        # Otherwise use DATABASE_PATH or default
        if DATABASE_URL and DATABASE_URL.startswith('sqlite://'):
            # Extract path from sqlite:///path/to/db.db
            db_path = DATABASE_URL.replace('sqlite:///', '')
        else:
            db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
        
        # Log DB path for debugging (only once per connection to avoid spam, but here we create new connection every time)
        # Using print for visibility in console if logging not configured
        try:
            abs_path = os.path.abspath(db_path)
            print(f"Connecting to SQLite DB: {abs_path}")
            logger.info(f"Connecting to SQLite DB: {abs_path}")
        except:
            pass
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def get_db_cursor(conn):
        """Get SQLite cursor"""
        return conn.cursor()
    
    DB_TYPE = 'sqlite'

# Helper function to execute queries with proper placeholders
def execute_query(conn, query, params=None):
    """Execute query with proper placeholders for PostgreSQL or SQLite"""
    cursor = get_db_cursor(conn)
    if DB_TYPE == 'postgresql':
        # PostgreSQL uses %s placeholders
        if params:
            cursor.execute(query.replace('?', '%s'), params)
        else:
            cursor.execute(query.replace('?', '%s'))
    else:
        # SQLite uses ? placeholders
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
    return cursor

# Log database configuration at startup
print("=" * 60)
print("🔍 DATABASE CONFIGURATION CHECK")
print("=" * 60)
print(f"DATABASE_URL present: {bool(DATABASE_URL)}")

if DATABASE_URL:
    if DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://'):
        print("✅ Database Type: PostgreSQL (Production)")
        print(f"   Connection: {DATABASE_URL[:30]}...")
    elif DATABASE_URL.startswith('sqlite://'):
        print("⚠️  Database Type: SQLite (from DATABASE_URL)")
    else:
        print(f"❓ Database Type: Unknown ({DATABASE_URL[:20]}...)")
else:
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    print("💾 Database Type: SQLite (local development)")
    print(f"   Path: {db_path}")

print(f"📊 DB_TYPE variable set to: {DB_TYPE}")
print("=" * 60)

