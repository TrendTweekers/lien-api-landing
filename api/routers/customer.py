from fastapi import APIRouter, HTTPException, Request, Depends
from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_user_from_session
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/api/user/stats")
async def get_user_stats(request: Request):
    """Get user statistics including subscription status and calculation counts"""
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    email = user.get('email')
    subscription_status = user.get('subscription_status', 'free')
    
    if not email:
        raise HTTPException(status_code=400, detail="User email not found")
        
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Count calculations
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE user_email = %s", (email,))
            else:
                cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE user_email = ?", (email,))
            
            calc_result = cursor.fetchone()
            calc_count = 0
            if calc_result:
                if isinstance(calc_result, dict):
                    calc_count = calc_result.get('count', 0)
                elif hasattr(calc_result, 'keys'):
                    try:
                        calc_count = calc_result['count']
                    except KeyError:
                        calc_count = calc_result[0] if len(calc_result) > 0 else 0
                else:
                    calc_count = calc_result[0] if len(calc_result) > 0 else 0
            
            # Check if user has Zapier token
            zapier_connected = False
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT zapier_token_hash FROM users WHERE email = %s", (email,))
            else:
                cursor.execute("SELECT zapier_token_hash FROM users WHERE email = ?", (email,))
            
            zapier_result = cursor.fetchone()
            if zapier_result:
                if isinstance(zapier_result, dict):
                    zapier_connected = zapier_result.get('zapier_token_hash') is not None
                else:
                    zapier_connected = zapier_result[0] is not None if len(zapier_result) > 0 else False
            
            return {
                "email": email,
                "subscriptionStatus": subscription_status,
                "calculationsUsed": calc_count,
                "calculationsLimit": 3 if subscription_status == 'free' else None,
                "zapier_connected": zapier_connected
            }
    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch user stats")

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
                cursor.execute("SELECT api_calls FROM customers WHERE email = %s", (email,))
            else:
                cursor.execute("SELECT api_calls FROM customers WHERE email = ?", (email,))
                
            row = cursor.fetchone()
            
            api_calls = 0
            if row:
                if isinstance(row, dict):
                    api_calls = row.get('api_calls', 0)
                elif hasattr(row, 'keys'): # Handle sqlite3.Row
                    try:
                        api_calls = row['api_calls']
                    except KeyError:
                        api_calls = 0
                elif isinstance(row, tuple):
                    api_calls = row[0]
                else:
                    api_calls = getattr(row, 'api_calls', 0)
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
