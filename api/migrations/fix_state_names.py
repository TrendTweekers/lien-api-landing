"""
Fix state names in lien_deadlines table if they're stored as codes instead of full names
Run with: railway run python api/migrations/fix_state_names.py
"""
import sys
from pathlib import Path

# Add parent directory to path
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
project_root = api_dir.parent
sys.path.insert(0, str(project_root))

from api.database import get_db, get_db_cursor, DB_TYPE

# State code to full name mapping
STATE_CODE_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'DC': 'District of Columbia', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii',
    'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine',
    'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska',
    'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
    'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island',
    'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas',
    'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

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

def fix_state_names():
    """Fix state names in database - returns dict with results"""
    result = {
        "updates_count": 0,
        "updated_states": [],
        "oklahoma_status": None,
        "errors": []
    }
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            for code, expected_name in STATE_CODE_TO_NAME.items():
                try:
                    # Check current state_name value
                    if DB_TYPE == 'postgresql':
                        cursor.execute(
                            "SELECT state_code, state_name FROM lien_deadlines WHERE state_code = %s",
                            (code,)
                        )
                    else:
                        cursor.execute(
                            "SELECT state_code, state_name FROM lien_deadlines WHERE state_code = ?",
                            (code,)
                        )
                    
                    row = cursor.fetchone()
                    
                    if row:
                        if isinstance(row, dict):
                            current_name = row.get('state_name')
                        elif isinstance(row, (tuple, list)):
                            current_name = row[1] if len(row) > 1 else None
                        else:
                            current_name = safe_fetch_value(row, 1)
                        
                        # Check if state_name needs fixing
                        needs_fix = (
                            current_name is None or
                            current_name == '' or
                            current_name == code or
                            current_name.upper() == code or
                            current_name != expected_name
                        )
                        
                        if needs_fix:
                            # Update to correct name
                            if DB_TYPE == 'postgresql':
                                cursor.execute("""
                                    UPDATE lien_deadlines 
                                    SET state_name = %s 
                                    WHERE state_code = %s
                                """, (expected_name, code))
                            else:
                                cursor.execute("""
                                    UPDATE lien_deadlines 
                                    SET state_name = ? 
                                    WHERE state_code = ?
                                """, (expected_name, code))
                            
                            if cursor.rowcount > 0:
                                result["updates_count"] += 1
                                result["updated_states"].append({
                                    "code": code,
                                    "old_name": current_name or "NULL",
                                    "new_name": expected_name
                                })
                except Exception as e:
                    result["errors"].append(f"Error updating {code}: {str(e)}")
            
            conn.commit()
            
            # Verify Oklahoma specifically
            if DB_TYPE == 'postgresql':
                cursor.execute(
                    "SELECT state_code, state_name FROM lien_deadlines WHERE state_code = 'OK'"
                )
            else:
                cursor.execute(
                    "SELECT state_code, state_name FROM lien_deadlines WHERE state_code = 'OK'"
                )
            ok_row = cursor.fetchone()
            
            if ok_row:
                if isinstance(ok_row, dict):
                    ok_name = ok_row.get('state_name')
                elif isinstance(ok_row, (tuple, list)):
                    ok_name = ok_row[1] if len(ok_row) > 1 else None
                else:
                    ok_name = safe_fetch_value(ok_row, 1)
                
                result["oklahoma_status"] = {
                    "state_code": "OK",
                    "state_name": ok_name,
                    "is_correct": ok_name == 'Oklahoma'
                }
        
        return result
        
    except Exception as e:
        result["errors"].append(f"Fatal error: {str(e)}")
        import traceback
        result["traceback"] = traceback.format_exc()
        return result

def main():
    """Main function for command-line execution"""
    print("=" * 60)
    print("🔧 FIXING STATE NAMES IN DATABASE")
    print("=" * 60)
    print(f"Database Type: {DB_TYPE}\n")
    
    result = fix_state_names()
    
    if result["updated_states"]:
        print("Checking and fixing state names...\n")
        for update in result["updated_states"]:
            print(f"✅ Updated {update['code']}: '{update['old_name']}' → '{update['new_name']}'")
    
    print(f"\n{'=' * 60}")
    print(f"✅ Fixed {result['updates_count']} state names")
    print(f"{'=' * 60}\n")
    
    if result["oklahoma_status"]:
        ok_status = result["oklahoma_status"]
        print(f"✅ Oklahoma verification: state_code='{ok_status['state_code']}', state_name='{ok_status['state_name']}'")
        if ok_status['is_correct']:
            print("   ✅ Oklahoma name is correct!")
        else:
            print(f"   ⚠️ Oklahoma name is still '{ok_status['state_name']}', expected 'Oklahoma'")
    else:
        print("❌ Oklahoma not found in database!")
    
    if result["errors"]:
        print("\n⚠️ Errors encountered:")
        for error in result["errors"]:
            print(f"   {error}")
    
    if result.get("traceback"):
        print("\n❌ Traceback:")
        print(result["traceback"])
        sys.exit(1)

if __name__ == "__main__":
    main()

