from fastapi import APIRouter
from datetime import date, datetime
import os
from pathlib import Path

# Import database functions from main.py
from api.main import get_db, get_db_cursor, DB_TYPE

# Router without prefix - prefix will be added in main.py include_router call
router = APIRouter(tags=["analytics"])

@router.get("/today")
def today_stats():
    """Get today's statistics from database - PostgreSQL/SQLite compatible"""
    print("=" * 60)
    print("📊 ANALYTICS: Fetching today's stats")
    print("=" * 60)
    
    try:
        today = date.today().isoformat()
        print(f"Today's date: {today}")
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Page views (you increment on each /v1/calculate call)
            pv = 0
            try:
                print("Querying page_views table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM page_views WHERE date = %s", (today,))
                else:
                    # Check if table exists (SQLite)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='page_views'")
                    if not cursor.fetchone():
                        print("page_views table does not exist")
                    else:
                        cursor.execute("SELECT COUNT(*) as count FROM page_views WHERE date = ?", (today,))
                
                result = cursor.fetchone()
                if isinstance(result, dict):
                    pv = result.get('count', 0) or 0
                elif isinstance(result, tuple):
                    pv = result[0] if result else 0
                else:
                    pv = result if result else 0
                print(f"Page views: {pv}")
            except Exception as e:
                print(f"Error counting page views: {e}")
                import traceback
                traceback.print_exc()
            
            # Unique visitors (distinct IP)
            uv = 0
            try:
                print("Querying unique visitors...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(DISTINCT ip) as count FROM page_views WHERE date = %s", (today,))
                else:
                    cursor.execute("SELECT COUNT(DISTINCT ip) as count FROM page_views WHERE date = ?", (today,))
                
                result = cursor.fetchone()
                if isinstance(result, dict):
                    uv = result.get('count', 0) or 0
                elif isinstance(result, tuple):
                    uv = result[0] if result else 0
                else:
                    uv = result if result else 0
                print(f"Unique visitors: {uv}")
            except Exception as e:
                print(f"Error counting unique visitors: {e}")
                import traceback
                traceback.print_exc()
            
            # Calculations today
            calc = 0
            try:
                print("Querying calculations table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = %s", (today,))
                else:
                    # Check if table exists (SQLite)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calculations'")
                    if not cursor.fetchone():
                        print("calculations table does not exist")
                    else:
                        cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = ?", (today,))
                
                result = cursor.fetchone()
                if isinstance(result, dict):
                    calc = result.get('count', 0) or 0
                elif isinstance(result, tuple):
                    calc = result[0] if result else 0
                else:
                    calc = result if result else 0
                print(f"Calculations: {calc}")
            except Exception as e:
                print(f"Error counting calculations: {e}")
                import traceback
                traceback.print_exc()
            
            # Paid today (Stripe webhook inserts row)
            paid = 0
            try:
                print("Querying payments table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) = %s", (today,))
                else:
                    # Check if table exists (SQLite)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
                    if not cursor.fetchone():
                        print("payments table does not exist")
                    else:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) = ?", (today,))
                
                result = cursor.fetchone()
                if isinstance(result, dict):
                    paid = float(result.get('total', 0) or 0)
                elif isinstance(result, tuple):
                    paid = float(result[0] if result and result[0] else 0)
                else:
                    paid = float(result if result else 0)
                print(f"Payments: ${paid}")
            except Exception as e:
                print(f"Error calculating payments: {e}")
                import traceback
                traceback.print_exc()
        
        result = {"pv": pv, "uv": uv, "calc": calc, "paid": paid}
        print(f"✅ Returning result: {result}")
        print("=" * 60)
        return result
        
    except Exception as e:
        print(f"❌ ERROR in today_stats: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {"pv": 0, "uv": 0, "calc": 0, "paid": 0, "error": str(e)}

