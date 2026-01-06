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
    user_id = user.get('id')
    
    if not email:
        raise HTTPException(status_code=400, detail="User email not found")
        
    try:
        # Check if admin (case-insensitive)
        is_admin = email.lower().strip() == "admin@stackedboost.com"
        
        # Get plan and usage from billing module
        from api.routers.billing import get_user_plan_and_usage, ensure_month_rollover
        
        if user_id:
            ensure_month_rollover(user_id, email)
            usage = get_user_plan_and_usage(user_id, email)
            plan = usage.get('plan', 'free')
            manual_count = usage.get('manual_calc_count', 0)
            api_count = usage.get('api_call_count', 0)
            usage_month = usage.get('usage_month')
        else:
            # Fallback if user_id not available
            plan = user.get('subscription_status', 'free')
            manual_count = 0
            api_count = 0
            usage_month = None
        
        # Determine limits based on plan
        manual_limit = 3 if plan == 'free' else None
        api_limit = 500 if plan == 'automated' else None
        
        # Calculate remaining
        manual_remaining = None
        if manual_limit is not None:
            manual_remaining = max(0, manual_limit - manual_count)
        
        api_remaining = None
        if api_limit is not None:
            api_remaining = max(0, api_limit - api_count)
        
        # Get next reset date (first day of next month)
        next_reset = None
        if usage_month:
            try:
                if isinstance(usage_month, str):
                    from datetime import datetime
                    usage_month_date = datetime.strptime(usage_month, '%Y-%m-%d').date()
                else:
                    usage_month_date = usage_month
                from datetime import date
                if usage_month_date.month == 12:
                    next_reset = date(usage_month_date.year + 1, 1, 1)
                else:
                    next_reset = date(usage_month_date.year, usage_month_date.month + 1, 1)
            except:
                pass
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
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
            "plan": plan,
            "subscriptionStatus": plan,  # Backward compatibility
            "manual_calc_used": manual_count,
            "manual_calc_limit": manual_limit,
            "manual_calc_remaining": manual_remaining,
            "api_calls_used": api_count,
            "api_calls_limit": api_limit,
            "api_calls_remaining": api_remaining,
            "zapier_connected": zapier_connected,
            "is_admin": is_admin,
            "usage_month": usage_month.isoformat() if usage_month else None,
            "next_reset": next_reset.isoformat() if next_reset else None,
            # Backward compatibility fields
            "calculationsUsed": manual_count,
            "calculationsLimit": manual_limit,
            "calculationsRemaining": manual_remaining,
        }
    except Exception as e:
        logger.error(f"Error fetching user stats: {e}")
        import traceback
        traceback.print_exc()
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

@router.get("/api/admin/email-captures")
async def get_email_captures(request: Request, limit: int = 100):
    """Admin-only endpoint to get email captures"""
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    email = user.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="User email not found")
    
    # Check if admin (case-insensitive)
    is_admin = email.lower().strip() == "admin@stackedboost.com"
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if email_captures table exists
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT email, created_at, ip_address, last_used_at
                    FROM email_captures
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (limit,))
            else:
                cursor.execute("""
                    SELECT email, created_at, ip_address, last_used_at
                    FROM email_captures
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            captures = []
            
            for row in rows:
                if isinstance(row, dict):
                    captures.append({
                        "email": row.get('email'),
                        "created_at": row.get('created_at'),
                        "ip_address": row.get('ip_address'),
                        "last_used_at": row.get('last_used_at'),
                    })
                elif isinstance(row, tuple):
                    captures.append({
                        "email": row[0] if len(row) > 0 else None,
                        "created_at": row[1] if len(row) > 1 else None,
                        "ip_address": row[2] if len(row) > 2 else None,
                        "last_used_at": row[3] if len(row) > 3 else None,
                    })
            
            return {
                "success": True,
                "count": len(captures),
                "captures": captures
            }
    except Exception as e:
        logger.error(f"Error fetching email captures: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch email captures: {str(e)}")
