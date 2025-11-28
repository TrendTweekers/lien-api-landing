from fastapi import APIRouter
from datetime import date, datetime
import sqlite3
import os
from pathlib import Path

router = APIRouter(prefix="/analytics", tags=["analytics"])

def get_db_path():
    """Get database path (works in Railway and local)"""
    BASE_DIR = Path(__file__).parent.parent
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    return str(db_path)

@router.get("/today")
def today_stats():
    """Get today's statistics from database"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        today = date.today().isoformat()
        
        # Check if tables exist
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        
        # Page views (you increment on each /v1/calculate call)
        pv = 0
        if 'page_views' in tables:
            try:
                pv_result = con.execute("SELECT COUNT(*) FROM page_views WHERE date = ?", (today,)).fetchone()
                pv = pv_result[0] if pv_result else 0
            except Exception as e:
                print(f"Error counting page views: {e}")
        
        # Unique visitors (distinct IP)
        uv = 0
        if 'page_views' in tables:
            try:
                uv_result = con.execute("SELECT COUNT(DISTINCT ip) FROM page_views WHERE date = ?", (today,)).fetchone()
                uv = uv_result[0] if uv_result else 0
            except Exception as e:
                print(f"Error counting unique visitors: {e}")
        
        # Calculations today
        calc = 0
        if 'calculations' in tables:
            try:
                calc_result = con.execute("SELECT COUNT(*) FROM calculations WHERE date(date) = ?", (today,)).fetchone()
                calc = calc_result[0] if calc_result else 0
            except Exception as e:
                print(f"Error counting calculations: {e}")
        
        # Paid today (Stripe webhook inserts row)
        paid = 0
        if 'payments' in tables:
            try:
                paid_result = con.execute("SELECT SUM(amount) FROM payments WHERE date(date) = ?", (today,)).fetchone()
                paid = paid_result[0] if paid_result and paid_result[0] else 0
            except Exception as e:
                print(f"Error calculating payments: {e}")
        
        return {"pv": pv, "uv": uv, "calc": calc, "paid": paid}
    except Exception as e:
        print(f"Error in today_stats: {e}")
        import traceback
        traceback.print_exc()
        return {"pv": 0, "uv": 0, "calc": 0, "paid": 0, "error": str(e)}
    finally:
        if con:
            con.close()

