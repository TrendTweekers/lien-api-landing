#!/usr/bin/env python3
"""
Query lien_deadlines table to check state data
"""
import sys
import os
from pathlib import Path

# Add parent directory to path to import api modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import get_db, get_db_cursor, DB_TYPE

def query_states():
    """Query all states from lien_deadlines table"""
    query = """
    SELECT state_code, state_name, preliminary_notice_required, preliminary_notice_days, lien_filing_days
    FROM lien_deadlines
    ORDER BY state_code;
    """
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute(query)
            else:
                # SQLite - adjust query if needed
                cursor.execute(query)
            
            results = cursor.fetchall()
            
            # Print header
            print("=" * 120)
            print(f"{'State':<6} {'State Name':<25} {'Prelim Required':<18} {'Prelim Days':<12} {'Lien Days':<12}")
            print("=" * 120)
            
            # Print results
            for row in results:
                if isinstance(row, dict):
                    state_code = row.get('state_code', '')
                    state_name = row.get('state_name', '')
                    prelim_required = row.get('preliminary_notice_required', '')
                    prelim_days = row.get('preliminary_notice_days', '')
                    lien_days = row.get('lien_filing_days', '')
                else:
                    # Tuple/list result
                    state_code = row[0] if len(row) > 0 else ''
                    state_name = row[1] if len(row) > 1 else ''
                    prelim_required = row[2] if len(row) > 2 else ''
                    prelim_days = row[3] if len(row) > 3 else ''
                    lien_days = row[4] if len(row) > 4 else ''
                
                # Format values
                prelim_required_str = str(prelim_required) if prelim_required is not None else 'NULL'
                prelim_days_str = str(prelim_days) if prelim_days is not None else 'NULL'
                lien_days_str = str(lien_days) if lien_days is not None else 'NULL'
                
                print(f"{state_code:<6} {state_name:<25} {prelim_required_str:<18} {prelim_days_str:<12} {lien_days_str:<12}")
            
            print("=" * 120)
            print(f"\nTotal states: {len(results)}")
            
            return results
            
    except Exception as e:
        print(f"❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔍 Querying lien_deadlines table...")
    print(f"Database type: {DB_TYPE}\n")
    query_states()

