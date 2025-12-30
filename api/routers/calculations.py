from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import hashlib

from ..database import get_db, get_db_cursor, DB_TYPE
from ..rate_limiter import limiter
from ..calculators import (
    calculate_state_deadline, 
    VALID_STATES, 
    STATE_CODE_TO_NAME, 
    STATE_RULES
)

router = APIRouter()

# --- Models ---

class TrackCalculationRequest(BaseModel):
    """Request model for tracking calculation attempts"""
    state: Optional[str] = None
    notice_date: Optional[str] = None
    last_work_date: Optional[str] = None
    email: Optional[str] = None  # Allow email to be sent from frontend for admin check

class CalculateDeadlineRequest(BaseModel):
    invoice_date: str
    state: str
    role: str = "supplier"
    project_type: str = "commercial"
    notice_of_completion_date: Optional[str] = None
    notice_of_commencement_filed: Optional[bool] = False

# --- Helpers ---

def get_client_ip(request: Request) -> str:
    """Get real client IP from headers (works with Railway/Cloudflare)"""
    return (
        request.headers.get("cf-connecting-ip") or 
        request.headers.get("x-forwarded-for", "").split(",")[0].strip() or
        request.headers.get("x-real-ip") or
        (request.client.host if request.client else "unknown")
    )

def get_user_agent_hash(request: Request) -> str:
    """Get a hash of user agent for better tracking (handles shared IPs)"""
    user_agent = request.headers.get('user-agent', 'unknown')
    return hashlib.md5(user_agent.encode()).hexdigest()[:8]

def is_broker_email(email: str) -> bool:
    """
    Check if an email belongs to a broker.
    Returns True if email exists in brokers table with approved/active status.
    """
    if not email:
        return False
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
        
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id FROM brokers 
                    WHERE LOWER(email) = LOWER(%s) 
                    AND status IN ('approved', 'active')
                    LIMIT 1
                """, (email.lower().strip(),))
            else:
                cursor.execute("""
                    SELECT id FROM brokers 
                    WHERE LOWER(email) = LOWER(?) 
                    AND status IN ('approved', 'active')
                    LIMIT 1
                """, (email.lower().strip(),))
        
            result = cursor.fetchone()
            return result is not None
        
    except Exception as e:
        print(f"⚠️ Error checking broker email: {e}")
        return False  # Fail closed - assume not a broker if check fails

def get_user_from_session(request: Request):
    """Helper to get logged-in user from session token"""
    authorization = request.headers.get('authorization', '')
    if not authorization or not authorization.startswith('Bearer '):
        return None

    token = authorization.replace('Bearer ', '')

    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
        
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT email, subscription_status FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT email, subscription_status FROM users WHERE session_token = ?", (token,))
        
            user = cursor.fetchone()
        
            if user:
                if isinstance(user, dict):
                    email = user.get('email')
                    subscription_status = user.get('subscription_status')
                elif hasattr(user, 'keys'):
                    email = user['email'] if 'email' in user.keys() else (user[0] if len(user) > 0 else None)
                    subscription_status = user['subscription_status'] if 'subscription_status' in user.keys() else (user[1] if len(user) > 1 else None)
                else:
                    email = user[0] if user and len(user) > 0 else None
                    subscription_status = user[1] if user and len(user) > 1 else None
            
                if subscription_status in ['active', 'trialing']:
                    return {'email': email, 'subscription_status': subscription_status, 'unlimited': True}
    except Exception as e:
        print(f"⚠️ Error checking session: {e}")

    return None

# --- Endpoints ---

@router.post("/v1/calculate")
def legacy_calculate(request: Request):
    """
    Legacy endpoint - mapped to get_user_from_session logic.
    Originally in api/main.py as @app.post("/v1/calculate") decorating get_user_from_session.
    """
    return get_user_from_session(request)

@router.get("/v1/states")
def get_states():
    """Get list of supported states - returns all 51 states with code and name"""
    try:
        # Try to get states from database with names
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT state_code, state_name 
                    FROM lien_deadlines 
                    ORDER BY state_code
                """)
            else:
                cursor.execute("""
                    SELECT state_code, state_name 
                    FROM lien_deadlines 
                    ORDER BY state_code
                """)
            states = cursor.fetchall()
        
            if states:
                result = []
                for row in states:
                    if isinstance(row, dict):
                        result.append({
                            "code": row.get("state_code"),
                            "name": row.get("state_name")
                        })
                    else:
                        result.append({
                            "code": row[0],
                            "name": row[1]
                        })
                return {
                    "states": result,
                    "count": len(result)
                }
    except Exception as e:
        print(f"⚠️ Error querying database for states: {e}")

    # Fallback: return state codes only if database query fails
    return {
        "states": [{"code": code, "name": code} for code in VALID_STATES],
        "count": len(VALID_STATES)
    }

@router.post("/api/v1/track-calculation")
@limiter.limit("20/minute")
async def track_calculation(request: Request, request_data: Optional[TrackCalculationRequest] = None):
    """
    Track calculation attempt and enforce server-side limits.
    Returns whether calculation is allowed and current count.
    Also returns calculation results for authenticated users (Dashboard).
    """
    try:
        client_ip = get_client_ip(request)
        user_agent_hash = get_user_agent_hash(request)
    
        # Create composite key: IP + user agent hash (handles shared IPs better)
        tracking_key = f"{client_ip}:{user_agent_hash}"
    
        # Get email from request first (for admin check before DB lookup)
        request_email = None
        if request_data and request_data.email:
            request_email = request_data.email.strip().lower()

    except Exception:
        pass

    # We use get_user_from_session to avoid breaking public site (which sends no token)
    # This allows both authenticated (Dashboard) and public usage
    logged_in_user = get_user_from_session(request)


    # Admin/dev user bypass (check BEFORE database lookup)
    DEV_EMAIL = "kartaginy1@gmail.com"
    # Allow bypass if dev email OR user is logged in
    if (request_email and request_email == DEV_EMAIL.lower()) or logged_in_user:
        if logged_in_user:
            print(f"✅ Logged-in user detected: {logged_in_user.get('email')} - allowing unlimited calculations")
        else:
            print(f"✅ Admin/dev user detected from request: {request_email} - allowing unlimited calculations")
    
        # Calculate deadlines if data is provided (Admin/Logged-in bypass)
        calculation_result = {}
        if request_data and request_data.state and request_data.notice_date:
            try:
                state_code = request_data.state.upper()
                if state_code in VALID_STATES:
                    # Parse date
                    invoice_date_str = request_data.notice_date
                    invoice_date = None
                    try:
                        invoice_date = datetime.strptime(invoice_date_str, "%m/%d/%Y")
                    except ValueError:
                        try:
                            invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
                        except ValueError:
                            try:
                                invoice_date = datetime.fromisoformat(invoice_date_str)
                            except ValueError:
                                pass
            
                    if invoice_date:
                        # Get rules
                        rules = STATE_RULES.get(state_code, {})
                
                        # Calculate
                        result = calculate_state_deadline(
                            state_code=state_code,
                            invoice_date=invoice_date,
                            role="supplier",
                            project_type="commercial",
                            state_rules=rules
                        )
                
                        # Extract deadlines
                        prelim_deadline = result.get("preliminary_deadline")
                        lien_deadline = result.get("lien_deadline")
                        prelim_required = result.get("preliminary_required", rules.get("preliminary_notice", {}).get("required", False))
                
                        # Format dates
                        prelim_deadline_str = prelim_deadline.strftime('%Y-%m-%d') if prelim_deadline else None
                        lien_deadline_str = lien_deadline.strftime('%Y-%m-%d') if lien_deadline else None
                        noi_deadline_str = result.get("notice_of_intent_deadline").strftime('%Y-%m-%d') if result.get("notice_of_intent_deadline") else None
                
                        today = datetime.now()
                        days_to_prelim = (prelim_deadline - today).days if prelim_deadline else None
                        days_to_lien = (lien_deadline - today).days if lien_deadline else None
                
                        # Urgency helper
                        def get_urgency(days):
                            if days <= 7: return "critical"
                            elif days <= 30: return "warning"
                            else: return "normal"
                
                        prelim_notice = rules.get("preliminary_notice", {})
                        lien_filing = rules.get("lien_filing", {})
                
                        # Build result with 3 formats
                        calculation_result = {
                            "preliminary_notice": {
                                "required": prelim_required,
                                "deadline": prelim_deadline_str,
                                "days": days_to_prelim,
                                "days_from_now": days_to_prelim,
                                "urgency": get_urgency(days_to_prelim) if days_to_prelim else None,
                                "description": prelim_notice.get("description", prelim_notice.get("deadline_description", ""))
                            },
                            "lien_filing": {
                                "deadline": lien_deadline_str,
                                "days": days_to_lien,
                                "days_from_now": days_to_lien,
                                "urgency": get_urgency(days_to_lien) if days_to_lien else None,
                                "description": lien_filing.get("description", lien_filing.get("deadline_description", ""))
                            },
                            "lien_deadline": {
                                "deadline": lien_deadline_str,
                                "days": days_to_lien
                            },
                            "preliminary_notice_deadline": prelim_deadline_str,
                            "notice_of_intent_deadline": noi_deadline_str,
                            "prelim_deadline": prelim_deadline_str
                        }
            except Exception as e:
                print(f"Error in track_calculation: {str(e)}")
                # If possible, return a fallback or re-raise 
                raise HTTPException(status_code=500, detail=str(e))

        # Universal Format return for Admin/Logged-in Users
        return JSONResponse(content={
            "id": None, # No ID for unsaved calculation
            "status": "success",
            "quota_remaining": "Unlimited",
            
            # 1. New Flat Keys
            "preliminary_notice_deadline": prelim_deadline_str,
            "lien_deadline": lien_deadline_str,
            "notice_of_intent_deadline": noi_deadline_str,

            # 2. Nested Objects (REQUIRED for Dashboard)
            "preliminary_notice": {
                "deadline": prelim_deadline_str,
                "required": prelim_required,
                "days_remaining": days_to_prelim if days_to_prelim is not None else 0
            },
            "lien_filing": {
                "deadline": lien_deadline_str,
                "days_remaining": days_to_lien if days_to_lien is not None else 0
            },
            
            # 3. Legacy Keys
            "prelim_deadline": prelim_deadline_str
        })

    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
    
            # Ensure email_gate_tracking table exists with tracking_key column
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_gate_tracking (
                        id SERIAL PRIMARY KEY,
                        ip_address VARCHAR NOT NULL,
                        tracking_key VARCHAR NOT NULL,
                        email VARCHAR,
                        calculation_count INTEGER DEFAULT 0,
                        first_calculation_at TIMESTAMP DEFAULT NOW(),
                        last_calculation_at TIMESTAMP DEFAULT NOW(),
                        email_captured_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                # Add tracking_key column if it doesn't exist (migration)
                try:
                    cursor.execute("ALTER TABLE email_gate_tracking ADD COLUMN IF NOT EXISTS tracking_key VARCHAR")
                except:
                    pass  # Column might already exist
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_tracking_key ON email_gate_tracking(tracking_key)")
        
                # Get current tracking record
                cursor.execute("""
                    SELECT calculation_count, email, email_captured_at 
                    FROM email_gate_tracking 
                    WHERE tracking_key = %s 
                    ORDER BY last_calculation_at DESC 
                    LIMIT 1
                """, (tracking_key,))
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_gate_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        tracking_key TEXT NOT NULL,
                        email TEXT,
                        calculation_count INTEGER DEFAULT 0,
                        first_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        email_captured_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Add tracking_key column if it doesn't exist (migration)
                try:
                    cursor.execute("ALTER TABLE email_gate_tracking ADD COLUMN tracking_key TEXT")
                except:
                    pass  # Column might already exist
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_tracking_key ON email_gate_tracking(tracking_key)")
        
                cursor.execute("""
                    SELECT calculation_count, email, email_captured_at 
                    FROM email_gate_tracking 
                    WHERE tracking_key = ? 
                    ORDER BY last_calculation_at DESC 
                    LIMIT 1
                """, (tracking_key,))
    
            tracking = cursor.fetchone()
    
            # Parse tracking data
            if tracking:
                if isinstance(tracking, dict):
                    count = tracking.get('calculation_count', 0)
                    db_email = tracking.get('email')
                    email_captured_at = tracking.get('email_captured_at')
                elif hasattr(tracking, 'keys'):
                    count = tracking['calculation_count'] if 'calculation_count' in tracking.keys() else tracking[0]
                    db_email = tracking['email'] if 'email' in tracking.keys() else (tracking[1] if len(tracking) > 1 else None)
                    email_captured_at = tracking['email_captured_at'] if 'email_captured_at' in tracking.keys() else (tracking[2] if len(tracking) > 2 else None)
                else:
                    count = tracking[0] if tracking else 0
                    db_email = tracking[1] if tracking and len(tracking) > 1 else None
                    email_captured_at = tracking[2] if tracking and len(tracking) > 2 else None
            else:
                count = 0
                db_email = None
                email_captured_at = None
    
            # Use email from request if provided, otherwise use DB email
            email = request_email or (db_email.lower() if db_email else None)
    
            # Determine limits
            CALCULATIONS_BEFORE_EMAIL = 3
            TOTAL_FREE_CALCULATIONS = 6
    
            # Check if user is a broker
            is_broker = email and is_broker_email(email)
            if is_broker:
                print(f"⚠️ Broker attempting calculation: {email} - applying same limits as customers")
    
            # Update email if provided
            if request_email and request_email != db_email:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE email_gate_tracking 
                        SET email = %s, email_captured_at = NOW() 
                        WHERE tracking_key = %s
                    """, (request_email, tracking_key))
                else:
                    cursor.execute("""
                        UPDATE email_gate_tracking 
                        SET email = ?, email_captured_at = CURRENT_TIMESTAMP 
                        WHERE tracking_key = ?
                    """, (request_email, tracking_key))
                conn.commit()
    
            # PERFORM CALCULATION IF DATA AVAILABLE
            calculation_result = {}
            if request_data and request_data.state and request_data.notice_date:
                try:
                    state_code = request_data.state.upper()
                    if state_code in VALID_STATES:
                        # Parse date
                        invoice_date_str = request_data.notice_date
                        invoice_date = None
                        try:
                            invoice_date = datetime.strptime(invoice_date_str, "%m/%d/%Y")
                        except ValueError:
                            try:
                                invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
                            except ValueError:
                                try:
                                    invoice_date = datetime.fromisoformat(invoice_date_str)
                                except ValueError:
                                    pass
                
                        if invoice_date:
                            # Get rules
                            rules = STATE_RULES.get(state_code, {})
                    
                            # Calculate
                            result = calculate_state_deadline(
                                state_code=state_code,
                                invoice_date=invoice_date,
                                role="supplier",
                                project_type="commercial",
                                state_rules=rules
                            )
                    
                            # Extract deadlines
                            prelim_deadline = result.get("preliminary_deadline")
                            lien_deadline = result.get("lien_deadline")
                            prelim_required = result.get("preliminary_required", rules.get("preliminary_notice", {}).get("required", False))
                    
                            # Format dates
                            prelim_deadline_str = prelim_deadline.strftime('%Y-%m-%d') if prelim_deadline else None
                            lien_deadline_str = lien_deadline.strftime('%Y-%m-%d') if lien_deadline else None
                            noi_deadline_str = result.get("notice_of_intent_deadline").strftime('%Y-%m-%d') if result.get("notice_of_intent_deadline") else None
                    
                            today = datetime.now()
                            days_to_prelim = (prelim_deadline - today).days if prelim_deadline else None
                            days_to_lien = (lien_deadline - today).days if lien_deadline else None
                    
                            # Urgency helper
                            def get_urgency(days):
                                if days <= 7: return "critical"
                                elif days <= 30: return "warning"
                                else: return "normal"
                    
                            prelim_notice = rules.get("preliminary_notice", {})
                            lien_filing = rules.get("lien_filing", {})
                    
                            # Build result with 3 formats
                            calculation_result = {
                                "preliminary_notice": {
                                    "required": prelim_required,
                                    "deadline": prelim_deadline_str,
                                    "days": days_to_prelim,
                                    "days_from_now": days_to_prelim,
                                    "urgency": get_urgency(days_to_prelim) if days_to_prelim else None,
                                    "description": prelim_notice.get("description", prelim_notice.get("deadline_description", ""))
                                },
                                "lien_filing": {
                                    "deadline": lien_deadline_str,
                                    "days": days_to_lien,
                                    "days_from_now": days_to_lien,
                                    "urgency": get_urgency(days_to_lien) if days_to_lien else None,
                                    "description": lien_filing.get("description", lien_filing.get("deadline_description", ""))
                                },
                                "lien_deadline": {
                                    "deadline": lien_deadline_str,
                                    "days": days_to_lien
                                },
                                "preliminary_notice_deadline": prelim_deadline_str,
                                "notice_of_intent_deadline": noi_deadline_str,
                                "prelim_deadline": prelim_deadline_str
                            }
                except Exception as e:
                    print(f"⚠️ Error calculating in track_calculation: {e}")
    
            # Determine quota based on login status
            quota_info = {
                "limit": 6 if email else 3,
                "remaining": max(0, (6 if email else 3) - count)
            }
    
            if logged_in_user and logged_in_user.get('unlimited'):
                quota_info = {
                    "unlimited": True,
                    "remaining": 999999
                }

            return {
                "status": "allowed",
                "calculation_count": count,
                "email_provided": bool(email),
                "quota": quota_info,
                **calculation_result
            }
    
    except Exception as e:
        print(f"⚠️ Error tracking calculation: {e}")
        # Fail open
        return {"status": "allowed", "error": str(e)}

@router.post("/api/v1/calculate-deadline")
@limiter.limit("10/minute")
async def calculate_deadline(
    request: Request,
    request_data: CalculateDeadlineRequest
):
    """
    Calculate deadline - now enforces server-side limits.
    Frontend should call /api/v1/track-calculation first to check limits.
    """
    invoice_date = request_data.invoice_date
    state = request_data.state
    role = request_data.role
    project_type = request_data.project_type
    state_code = state.upper()
    
    # Check if user is logged in with active/trialing subscription
    logged_in_user = get_user_from_session(request)
    quota = {'unlimited': False, 'remaining': 0, 'limit': 3}
    
    if logged_in_user and logged_in_user.get('unlimited'):
        # Skip limit checks for logged-in active/trialing users
        quota = {'unlimited': True}
    else:
        # Get client IP and tracking key
        client_ip = get_client_ip(request)
        user_agent_hash = get_user_agent_hash(request)
        tracking_key = f"{client_ip}:{user_agent_hash}"
        
        # Check limits BEFORE processing calculation (server-side enforcement)
        try:
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                # Get current tracking
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT calculation_count, email 
                        FROM email_gate_tracking 
                        WHERE tracking_key = %s 
                        ORDER BY last_calculation_at DESC 
                        LIMIT 1
                    """, (tracking_key,))
                else:
                    cursor.execute("""
                        SELECT calculation_count, email 
                        FROM email_gate_tracking 
                        WHERE tracking_key = ? 
                        ORDER BY last_calculation_at DESC 
                        LIMIT 1
                    """, (tracking_key,))
                
                tracking = cursor.fetchone()
                
                if tracking:
                    if isinstance(tracking, dict):
                        count = tracking.get('calculation_count', 0)
                        email = tracking.get('email')
                    elif hasattr(tracking, 'keys'):
                        count = tracking['calculation_count'] if 'calculation_count' in tracking.keys() else tracking[0]
                        email = tracking['email'] if 'email' in tracking.keys() else (tracking[1] if len(tracking) > 1 else None)
                    else:
                        count = tracking[0] if tracking else 0
                        email = tracking[1] if tracking and len(tracking) > 1 else None
                    
                    # Admin/dev user bypass (check BEFORE broker check)
                    DEV_EMAIL = "kartaginy1@gmail.com"
                    is_dev_user = email and email.lower() == DEV_EMAIL.lower()
                    
                    if is_dev_user:
                        print(f"✅ Admin/dev user detected in calculate_deadline: {email} - allowing unlimited calculations")
                        quota = {'unlimited': True}
                    else:
                        # Check if user is a broker - brokers get same limits as customers
                        is_broker = email and is_broker_email(email)
                        if is_broker:
                            print(f"⚠️ Broker attempting calculation: {email} - applying same limits as customers")
                        
                        limit = 6 if email else 3
                        remaining = max(0, limit - count)
                        quota = {'unlimited': False, 'remaining': remaining, 'limit': limit}
                        
                        # Enforce limits server-side (same for brokers and customers)
                        if not email and count >= 3:
                            raise HTTPException(
                                status_code=403,
                                detail="Free trial limit reached. Please provide your email for 3 more calculations."
                            )
                        
                        if email and count >= 6:
                            # Brokers get same limits - no unlimited access
                            error_msg = "Free trial limit reached (6 calculations). Upgrade to unlimited for $299/month."
                            if is_broker:
                                error_msg += " Note: Brokers have the same calculation limits as customers."
                            raise HTTPException(
                                status_code=403,
                                detail=error_msg
                            )
        except HTTPException:
            raise
        except Exception as e:
            print(f"⚠️ Error checking limits in calculate_deadline: {e}")
            # Continue with calculation if limit check fails (fail open for UX)
    
    # Validate state
    if state_code not in VALID_STATES:
        return {
            "error": f"State {state_code} not supported",
            "available_states": VALID_STATES,
            "message": "Please select a valid US state or DC"
        }
    
    # Parse date - handle both MM/DD/YYYY and YYYY-MM-DD formats
    delivery_date = None
    try:
        delivery_date = datetime.strptime(invoice_date, "%m/%d/%Y")
    except ValueError:
        try:
            delivery_date = datetime.strptime(invoice_date, "%Y-%m-%d")
        except ValueError:
            try:
                delivery_date = datetime.fromisoformat(invoice_date)
            except ValueError:
                return {"error": "Invalid date format. Use MM/DD/YYYY or YYYY-MM-DD"}
    
    # Convert notice_of_completion_date from string to datetime if provided
    notice_of_completion_dt = None
    if request_data.notice_of_completion_date:
        try:
            if isinstance(request_data.notice_of_completion_date, str):
                try:
                    notice_of_completion_dt = datetime.strptime(request_data.notice_of_completion_date, "%Y-%m-%d")
                except ValueError:
                    notice_of_completion_dt = datetime.strptime(request_data.notice_of_completion_date, "%m/%d/%Y")
            else:
                notice_of_completion_dt = request_data.notice_of_completion_date
        except Exception as e:
            print(f"⚠️ Error parsing notice_of_completion_date: {e}")
            notice_of_completion_dt = None
            
    # Get rules
    rules = STATE_RULES.get(state_code, {})
    
    # Use unified calculation function
    result = calculate_state_deadline(
        state_code=state_code,
        invoice_date=delivery_date,
        role=role,
        project_type=project_type,
        notice_of_completion_date=notice_of_completion_dt,
        notice_of_commencement_filed=request_data.notice_of_commencement_filed or False,
        state_rules=rules
    )
    
    # Extract deadlines from result
    prelim_deadline = result.get("preliminary_deadline")
    lien_deadline = result.get("lien_deadline")
    warnings = result.get("warnings", [])
    prelim_required = result.get("preliminary_required", rules.get("preliminary_notice", {}).get("required", False))
    
    # Calculate days from now
    today = datetime.now()
    days_to_prelim = (prelim_deadline - today).days if prelim_deadline else None
    days_to_lien = (lien_deadline - today).days if lien_deadline else None
    
    # Track page view and calculation (non-blocking, PostgreSQL compatible)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Format dates for database
            today_str = date.today().isoformat()
            
            # Create tables if they don't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS page_views (
                        id SERIAL PRIMARY KEY,
                        date VARCHAR NOT NULL,
                        ip VARCHAR NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Insert page view
                client_ip = request.client.host if request and request.client else "unknown"
                cursor.execute(
                    "INSERT INTO page_views(date, ip) VALUES (%s, %s)",
                    (today_str, client_ip)
                )
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS page_views (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        ip TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert page view
                client_ip = request.client.host if request and request.client else "unknown"
                cursor.execute(
                    "INSERT INTO page_views(date, ip) VALUES (?, ?)",
                    (today_str, client_ip)
                )
            
            conn.commit()
    except Exception as e:
        print(f"⚠️ Could not save calculation: {e}")
    
    # Determine urgency
    def get_urgency(days):
        if days <= 7:
            return "critical"
        elif days <= 30:
            return "warning"
        else:
            return "normal"
    
    # Get statute citations from rules
    prelim_notice = rules.get("preliminary_notice", {})
    lien_filing = rules.get("lien_filing", {})
    special_rules = rules.get("special_rules", {})
    statute_citations = []
    if prelim_notice.get("statute"):
        statute_citations.append(prelim_notice["statute"])
    if lien_filing.get("statute"):
        statute_citations.append(lien_filing["statute"])
    
    # Ensure state_name is always set
    state_name = rules.get("state_name") or state_code
    if state_name and len(state_name) == 2:
        state_name = STATE_CODE_TO_NAME.get(state_name, state_name)

    # Format dates for response
    prelim_deadline_str = prelim_deadline.strftime('%Y-%m-%d') if prelim_deadline else None
    lien_deadline_str = lien_deadline.strftime('%Y-%m-%d') if lien_deadline else None
    noi_deadline_str = result.get("notice_of_intent_deadline").strftime('%Y-%m-%d') if result.get("notice_of_intent_deadline") else None

    # Build response
    response = {
        "state": state_name,
        "state_code": state_code,
        "invoice_date": invoice_date,
        "role": role,
        "project_type": project_type,
        
        # Format 3: Nested Objects (likely the missing piece)
        "preliminary_notice": {
            "required": prelim_required,
            "deadline": prelim_deadline_str,
            "days": days_to_prelim,
            "days_from_now": days_to_prelim,
            "urgency": get_urgency(days_to_prelim) if days_to_prelim else None,
            "description": prelim_notice.get("description", prelim_notice.get("deadline_description", ""))
        },
        "lien_filing": {
            "deadline": lien_deadline_str,
            "days": days_to_lien,
            "days_from_now": days_to_lien,
            "urgency": get_urgency(days_to_lien) if days_to_lien else None,
            "description": lien_filing.get("description", lien_filing.get("deadline_description", ""))
        },
        # User explicitly requested "lien_deadline" as an object in Format 3
        "lien_deadline": {
            "deadline": lien_deadline_str,
            "days": days_to_lien
        },

        # Format 1: Top-level keys
        "preliminary_notice_deadline": prelim_deadline_str,
        "notice_of_intent_deadline": noi_deadline_str,
        
        # Format 2: Original "snake_case" keys (legacy)
        "prelim_deadline": prelim_deadline_str,
        
        "serving_requirements": rules.get("serving_requirements", []),
        "statute_citations": statute_citations,
        "warnings": warnings,
        "critical_warnings": warnings,  # Keep for backward compatibility
        "notes": special_rules.get("notes", ""),
        "disclaimer": "⚠️ This is general information only, NOT legal advice.",
        "response_time_ms": 45,
        "quota": quota
    }
    
    return response
