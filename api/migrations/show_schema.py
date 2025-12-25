"""
Script to show lien_deadlines table structure and sample data
Run with: railway run python api/migrations/show_schema.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
project_root = api_dir.parent
sys.path.insert(0, str(project_root))

from api.database import get_db, get_db_cursor, DB_TYPE

def main():
    print("=" * 60)
    print("📊 LIEN_DEADLINES TABLE SCHEMA")
    print("=" * 60)
    print(f"Database Type: {DB_TYPE}\n")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                # Get column names and types
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'lien_deadlines'
                    ORDER BY ordinal_position
                """)
                
                print("=== COLUMN STRUCTURE ===")
                columns = []
                for row in cursor.fetchall():
                    col_name = row[0]
                    col_type = row[1]
                    nullable = row[2]
                    columns.append(col_name)
                    nullable_str = "NULL" if nullable == 'YES' else "NOT NULL"
                    print(f"{col_name:40} {col_type:20} {nullable_str}")
                
                # Get a sample row (Alaska)
                print("\n=== SAMPLE ROW (Alaska - AK) ===")
                cursor.execute("SELECT * FROM lien_deadlines WHERE state_code = 'AK' LIMIT 1")
                row = cursor.fetchone()
                
                if row:
                    if isinstance(row, dict):
                        # Dict-like result
                        for col in columns:
                            val = row.get(col)
                            if val is None:
                                val_str = "NULL"
                            elif isinstance(val, bool):
                                val_str = str(val)
                            elif isinstance(val, (int, float)):
                                val_str = str(val)
                            else:
                                val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                            print(f"{col:40} = {val_str}")
                    else:
                        # Tuple/list result
                        for i, col in enumerate(columns):
                            if i < len(row):
                                val = row[i]
                                if val is None:
                                    val_str = "NULL"
                                elif isinstance(val, bool):
                                    val_str = str(val)
                                elif isinstance(val, (int, float)):
                                    val_str = str(val)
                                else:
                                    val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                                print(f"{col:40} = {val_str}")
                            else:
                                print(f"{col:40} = <missing>")
                else:
                    print("❌ Alaska (AK) not found in database!")
                    
                    # Try to get any state
                    cursor.execute("SELECT state_code, state_name FROM lien_deadlines LIMIT 1")
                    any_row = cursor.fetchone()
                    if any_row:
                        if isinstance(any_row, dict):
                            print(f"\n✅ Found sample state: {any_row.get('state_code')} - {any_row.get('state_name')}")
                        else:
                            print(f"\n✅ Found sample state: {any_row[0]} - {any_row[1]}")
                
            else:
                # SQLite
                cursor.execute("PRAGMA table_info(lien_deadlines)")
                columns_info = cursor.fetchall()
                
                print("=== COLUMN STRUCTURE ===")
                columns = []
                for row in columns_info:
                    # SQLite PRAGMA returns: (cid, name, type, notnull, dflt_value, pk)
                    col_name = row[1]
                    col_type = row[2]
                    not_null = "NOT NULL" if row[3] else "NULL"
                    columns.append(col_name)
                    print(f"{col_name:40} {col_type:20} {not_null}")
                
                # Get a sample row (Alaska)
                print("\n=== SAMPLE ROW (Alaska - AK) ===")
                cursor.execute("SELECT * FROM lien_deadlines WHERE state_code = 'AK' LIMIT 1")
                row = cursor.fetchone()
                
                if row:
                    for i, col in enumerate(columns):
                        if i < len(row):
                            val = row[i]
                            if val is None:
                                val_str = "NULL"
                            elif isinstance(val, (int, float)):
                                val_str = str(val)
                            else:
                                val_str = str(val)[:50] + "..." if len(str(val)) > 50 else str(val)
                            print(f"{col:40} = {val_str}")
                        else:
                            print(f"{col:40} = <missing>")
                else:
                    print("❌ Alaska (AK) not found in database!")
                    
                    # Try to get any state
                    cursor.execute("SELECT state_code, state_name FROM lien_deadlines LIMIT 1")
                    any_row = cursor.fetchone()
                    if any_row:
                        print(f"\n✅ Found sample state: {any_row[0]} - {any_row[1]}")
            
            # Get total count
            cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
            result = cursor.fetchone()
            if isinstance(result, dict):
                count = list(result.values())[0] if result else 0
            elif isinstance(result, (tuple, list)):
                count = result[0] if len(result) > 0 else 0
            else:
                count = result if result else 0
            
            print(f"\n=== SUMMARY ===")
            print(f"Total states in database: {count}")
            print(f"Expected: 51 states (50 US states + DC)")
            
            if count >= 51:
                print("✅ All states present!")
            else:
                print(f"⚠️ Missing {51 - count} states")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

