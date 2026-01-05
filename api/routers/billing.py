"""
Billing and plan enforcement module
Handles plan limits, usage tracking, and month rollover
"""
from datetime import date, datetime
from typing import Literal
from fastapi import HTTPException
from api.database import get_db, get_db_cursor, DB_TYPE
import logging

logger = logging.getLogger(__name__)

UsageKind = Literal["manual", "api", "zapier_webhook"]
PlanType = Literal["free", "basic", "automated", "enterprise"]

def get_month_start(dt: date = None) -> date:
    """Get the first day of the month for a given date (or current month)"""
    if dt is None:
        dt = date.today()
    return date(dt.year, dt.month, 1)


def ensure_month_rollover(user_id: int, user_email: str = None):
    """
    Check if we've rolled into a new month and reset counters if needed.
    Updates the user's usage_month and resets all counters to 0.
    """
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            current_month_start = get_month_start()
            
            # Get current usage_month for user
            if DB_TYPE == 'postgresql':
                cursor.execute(
                    "SELECT usage_month FROM users WHERE id = %s",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT usage_month FROM users WHERE id = ?",
                    (user_id,)
                )
            
            result = cursor.fetchone()
            user_month_start = None
            
            if result:
                if isinstance(result, dict):
                    user_month_start = result.get('usage_month')
                elif hasattr(result, 'keys'):
                    user_month_start = result['usage_month'] if 'usage_month' in result.keys() else None
                else:
                    user_month_start = result[0] if len(result) > 0 else None
                
                # Convert string to date if needed
                if isinstance(user_month_start, str):
                    user_month_start = datetime.strptime(user_month_start, '%Y-%m-%d').date()
            
            # If no usage_month set or it's a different month, reset counters
            if user_month_start is None or user_month_start < current_month_start:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE users 
                        SET usage_month = %s,
                            manual_calc_count = 0,
                            api_call_count = 0,
                            zapier_webhook_count = 0
                        WHERE id = %s
                    """, (current_month_start, user_id))
                else:
                    cursor.execute("""
                        UPDATE users 
                        SET usage_month = ?,
                            manual_calc_count = 0,
                            api_call_count = 0,
                            zapier_webhook_count = 0
                        WHERE id = ?
                    """, (current_month_start.isoformat(), user_id))
                
                conn.commit()
                logger.info(f"Month rollover: Reset counters for user {user_id} (email: {user_email})")
                return True
            
            return False
    except Exception as e:
        logger.error(f"Error in ensure_month_rollover for user {user_id}: {e}")
        # Don't raise - allow operation to continue
        return False


def increment_usage(user_id: int, kind: UsageKind, user_email: str = None):
    """
    Increment usage counter for a user.
    kind: "manual", "api", or "zapier_webhook"
    
    Note: zapier_webhook also increments api_call_count (counts toward 500 limit)
    """
    try:
        ensure_month_rollover(user_id, user_email)
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if kind == "manual":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE users 
                        SET manual_calc_count = manual_calc_count + 1
                        WHERE id = %s
                    """, (user_id,))
                else:
                    cursor.execute("""
                        UPDATE users 
                        SET manual_calc_count = manual_calc_count + 1
                        WHERE id = ?
                    """, (user_id,))
            
            elif kind == "api":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE users 
                        SET api_call_count = api_call_count + 1
                        WHERE id = %s
                    """, (user_id,))
                else:
                    cursor.execute("""
                        UPDATE users 
                        SET api_call_count = api_call_count + 1
                        WHERE id = ?
                    """, (user_id,))
            
            elif kind == "zapier_webhook":
                # Zapier webhooks count toward both zapier_webhook_count AND api_call_count
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE users 
                        SET zapier_webhook_count = zapier_webhook_count + 1,
                            api_call_count = api_call_count + 1
                        WHERE id = %s
                    """, (user_id,))
                else:
                    cursor.execute("""
                        UPDATE users 
                        SET zapier_webhook_count = zapier_webhook_count + 1,
                            api_call_count = api_call_count + 1
                        WHERE id = ?
                    """, (user_id,))
            
            conn.commit()
            logger.info(f"Incremented {kind} usage for user {user_id} (email: {user_email})")
            return True
    except Exception as e:
        logger.error(f"Error incrementing {kind} usage for user {user_id}: {e}")
        return False


def get_user_plan_and_usage(user_id: int, user_email: str = None):
    """
    Get user's plan and current usage counts.
    Returns dict with plan, manual_calc_count, api_call_count, zapier_webhook_count, usage_month
    """
    try:
        ensure_month_rollover(user_id, user_email)
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT plan, manual_calc_count, api_call_count, 
                           zapier_webhook_count, usage_month
                    FROM users WHERE id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT plan, manual_calc_count, api_call_count, 
                           zapier_webhook_count, usage_month
                    FROM users WHERE id = ?
                """, (user_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            if isinstance(result, dict):
                return {
                    'plan': result.get('plan', 'free'),
                    'manual_calc_count': result.get('manual_calc_count', 0),
                    'api_call_count': result.get('api_call_count', 0),
                    'zapier_webhook_count': result.get('zapier_webhook_count', 0),
                    'usage_month': result.get('usage_month'),
                }
            else:
                return {
                    'plan': result[0] if len(result) > 0 else 'free',
                    'manual_calc_count': result[1] if len(result) > 1 else 0,
                    'api_call_count': result[2] if len(result) > 2 else 0,
                    'zapier_webhook_count': result[3] if len(result) > 3 else 0,
                    'usage_month': result[4] if len(result) > 4 else None,
                }
    except Exception as e:
        logger.error(f"Error getting plan/usage for user {user_id}: {e}")
        return {
            'plan': 'free',
            'manual_calc_count': 0,
            'api_call_count': 0,
            'zapier_webhook_count': 0,
            'usage_month': None,
        }


def check_plan_limit(user_id: int, feature: str, user_email: str = None) -> dict:
    """
    Check if user can access a feature based on their plan.
    Returns dict with 'allowed' boolean and optional 'error' dict for 402 response.
    
    feature: "manual_calc", "zapier", "api"
    """
    usage = get_user_plan_and_usage(user_id, user_email)
    if not usage:
        # Default to free plan if user not found
        usage = {
            'plan': 'free',
            'manual_calc_count': 0,
            'api_call_count': 0,
            'zapier_webhook_count': 0,
        }
    
    plan = usage.get('plan', 'free')
    manual_count = usage.get('manual_calc_count', 0)
    api_count = usage.get('api_call_count', 0)
    
    if feature == "manual_calc":
        if plan == "free":
            if manual_count >= 3:
                return {
                    'allowed': False,
                    'error': {
                        'code': 'LIMIT_REACHED',
                        'limit_type': 'manual_calcs',
                        'used': manual_count,
                        'limit': 3,
                        'plan': 'free'
                    }
                }
        # basic, automated, enterprise: unlimited manual
        return {'allowed': True}
    
    elif feature == "zapier":
        if plan == "free" or plan == "basic":
            return {
                'allowed': False,
                'error': {
                    'code': 'UPGRADE_REQUIRED',
                    'feature': 'zapier',
                    'plan': plan
                }
            }
        # automated, enterprise: allowed
        return {'allowed': True}
    
    elif feature == "api":
        if plan == "free" or plan == "basic":
            return {
                'allowed': False,
                'error': {
                    'code': 'UPGRADE_REQUIRED',
                    'feature': 'api',
                    'plan': plan
                }
            }
        elif plan == "automated":
            if api_count >= 500:
                return {
                    'allowed': False,
                    'error': {
                        'code': 'LIMIT_REACHED',
                        'limit_type': 'api_calls',
                        'used': api_count,
                        'limit': 500,
                        'plan': 'automated'
                    }
                }
        # enterprise: unlimited
        return {'allowed': True}
    
    return {'allowed': True}

