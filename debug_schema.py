import sqlite3
import os

def check_tables():
    db_path = "liendeadline.db"
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables found:")
    for t in tables:
        print(f"- {t[0]}")
    
    for table in tables:
        table_name = table[0]
        if table_name in ['users', 'customers']:
            print(f"\n--- Schema for {table_name} ---")
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            for col in columns:
                print(col)
                
    conn.close()

if __name__ == "__main__":
    check_tables()
