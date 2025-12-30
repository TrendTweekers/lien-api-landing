from fastapi import APIRouter, HTTPException, Request, Depends
from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_user_from_session
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/api/customer/stats")
async def get_customer_stats(request: Request):
    """Get statistics for the logged-in customer"""
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    email = user.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="User email not found")
        
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Query customers table for API calls
            # Note: auth uses 'users' table, but stats seem to be in 'customers' table
            # We assume email is the common key
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT calls_used FROM customers WHERE email = %s", (email,))
            else:
                cursor.execute("SELECT calls_used FROM customers WHERE email = ?", (email,))
                
            row = cursor.fetchone()
            
            api_calls = 0
            if row:
                if isinstance(row, dict):
                    api_calls = row.get('calls_used', 0)
                elif isinstance(row, tuple):
                    api_calls = row[0]
                else:
                    api_calls = getattr(row, 'calls_used', 0)
            else:
                # If not in customers table, maybe insert it? 
                # Or just return 0
                logger.warning(f"Customer not found in customers table: {email}")
                
            return {
                "api_calls": api_calls,
                "email": email,
                "plan": user.get('subscription_status', 'active') # From auth session
            }
            
    except Exception as e:
        logger.error(f"Error fetching customer stats: {e}")
        return {
            "api_calls": 0,
            "error": str(e)
        }
