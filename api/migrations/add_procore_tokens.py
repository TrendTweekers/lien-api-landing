"""
Migration: Create procore_tokens table
Run manually via: GET /api/admin/run-procore-migration
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def run_migration():
    """Create procore_tokens table for OAuth tokens"""
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise Exception("DATABASE_URL not found")
    
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        print("🔄 Creating procore_tokens table...")
        
        # Create procore_tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procore_tokens (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) UNIQUE NOT NULL,
                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        conn.commit()
        print("✅ procore_tokens table created successfully")
        
        # Verify table exists
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'procore_tokens'
        """)
        columns = cursor.fetchall()
        print(f"✅ Verified procore_tokens table with {len(columns)} columns")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {str(e)}")
        raise
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    run_migration()

