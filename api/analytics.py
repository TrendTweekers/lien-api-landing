from fastapi import APIRouter
from datetime import date, datetime
import sqlite3
from pathlib import Path

router = APIRouter(prefix="/analytics", tags=["analytics"])

def get_db_path():
    """Get database path (works in Railway and local)"""
    db_path = Path(__file__).parent.parent / "admin.db"
    return str(db_path)

@router.get("/today")
def today_stats():
    """Get today's statistics from database"""
    con = sqlite3.connect(get_db_path())
    today = date.today().isoformat()
    
    try:
        # Page views (you increment on each /v1/calculate call)
        pv_result = con.execute("SELECT COUNT(*) FROM page_views WHERE date = ?", (today,)).fetchone()
        pv = pv_result[0] if pv_result else 0
        
        # Unique visitors (distinct IP)
        uv_result = con.execute("SELECT COUNT(DISTINCT ip) FROM page_views WHERE date = ?", (today,)).fetchone()
        uv = uv_result[0] if uv_result else 0
        
        # Calculations today
        calc_result = con.execute("SELECT COUNT(*) FROM calculations WHERE date(date) = ?", (today,)).fetchone()
        calc = calc_result[0] if calc_result else 0
        
        # Paid today (Stripe webhook inserts row)
        paid_result = con.execute("SELECT SUM(amount) FROM payments WHERE date(date) = ?", (today,)).fetchone()
        paid = paid_result[0] if paid_result and paid_result[0] else 0
        
    except sqlite3.OperationalError as e:
        # Table doesn't exist yet - return zeros
        print(f"Analytics tables not initialized: {e}")
        pv = uv = calc = paid = 0
    
    con.close()
    return {"pv": pv, "uv": uv, "calc": calc, "paid": paid}

