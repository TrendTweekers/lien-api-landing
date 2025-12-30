import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def check_schema():
    """
    Connects to PostgreSQL and lists all tables and columns.
    """
    db_url = os.getenv('DATABASE_URL')
    
    print("=" * 60)
    print("🔍 PRODUCTION SCHEMA INSPECTOR")
    print("=" * 60)

    if not db_url:
        print("❌ DATABASE_URL environment variable is not set.")
        print("This script is intended to run against the production PostgreSQL database.")
        print("Please set DATABASE_URL and try again.")
        return

    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 is not installed.")
        print("Please install it using: pip install psycopg2-binary")
        return

    try:
        print(f"🔌 Connecting to database...")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Get all tables in public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        if not tables:
            print("⚠️ No tables found in public schema.")
            return

        print(f"✅ Found {len(tables)} tables.")
        
        for table in tables:
            table_name = table[0]
            print(f"\n📋 TABLE: {table_name}")
            print("-" * 80)
            
            # Get columns for this table
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = %s AND table_schema = 'public'
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cursor.fetchall()
            
            # Print header
            print(f"{'Column Name':<30} | {'Type':<15} | {'Null':<5} | {'Default'}")
            print("-" * 80)
            
            for col in columns:
                col_name, col_type, nullable, default = col
                default_val = str(default) if default else 'NULL'
                
                # Truncate long default values
                if len(default_val) > 25:
                    default_val = default_val[:22] + "..."
                
                print(f"{col_name:<30} | {col_type:<15} | {nullable:<5} | {default_val}")
                
        print("\n" + "=" * 60)
        print("✅ Schema check complete.")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_schema()
