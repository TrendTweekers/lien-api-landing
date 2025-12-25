"""
Quick script to check how many states are in the lien_deadlines table
"""
import sys
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
project_root = api_dir.parent
sys.path.insert(0, str(project_root))

from api.database import get_db, get_db_cursor, DB_TYPE

def safe_fetch_value(cursor_result, index=0):
    """Safely extract value from cursor result"""
    if cursor_result is None:
        return None
    if isinstance(cursor_result, dict):
        keys = list(cursor_result.keys())
        if keys:
            return cursor_result[keys[index]]
        return None
    elif isinstance(cursor_result, (tuple, list)):
        return cursor_result[index] if len(cursor_result) > index else None
    else:
        try:
            return cursor_result[index]
        except (KeyError, TypeError):
            return cursor_result

def main():
    print("=" * 60)
    print("🔍 CHECKING DATABASE STATE COUNT")
    print("=" * 60)
    print(f"Database Type: {DB_TYPE}\n")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if table exists
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'lien_deadlines'
                    )
                """)
                result = cursor.fetchone()
                table_exists = safe_fetch_value(result, 0) if result else False
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lien_deadlines'")
                table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                print("❌ lien_deadlines table does NOT exist!")
                print("   Run: python api/migrations/fix_production_database.py")
                return
            
            # Count states
            cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
            result = cursor.fetchone()
            count = safe_fetch_value(result, 0) if result else 0
            
            print(f"📊 States in database: {count}")
            
            if count < 51:
                print(f"\n⚠️ WARNING: Only {count} states found, expected 51!")
                print("   Missing states need to be added.")
                print("\n   To fix, run:")
                print("   railway run python api/migrations/fix_production_database.py")
            elif count == 51:
                print("✅ All 51 states present!")
            else:
                print(f"⚠️ Unexpected: {count} states found (expected 51)")
            
            # List all state codes
            print("\n📋 State codes in database:")
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT state_code, state_name FROM lien_deadlines ORDER BY state_code")
            else:
                cursor.execute("SELECT state_code, state_name FROM lien_deadlines ORDER BY state_code")
            
            states = cursor.fetchall()
            state_codes = []
            for row in states:
                try:
                    if isinstance(row, dict):
                        code = row.get('state_code')
                        name = row.get('state_name')
                    elif isinstance(row, (tuple, list)):
                        code = row[0] if len(row) > 0 else None
                        name = row[1] if len(row) > 1 else None
                    else:
                        # Try to access by index
                        code = safe_fetch_value(row, 0)
                        name = safe_fetch_value(row, 1)
                    
                    if code:
                        state_codes.append(str(code).upper())
                        print(f"   {code}: {name}")
                except Exception as e:
                    print(f"   ⚠️ Error parsing row: {row} - {e}")
                    continue
            
            # Check for missing states
            expected_states = [
                'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'DC', 'FL',
                'GA', 'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'ME',
                'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH',
                'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI',
                'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
            ]
            
            missing_states = [s for s in expected_states if s not in state_codes]
            
            if missing_states:
                print(f"\n❌ Missing states ({len(missing_states)}): {', '.join(missing_states)}")
            else:
                print("\n✅ All 51 states present!")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

