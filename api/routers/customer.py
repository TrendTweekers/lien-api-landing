from fastapi import APIRouter, HTTPException, Request, Depends, Header
from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_user_from_session, get_current_user
from pydantic import BaseModel, EmailStr
import logging
import subprocess
import sys
import os
import hmac
from pathlib import Path

router = APIRouter()
logger = logging.getLogger(__name__)

def require_cron_secret(request: Request, x_cron_secret: str = Header(None, alias="x-cron-secret")):
    """
    Dependency for Railway cron endpoints.
    Validates X-CRON-SECRET header against CRON_SECRET env var using constant-time comparison.
    """
    route_path = request.url.path
    cron_secret = os.environ.get("CRON_SECRET")
    client_ip = request.client.host if request.client else "unknown"
    
    # If CRON_SECRET env var is missing, treat cron endpoints as disabled
    if not cron_secret:
        logger.error(f"CRON_DENY route={route_path} reason=CRON_SECRET_not_configured")
        raise HTTPException(
            status_code=503,
            detail="Cron endpoints are disabled: CRON_SECRET environment variable not configured"
        )
    
    # If header is missing or doesn't match, deny
    if not x_cron_secret:
        logger.warning(f"CRON_DENY route={route_path} ip={client_ip} reason=missing_header")
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(x_cron_secret, cron_secret):
        logger.warning(f"CRON_DENY route={route_path} ip={client_ip} reason=secret_mismatch")
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    
    # Success - log acceptance
    logger.info(f"CRON_OK route={route_path} ip={client_ip}")
    return True

class EmailPrefsIn(BaseModel):
    alert_email: Optional[EmailStr] = None  # Legacy single email
    email_alerts_enabled: Optional[bool] = None  # Legacy flag
    notification_emails: Optional[str] = None  # New: comma-separated emails

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
            
            # Check if user has Zapier token and get email alert preferences
            zapier_connected = False
            alert_email = None
            email_alerts_enabled = True
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT zapier_token_hash, alert_email, email_alerts_enabled 
                    FROM users 
                    WHERE email = %s
                """, (email,))
            else:
                cursor.execute("""
                    SELECT zapier_token_hash, alert_email, email_alerts_enabled 
                    FROM users 
                    WHERE email = ?
                """, (email,))
            
            user_row = cursor.fetchone()
            if user_row:
                if isinstance(user_row, dict):
                    zapier_connected = user_row.get('zapier_token_hash') is not None
                    alert_email = user_row.get('alert_email')
                    email_alerts_enabled = bool(user_row.get('email_alerts_enabled', True))
                else:
                    zapier_connected = user_row[0] is not None if len(user_row) > 0 else False
                    alert_email = user_row[1] if len(user_row) > 1 else None
                    email_alerts_enabled = bool(user_row[2]) if len(user_row) > 2 else True
        
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
            "alert_email": alert_email,
            "email_alerts_enabled": email_alerts_enabled,
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
async def get_email_captures(request: Request, limit: int = 100, user = Depends(get_current_user)):
    """Admin-only endpoint to get email captures"""
    if user.get('email', '').lower() != "admin@stackedboost.com":
        raise HTTPException(status_code=403, detail="Forbidden")
    
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

@router.get("/api/user/preferences")
async def get_user_preferences(request: Request, current_user: dict = Depends(get_current_user)):
    """Get user email alert preferences"""
    email = current_user.get('email')
    
    if not email:
        raise HTTPException(status_code=400, detail="User email not found")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if notification_emails column exists, add if missing
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'notification_emails'
                """)
            else:
                cursor.execute("""
                    SELECT name FROM pragma_table_info('users') WHERE name = 'notification_emails'
                """)
            
            col_exists = cursor.fetchone()
            if not col_exists:
                if DB_TYPE == 'postgresql':
                    cursor.execute("ALTER TABLE users ADD COLUMN notification_emails TEXT")
                else:
                    cursor.execute("ALTER TABLE users ADD COLUMN notification_emails TEXT")
                conn.commit()
            
            # Fetch preferences
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT notification_emails, alert_email, email_alerts_enabled 
                    FROM users 
                    WHERE email = %s
                """, (email,))
            else:
                cursor.execute("""
                    SELECT notification_emails, alert_email, email_alerts_enabled 
                    FROM users 
                    WHERE email = ?
                """, (email,))
            
            row = cursor.fetchone()
            if row:
                if isinstance(row, dict):
                    notification_emails = row.get('notification_emails') or row.get('alert_email') or ""
                    alert_email = row.get('alert_email')
                    email_alerts_enabled = bool(row.get('email_alerts_enabled', True))
                else:
                    notification_emails = (row[0] if len(row) > 0 and row[0] else None) or (row[1] if len(row) > 1 and row[1] else None) or ""
                    alert_email = row[1] if len(row) > 1 else None
                    email_alerts_enabled = bool(row[2]) if len(row) > 2 else True
            else:
                notification_emails = ""
                alert_email = None
                email_alerts_enabled = True
            
            return {
                "notification_emails": notification_emails,
                "alert_email": alert_email,  # Legacy
                "email_alerts_enabled": email_alerts_enabled  # Legacy
            }
    except Exception as e:
        logger.error(f"Error fetching user preferences: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to fetch preferences")

@router.post("/api/user/preferences")
async def save_user_preferences(request: Request, body: EmailPrefsIn, current_user: dict = Depends(get_current_user)):
    """Save user email alert preferences - requires Basic+ plan"""
    from api.routers.billing import require_plan
    
    # Gate: Basic+ plans only (Free cannot enable email reminders)
    plan_info = require_plan(current_user, ["basic", "automated", "enterprise"], route_name="/api/user/preferences")
    
    email = current_user.get('email')
    user_id = current_user.get('id')
    
    if not email:
        raise HTTPException(status_code=400, detail="User email not found")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if notification_emails column exists, add if missing
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'users' AND column_name = 'notification_emails'
                """)
            else:
                cursor.execute("""
                    SELECT name FROM pragma_table_info('users') WHERE name = 'notification_emails'
                """)
            
            col_exists = cursor.fetchone()
            if not col_exists:
                if DB_TYPE == 'postgresql':
                    cursor.execute("ALTER TABLE users ADD COLUMN notification_emails TEXT")
                else:
                    cursor.execute("ALTER TABLE users ADD COLUMN notification_emails TEXT")
                conn.commit()
            
            # Determine which email field to use
            # Priority: notification_emails > alert_email (for backward compatibility)
            notification_emails = body.notification_emails
            if not notification_emails and body.alert_email:
                notification_emails = body.alert_email
            
            # Determine email_alerts_enabled
            email_alerts_enabled = body.email_alerts_enabled
            if email_alerts_enabled is None:
                email_alerts_enabled = True  # Default to enabled if not specified
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users
                    SET notification_emails = %s,
                        alert_email = %s,
                        email_alerts_enabled = %s
                    WHERE email = %s
                """, (notification_emails or "", notification_emails or body.alert_email or "", email_alerts_enabled, email))
            else:
                cursor.execute("""
                    UPDATE users
                    SET notification_emails = ?,
                        alert_email = ?,
                        email_alerts_enabled = ?
                    WHERE email = ?
                """, (notification_emails or "", notification_emails or body.alert_email or "", 1 if email_alerts_enabled else 0, email))
            
            conn.commit()
            
            return {"ok": True, "message": "Preferences saved successfully"}
            
    except Exception as e:
        logger.error(f"Error saving user preferences: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to save preferences")

@router.post("/api/admin/run-email-alerts")
async def run_email_alerts(request: Request, _cron_auth = Depends(require_cron_secret)):
    """
    Railway cron endpoint to trigger email alerts script.
    Authenticated via X-CRON-SECRET header (not user session).
    """
    # Get script path relative to project root
    script_path = Path(__file__).parent.parent.parent / "scripts" / "send_email_alerts.py"
    
    if not script_path.exists():
        raise HTTPException(
            status_code=500, 
            detail=f"Script not found at {script_path}"
        )
    
    try:
        # Run script inside the same container/environment
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(script_path.parent.parent)  # Set working directory to project root
        )
        
        # Try to extract email count from stdout if available
        emails_sent = None
        if result.stdout:
            # Look for pattern like "✅ Email alerts processed: 5 emails sent"
            import re
            match = re.search(r'(\d+)\s+emails?\s+sent', result.stdout, re.IGNORECASE)
            if match:
                try:
                    emails_sent = int(match.group(1))
                except ValueError:
                    pass
        
        return {
            "ok": result.returncode == 0,
            "code": result.returncode,
            "emails_sent": emails_sent,
            "stdout": result.stdout[-2000:] if result.stdout else "",  # Last 2000 chars
            "stderr": result.stderr[-2000:] if result.stderr else "",  # Last 2000 chars
            "message": "Email alerts script executed"
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500,
            detail="Script execution timed out after 5 minutes"
        )
    except Exception as e:
        logger.error(f"Error running email alerts script: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to run script: {str(e)}"
        )
