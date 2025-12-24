"""
Verification script to check database state after migration

Usage:
    railway run python api/migrations/verify_database.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
project_root = api_dir.parent
sys.path.insert(0, str(project_root))

from api.database import get_db, get_db_cursor, DB_TYPE

def main():
    print("=" * 60)
    print("🔍 DATABASE VERIFICATION")
    print("=" * 60)
    print(f"Database Type: {DB_TYPE}")
    print()
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check customers table
            print("1️⃣ Checking customers table...")
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM customers")
                    count = cursor.fetchone()[0]
                else:
                    cursor.execute("SELECT COUNT(*) FROM customers")
                    count = cursor.fetchone()[0]
                print(f"   ✅ Customers table exists ({count} records)")
            except Exception as e:
                print(f"   ❌ Customers table error: {e}")
            
            # Check api_keys table
            print("\n2️⃣ Checking api_keys table...")
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM api_keys")
                    count = cursor.fetchone()[0]
                else:
                    cursor.execute("SELECT COUNT(*) FROM api_keys")
                    count = cursor.fetchone()[0]
                print(f"   ✅ API keys table exists ({count} records)")
            except Exception as e:
                print(f"   ❌ API keys table error: {e}")
            
            # Check lien_deadlines table
            print("\n3️⃣ Checking lien_deadlines table...")
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    total_count = cursor.fetchone()[0]
                    print(f"   ✅ Total states: {total_count}")
                    
                    # Check Hawaii specifically
                    cursor.execute("""
                        SELECT state_code, state_name, lien_filing_days, preliminary_notice_required
                        FROM lien_deadlines 
                        WHERE state_code = 'HI'
                    """)
                    hawaii = cursor.fetchone()
                    if hawaii:
                        print(f"   ✅ Hawaii verified:")
                        print(f"      State: {hawaii['state_name']}")
                        print(f"      Lien deadline: {hawaii['lien_filing_days']} days")
                        print(f"      Prelim required: {hawaii['preliminary_notice_required']}")
                    else:
                        print("   ❌ Hawaii not found!")
                    
                    # Check a few other states
                    cursor.execute("""
                        SELECT state_code, state_name, lien_filing_days
                        FROM lien_deadlines 
                        WHERE state_code IN ('AK', 'TX', 'CA', 'NY')
                        ORDER BY state_code
                    """)
                    test_states = cursor.fetchall()
                    print(f"\n   📊 Sample states:")
                    for state in test_states:
                        print(f"      {state['state_code']}: {state['state_name']} - {state['lien_filing_days']} days")
                    
                else:
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    total_count = cursor.fetchone()[0]
                    print(f"   ✅ Total states: {total_count}")
                    
                    # Check Hawaii specifically
                    cursor.execute("""
                        SELECT state_code, state_name, lien_filing_days, preliminary_notice_required
                        FROM lien_deadlines 
                        WHERE state_code = 'HI'
                    """)
                    hawaii = cursor.fetchone()
                    if hawaii:
                        print(f"   ✅ Hawaii verified:")
                        print(f"      State: {hawaii[1]}")
                        print(f"      Lien deadline: {hawaii[2]} days")
                        print(f"      Prelim required: {bool(hawaii[3])}")
                    else:
                        print("   ❌ Hawaii not found!")
                    
                    # Check a few other states
                    cursor.execute("""
                        SELECT state_code, state_name, lien_filing_days
                        FROM lien_deadlines 
                        WHERE state_code IN ('AK', 'TX', 'CA', 'NY')
                        ORDER BY state_code
                    """)
                    test_states = cursor.fetchall()
                    print(f"\n   📊 Sample states:")
                    for state in test_states:
                        print(f"      {state[0]}: {state[1]} - {state[2]} days")
                
                if total_count == 51:
                    print(f"\n   🎉 Perfect! All 51 jurisdictions are present!")
                elif total_count > 51:
                    print(f"\n   ⚠️ Warning: More than 51 states found ({total_count})")
                else:
                    print(f"\n   ❌ Error: Only {total_count} states found (expected 51)")
                    
            except Exception as e:
                print(f"   ❌ lien_deadlines table error: {e}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("✅ VERIFICATION COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

