import psycopg2
import os

def run_migration():
    DATABASE_URL = os.getenv('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='calculations' AND column_name='project_type'
        """)
        
        if not cursor.fetchone():
            print("Adding project_type column...")
            cursor.execute("""
                ALTER TABLE calculations 
                ADD COLUMN project_type VARCHAR(50) DEFAULT 'commercial'
            """)
            conn.commit()
            print("✅ project_type column added")
        else:
            print("✅ project_type column already exists")
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    run_migration()

