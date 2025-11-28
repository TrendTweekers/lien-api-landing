from fastapi import APIRouter
from datetime import date, datetime
import sqlite3
import os
from pathlib import Path

# Router without prefix - prefix will be added in main.py include_router call
router = APIRouter(tags=["analytics"])

def get_db_path():
    """Get database path (works in Railway and local)"""
    BASE_DIR = Path(__file__).parent.parent
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    return str(db_path)

@router.get("/today")
def today_stats():
    """Get today's statistics from database"""
    print("=== /api/analytics/today ENDPOINT CALLED ===")
    con = None
    try:
        db_path = get_db_path()
        print(f"Database path: {db_path}")
        con = sqlite3.connect(db_path)
        print("Database connection opened")
        today = date.today().isoformat()
        print(f"Today's date: {today}")
        
        # Check if tables exist
        print("Checking table existence...")
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        print(f"Found tables: {tables}")
        
        # Page views (you increment on each /v1/calculate call)
        pv = 0
        if 'page_views' in tables:
            try:
                print("Querying page_views table...")
                pv_result = con.execute("SELECT COUNT(*) FROM page_views WHERE date = ?", (today,)).fetchone()
                pv = pv_result[0] if pv_result else 0
                print(f"Page views: {pv}")
            except Exception as e:
                print(f"Error counting page views: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("page_views table does not exist")
        
        # Unique visitors (distinct IP)
        uv = 0
        if 'page_views' in tables:
            try:
                print("Querying unique visitors...")
                uv_result = con.execute("SELECT COUNT(DISTINCT ip) FROM page_views WHERE date = ?", (today,)).fetchone()
                uv = uv_result[0] if uv_result else 0
                print(f"Unique visitors: {uv}")
            except Exception as e:
                print(f"Error counting unique visitors: {e}")
                import traceback
                traceback.print_exc()
        
        # Calculations today
        calc = 0
        if 'calculations' in tables:
            try:
                print("Querying calculations table...")
                calc_result = con.execute("SELECT COUNT(*) FROM calculations WHERE date(date) = ?", (today,)).fetchone()
                calc = calc_result[0] if calc_result else 0
                print(f"Calculations: {calc}")
            except Exception as e:
                print(f"Error counting calculations: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("calculations table does not exist")
        
        # Paid today (Stripe webhook inserts row)
        paid = 0
        if 'payments' in tables:
            try:
                print("Querying payments table...")
                paid_result = con.execute("SELECT SUM(amount) FROM payments WHERE date(date) = ?", (today,)).fetchone()
                paid = paid_result[0] if paid_result and paid_result[0] else 0
                print(f"Payments: {paid}")
            except Exception as e:
                print(f"Error calculating payments: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("payments table does not exist")
        
        result = {"pv": pv, "uv": uv, "calc": calc, "paid": paid}
        print(f"Returning result: {result}")
        return result
    except Exception as e:
        print(f"=== ERROR in today_stats: {e} ===")
        import traceback
        traceback.print_exc()
        return {"pv": 0, "uv": 0, "calc": 0, "paid": 0, "error": str(e)}
    finally:
        if con:
            print("Closing database connection")
            con.close()

