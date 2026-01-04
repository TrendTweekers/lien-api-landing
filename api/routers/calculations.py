from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
import sys

# We assume database imports are safe.
from api.database import get_db, get_db_cursor, DB_TYPE

logger = logging.getLogger(__name__)

# 🟢 CRITICAL CHANGE: No Prefix. We define full paths manually.
router = APIRouter(tags=["calculations"])

# --- Request Models ---
class CalculationRequest(BaseModel):
    state: str
    invoice_date: str
    project_type: Optional[str] = "Commercial"
    notice_date: Optional[str] = None

class SaveRequest(BaseModel):
    # Snake Case Fields (all Optional for permissive parsing)
    project_name: Optional[str] = None
    client_name: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    invoice_date: Optional[str] = None
    invoice_amount: Optional[float] = None
    prelim_deadline: Optional[str] = None
    prelim_deadline_days: Optional[int] = None
    lien_deadline: Optional[str] = None
    lien_deadline_days: Optional[int] = None
    notes: Optional[str] = None
    project_type: Optional[str] = None
    quickbooks_invoice_id: Optional[str] = None
    reminder_1day: Optional[bool] = False
    reminder_7days: Optional[bool] = False
    # Camel Case Aliases (for React frontend)
    projectName: Optional[str] = None
    clientName: Optional[str] = None
    stateCode: Optional[str] = None
    invoiceDate: Optional[str] = None
    invoiceAmount: Optional[float] = None
    prelimDeadline: Optional[str] = None
    prelimDeadlineDays: Optional[int] = None
    lienDeadline: Optional[str] = None
    lienDeadlineDays: Optional[int] = None
    projectType: Optional[str] = None
    quickbooksInvoiceId: Optional[str] = None
    reminder1day: Optional[bool] = False
    reminder7days: Optional[bool] = False
    # Nested reminders object (from frontend)
    reminders: Optional[dict] = None

# --- Helper Functions ---

def increment_api_calls(user_email: str):
    """
    Increment API calls for a user.
    Handles both PostgreSQL (UPSERT) and SQLite.
    """
    try:
        if user_email:
            user_email = user_email.lower().strip()
            
        logger.info(f"TRACKING: Incrementing API calls for {user_email}")
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                # Upsert for PostgreSQL
                cursor.execute("""
                    INSERT INTO customers (email, api_calls, status)
                    VALUES (%s, 1, 'active')
                    ON CONFLICT (email) 
                    DO UPDATE SET api_calls = customers.api_calls + 1
                """, (user_email,))
            else:
                # SQLite Upsert
                cursor.execute("""
                    INSERT INTO customers (email, api_calls, status)
                    VALUES (?, 1, 'active')
                    ON CONFLICT(email) 
                    DO UPDATE SET api_calls = api_calls + 1
                """, (user_email,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"TRACKING ERROR: Failed to increment for {user_email}: {e}")
        # Don't raise, just log - we don't want to fail the calculation
        return False

# --- Endpoints ---

@router.get("/api/v1/supported-states")
async def get_supported_states():
    """
    Get list of states that have legal logic implemented.
    Returns states from:
    1. STATE_RULES (state_rules.json) - includes states with ANY rules (preliminary OR lien filing)
    2. Database (lien_deadlines table) - states with ANY deadline rules
    3. Hardcoded calculation functions (TX, WA, CA, OH, OR, HI, NJ, IN, LA, MA)
    
    A state is considered supported if it has EITHER preliminary notice rules OR lien filing rules.
    This ensures states like Alaska (lien filing only) are included.
    """
    supported_states = set()
    
    try:
        # 1. Get states from STATE_RULES (loaded from state_rules.json)
        from api.calculators import STATE_RULES
        supported_states.update(STATE_RULES.keys())
    except Exception as e:
        logger.warning(f"Could not load STATE_RULES: {e}")
    
    try:
        # 2. Query database for states with ANY rules (preliminary OR lien filing)
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT DISTINCT state_code 
                    FROM lien_deadlines 
                    WHERE state_code IS NOT NULL 
                    AND (
                        preliminary_notice_days IS NOT NULL 
                        OR lien_filing_days IS NOT NULL
                    )
                """)
            else:
                cursor.execute("""
                    SELECT DISTINCT state_code 
                    FROM lien_deadlines 
                    WHERE state_code IS NOT NULL 
                    AND (
                        preliminary_notice_days IS NOT NULL 
                        OR lien_filing_days IS NOT NULL
                    )
                """)
            
            db_rows = cursor.fetchall()
            for row in db_rows:
                if isinstance(row, dict):
                    state_code = row.get('state_code')
                else:
                    state_code = row[0] if len(row) > 0 else None
                
                if state_code:
                    supported_states.add(state_code.upper())
    except Exception as e:
        logger.warning(f"Could not query database for supported states: {e}")
    
    # 3. Include states with hardcoded calculation functions
    # These are: TX, WA, CA, OH, OR, HI, NJ, IN, LA, MA
    hardcoded_states = {"TX", "WA", "CA", "OH", "OR", "HI", "NJ", "IN", "LA", "MA"}
    supported_states.update(hardcoded_states)
    
    # Convert to sorted list of state codes
    state_codes = sorted(list(supported_states))
    
    return JSONResponse(content={
        "status": "success",
        "states": state_codes,
        "count": len(state_codes)
    })

@router.get("/api/calculations/history")
async def get_history(request: Request):
    """
    Fetch history. Path matches current frontend: /api/calculations/history
    """
    # 🟢 LAZY IMPORT
    try:
        from api.routers.auth import get_user_from_session
    except ImportError:
        logger.error("CRITICAL: Could not import get_user_from_session from api.routers.auth")
        raise HTTPException(status_code=500, detail="Auth Config Error")

    # 1. Auth Check
    user = get_user_from_session(request)
    
    if not user:
        logger.warning("Auth failed - returning empty history to prevent frontend error")
        return JSONResponse(content={"history": []})

    # 2. Fetch History
    try:
        user_email = user.get("email", "")
        if not user_email:
            return JSONResponse(content={"history": []})
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Select with reminder columns (migration adds these columns on startup)
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    SELECT id, project_name, client_name, state, state_code, invoice_amount, 
                           invoice_date, prelim_deadline, prelim_deadline_days,
                           lien_deadline, lien_deadline_days, notes,
                           COALESCE(reminder_1day, true) as reminder_1day,
                           COALESCE(reminder_7days, false) as reminder_7days,
                           created_at
                    FROM calculations 
                    WHERE user_email = %s 
                    ORDER BY created_at DESC
                """, (user_email,))
            else:
                cursor.execute("""
                    SELECT id, project_name, client_name, state, state_code, invoice_amount,
                           invoice_date, prelim_deadline, prelim_deadline_days,
                           lien_deadline, lien_deadline_days, notes,
                           COALESCE(reminder_1day, 1) as reminder_1day,
                           COALESCE(reminder_7days, 0) as reminder_7days,
                           created_at
                    FROM calculations 
                    WHERE user_email = ? 
                    ORDER BY created_at DESC
                """, (user_email,))
            
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                if isinstance(row, dict):
                    # Extract reminder values (handle both boolean and int)
                    # CRITICAL: Default reminder_1day to True (1 Day enabled) if NULL
                    # Default reminder_7days to False (7 Days disabled) if NULL
                    reminder_1day_raw = row.get('reminder_1day')
                    reminder_7days_raw = row.get('reminder_7days')
                    
                    # Handle reminder_1day: default to True if NULL
                    if reminder_1day_raw is None:
                        reminder_1day = True  # Default to enabled (1 Day)
                    elif isinstance(reminder_1day_raw, bool):
                        reminder_1day = reminder_1day_raw
                    elif isinstance(reminder_1day_raw, int):
                        reminder_1day = bool(reminder_1day_raw)  # 1 = True, 0 = False
                    else:
                        reminder_1day = bool(reminder_1day_raw)
                    
                    # Handle reminder_7days: default to False if NULL
                    if reminder_7days_raw is None:
                        reminder_7days = False  # Default to disabled (7 Days)
                    elif isinstance(reminder_7days_raw, bool):
                        reminder_7days = reminder_7days_raw
                    elif isinstance(reminder_7days_raw, int):
                        reminder_7days = bool(reminder_7days_raw)  # 1 = True, 0 = False
                    else:
                        reminder_7days = bool(reminder_7days_raw)
                    
                    history.append({
                        "id": row.get('id'),
                        "project_name": row.get('project_name') or "",
                        "client_name": row.get('client_name') or "",
                        "state": row.get('state') or "",
                        "state_code": row.get('state_code') or "",
                        "amount": float(row.get('invoice_amount') or 0),
                        "invoice_date": str(row.get('invoice_date') or ""),
                        "prelim_deadline": str(row.get('prelim_deadline') or ""),
                        "prelim_deadline_days": row.get('prelim_deadline_days'),
                        "lien_deadline": str(row.get('lien_deadline') or ""),
                        "lien_deadline_days": row.get('lien_deadline_days'),
                        "notes": row.get('notes') or "",
                        "reminder_1day": reminder_1day,
                        "reminder_7days": reminder_7days,
                        "created_at": str(row.get('created_at') or "")
                    })
                else:
                    # Handle tuple/row format - reminder columns are at index 12, 13
                    # Default to True if NULL (matching new save behavior where reminders default to enabled)
                    if len(row) > 12:
                        reminder_1day = bool(row[12]) if row[12] is not None else True  # Default to True if NULL
                    else:
                        reminder_1day = True  # Default to enabled
                    
                    if len(row) > 13:
                        reminder_7days = bool(row[13]) if row[13] is not None else False  # Default to False if NULL
                    else:
                        reminder_7days = False  # Default to disabled (7 Days)
                    
                    history.append({
                        "id": row[0] if len(row) > 0 else None,
                        "project_name": row[1] if len(row) > 1 else "",
                        "client_name": row[2] if len(row) > 2 else "",
                        "state": row[3] if len(row) > 3 else "",
                        "state_code": row[4] if len(row) > 4 else "",
                        "amount": float(row[5]) if len(row) > 5 and row[5] else 0.0,
                        "invoice_date": str(row[6]) if len(row) > 6 else "",
                        "prelim_deadline": str(row[7]) if len(row) > 7 else "",
                        "prelim_deadline_days": row[8] if len(row) > 8 else None,
                        "lien_deadline": str(row[9]) if len(row) > 9 else "",
                        "lien_deadline_days": row[10] if len(row) > 10 else None,
                        "notes": row[11] if len(row) > 11 else "",
                        "reminder_1day": reminder_1day,
                        "reminder_7days": reminder_7days,
                        "created_at": str(row[14] if len(row) > 14 else row[-1] if len(row) > 0 else "")
                    })
            
            return JSONResponse(content={"history": history})
    except Exception as e:
        logger.error(f"History DB Error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"history": []})


@router.post("/api/v1/calculate-deadline")
async def track_calculation(request: Request, calc_req: CalculationRequest):
    """
    Calculates deadline. Path matches frontend: /api/v1/calculate-deadline
    """
    # 🟢 LAZY IMPORTS
    from api.routers.auth import get_user_from_session
    from api.calculators import calculate_state_deadline

    # 1. Auth & Quota
    user = get_user_from_session(request)
    quota_remaining = 3  # Public users get 3 calculations
    if user:
        quota_remaining = 9999  # Admins get integer (not "Unlimited" string) to prevent JS math errors

    # 2. Calculation
    try:
        inv_date = datetime.strptime(calc_req.invoice_date, "%Y-%m-%d")
        noc_date = None
        if calc_req.notice_date:
             noc_date = datetime.strptime(calc_req.notice_date, "%Y-%m-%d")

        # RUN MATH
        result = calculate_state_deadline(
            state_code=calc_req.state,
            invoice_date=inv_date,
            project_type=calc_req.project_type.lower() if calc_req.project_type else "commercial",
            notice_of_completion_date=noc_date
        )

        # Extract raw values (keep as datetime if datetime, date if date)
        raw_prelim = result.get("preliminary_deadline") or result.get("prelim_deadline")
        raw_lien = result.get("lien_deadline")
        warnings = result.get("warnings", [])

        # For MATH: Convert to date objects for subtraction
        prelim_date = raw_prelim.date() if isinstance(raw_prelim, datetime) else raw_prelim
        lien_date = raw_lien.date() if isinstance(raw_lien, datetime) else raw_lien

        # Calculate days remaining (using date objects)
        today = datetime.now().date()
        
        # 🔍 DEBUG: Log calculation details
        logger.info(f"CALC DEBUG: State={calc_req.state}, InvDate={inv_date}, Today={today}")
        if raw_prelim:
             logger.info(f"CALC DEBUG: RawPrelim={raw_prelim} (Type: {type(raw_prelim)})")
        if raw_lien:
             logger.info(f"CALC DEBUG: RawLien={raw_lien} (Type: {type(raw_lien)})")

        prelim_days = int((prelim_date - today).days) if prelim_date else None
        lien_days = int((lien_date - today).days) if lien_date else None
        
        logger.info(f"CALC DEBUG: PrelimDays={prelim_days}, LienDays={lien_days}")

        # For RESPONSE: Use simple YYYY-MM-DD format (CRITICAL for frontend compatibility)
        if raw_prelim:
            if isinstance(raw_prelim, datetime):
                prelim_deadline_str = raw_prelim.strftime("%Y-%m-%d")
            elif hasattr(raw_prelim, 'strftime'):
                prelim_deadline_str = raw_prelim.strftime("%Y-%m-%d")
            else:
                prelim_deadline_str = str(raw_prelim)
        else:
            prelim_deadline_str = None
            
        if raw_lien:
            if isinstance(raw_lien, datetime):
                lien_deadline_str = raw_lien.strftime("%Y-%m-%d")
            elif hasattr(raw_lien, 'strftime'):
                lien_deadline_str = raw_lien.strftime("%Y-%m-%d")
            else:
                lien_deadline_str = str(raw_lien)
        else:
            lien_deadline_str = None

        # 3. Construct response_data dictionary with ALL keys
        response_data = {
            # Echo fields from request
            "state": calc_req.state,
            "invoice_date": calc_req.invoice_date,
            "project_type": calc_req.project_type,
            # Quota
            "quota_remaining": quota_remaining,
            "quotaRemaining": quota_remaining,  # camelCase for React
            # Warnings
            "warnings": warnings,
            # Deadlines (snake_case)
            "preliminary_notice_deadline": prelim_deadline_str,
            "prelim_deadline": prelim_deadline_str,
            # Deadlines (camelCase)
            "preliminaryNoticeDeadline": prelim_deadline_str,
            "prelimDeadline": prelim_deadline_str,
            # Days remaining (snake_case) - Frontend expects these keys (matching SaveRequest model)
            "prelim_deadline_days": prelim_days,
            "lien_deadline_days": lien_days,
            "prelim_days_remaining": prelim_days,
            "preliminary_days_remaining": prelim_days,
            "days_until_prelim": prelim_days,
            "lien_days_remaining": lien_days,
            "days_remaining": lien_days,  # Fallback for the main deadline
            # Days remaining (camelCase) - for React frontend
            "prelimDeadlineDays": prelim_days,
            "lienDeadlineDays": lien_days,
            "prelimDaysRemaining": prelim_days,
            "lienDaysRemaining": lien_days,
            "daysRemaining": lien_days,  # camelCase fallback for the main deadline
            # Nested objects (for Dashboard compatibility) - Comprehensive keys
            "preliminary_notice": {
                "deadline": prelim_deadline_str,
                "required": True,
                "days_from_now": prelim_days,  # Critical: Frontend expects this field
                # snake_case keys (backward compatibility)
                "days_remaining": prelim_days,
                "deadline_days": prelim_days,
                "days_count": prelim_days,
                "days_diff": prelim_days,
                "days_until": prelim_days,
                "days": prelim_days,
                # camelCase keys for React frontend
                "daysRemaining": prelim_days,
                "deadlineDays": prelim_days,
                "daysCount": prelim_days,
                "daysDiff": prelim_days,
                "daysUntil": prelim_days
            },
            "lien_filing": {
                "deadline": lien_deadline_str,
                "days_from_now": lien_days,  # Critical: Frontend expects this field
                # snake_case keys (backward compatibility)
                "days_remaining": lien_days,
                "deadline_days": lien_days,
                "days_count": lien_days,
                "days_diff": lien_days,
                "days_until": lien_days,
                "days": lien_days,
                # camelCase keys for React frontend
                "daysRemaining": lien_days,
                "deadlineDays": lien_days,
                "daysCount": lien_days,
                "daysDiff": lien_days,
                "daysUntil": lien_days
            }
        }

        # 3.5. Increment Usage (api_calls)
        logger.info(f"TRACKING DEBUG: User object: {user}")
        if user and user.get('email'):
            increment_api_calls(user.get('email'))
        else:
            logger.warning("TRACKING DEBUG: No user or email found in session, skipping tracking")

        # 4. Return with "Triple Payload" strategy:
        # - Wrapped in "data" for frontend expecting a wrapper
        # - Wrapped in "result" for frontend expecting result wrapper
        # - Spread at root level for backward compatibility
        return JSONResponse(content={
            "status": "success",
            "data": response_data,  # <-- For frontend expecting a wrapper
            "result": response_data,  # <-- For frontend expecting result wrapper
            **response_data         # <-- For frontend expecting root keys (Fallback)
        })
    except Exception as e:
        logger.error(f"Calculation Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/api/calculations/save")
async def save_calculation(request: Request, body: SaveRequest):
    """Save a calculation to the database"""
    # 🟢 LAZY IMPORT
    from api.routers.auth import get_user_from_session
    from api.database import get_db
    
    # Log the raw payload for debugging
    print(f"📥 SAVE PAYLOAD RECEIVED: {body.dict()}")
    
    # 1. Auth Check
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    # 2. Map camelCase to snake_case (support both formats)
    p_name = body.project_name or body.projectName or ""
    c_name = body.client_name or body.clientName
    state_val = body.state or ""
    state_code_val = body.state_code or body.stateCode or state_val
    
    # CRITICAL: Ensure state_code is exactly 2 uppercase characters (fix TX -> RI issue)
    if state_code_val:
        # Remove any whitespace and take first 2 characters, then uppercase
        state_code_val = state_code_val.strip().upper()[:2]
    
    # Validate state_code is exactly 2 characters
    if not state_code_val or len(state_code_val) != 2:
        # Fallback: try to extract from state_val
        if state_val:
            state_code_val = state_val.strip().upper()[:2]
        else:
            state_code_val = "XX"  # Default fallback
    
    # Final validation - must be exactly 2 uppercase letters
    if len(state_code_val) != 2 or not state_code_val.isalpha():
        state_code_val = "XX"
    
    # Log for debugging
    print(f"💾 Save request - state_val: '{state_val}', state_code_val: '{state_code_val}'")
    inv_date = body.invoice_date or body.invoiceDate or ""
    inv_amount = body.invoice_amount or body.invoiceAmount
    prelim_dead = body.prelim_deadline or body.prelimDeadline
    prelim_days = body.prelim_deadline_days or body.prelimDeadlineDays
    lien_dead = body.lien_deadline or body.lienDeadline or ""
    lien_days = body.lien_deadline_days or body.lienDeadlineDays
    project_type_val = body.project_type or body.projectType or "commercial"
    quickbooks_invoice_id = body.quickbooks_invoice_id or getattr(body, 'quickbooksInvoiceId', None)
    
    # Extract reminder values from nested object or direct fields
    # CRITICAL: Default to reminder_1day=True (1 Day enabled), reminder_7days=True (7 Days enabled) - BOTH ON
    # These defaults ensure new saves always have both reminders enabled
    reminder_1day = True  # Default to enabled (1 Day) - only override if explicitly set
    reminder_7days = True  # Default to enabled (7 Days) - BOTH ON - only override if explicitly set
    
    if body.reminders:
        # Check if any prelim or lien reminder is checked for 1 day
        if body.reminders.get('prelim1') is not None or body.reminders.get('lien1') is not None:
            reminder_1day = bool(
                body.reminders.get('prelim1') or 
                body.reminders.get('lien1')
            )
        elif body.reminder_1day is not None or body.reminder1day is not None:
            # Only override default if explicitly provided (including False)
            reminder_1day = bool(body.reminder_1day if body.reminder_1day is not None else body.reminder1day)
        
        # Check if any prelim or lien reminder is checked for 7 days
        if body.reminders.get('prelim7') is not None or body.reminders.get('lien7') is not None:
            reminder_7days = bool(
                body.reminders.get('prelim7') or 
                body.reminders.get('lien7')
            )
        elif body.reminder_7days is not None or body.reminder7days is not None:
            # Only override default if explicitly provided (including False)
            reminder_7days = bool(body.reminder_7days if body.reminder_7days is not None else body.reminder7days)
    else:
        # Use direct fields if reminders object not provided
        # CRITICAL: Only override defaults if explicitly set (not None)
        # If field is missing (None), keep default True for reminder_1day
        if body.reminder_1day is not None:
            reminder_1day = bool(body.reminder_1day)
        elif body.reminder1day is not None:
            reminder_1day = bool(body.reminder1day)
        # reminder_1day stays True (default) if not provided
        
        if body.reminder_7days is not None:
            reminder_7days = bool(body.reminder_7days)
        elif body.reminder7days is not None:
            reminder_7days = bool(body.reminder7days)
        # reminder_7days stays True (default) if not provided
    
    # 3. Save to database
    try:
        import json
        from api.routers.auth import get_user_from_session
        
        # Get user email for the schema
        user_email = user.get("email", "")
        if not user_email:
            raise HTTPException(status_code=400, detail="User email not found")
        
        # Ensure required fields have defaults
        if not p_name:
            p_name = "Untitled Project"
        if not c_name:
            c_name = "Unknown Client"
        if not state_val:
            state_val = "Unknown"
        if not state_code_val or len(state_code_val) != 2:
            state_code_val = state_val[:2].upper() if len(state_val) >= 2 else "XX"
        if not inv_date:
            inv_date = datetime.now().strftime("%Y-%m-%d")
        if not lien_dead:
            lien_dead = inv_date  # Default to invoice date if not provided
        if not project_type_val:
            project_type_val = "commercial"
        # Normalize project_type to lowercase
        project_type_val = project_type_val.lower()
        
        # Log for debugging
        print(f"💾 Saving calculation: state_code={state_code_val}, project_type={project_type_val}, qb_invoice_id={quickbooks_invoice_id}")
        
        # Ensure lien_deadline_days is set (required by schema)
        if lien_days is None:
            if lien_dead:
                try:
                    lien_date = datetime.strptime(lien_dead, "%Y-%m-%d").date()
                    today = datetime.now().date()
                    lien_days = int((lien_date - today).days)
                except:
                    lien_days = 0
            else:
                lien_days = 0
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Ensure columns exist (migration) - CRITICAL for PostgreSQL compatibility
            try:
                if DB_TYPE == "postgresql":
                    # Check existing columns
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = 'calculations'
                    """)
                    existing_columns = [row[0] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
                    
                    # Add user_email if missing (required for save endpoint)
                    if 'user_email' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN user_email VARCHAR")
                        conn.commit()
                        print("✅ Added user_email column to calculations table")
                    
                    # Add other required columns if missing
                    if 'project_name' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN project_name VARCHAR")
                        conn.commit()
                        print("✅ Added project_name column to calculations table")
                    
                    if 'client_name' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN client_name VARCHAR")
                        conn.commit()
                        print("✅ Added client_name column to calculations table")
                    
                    if 'invoice_amount' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN invoice_amount DECIMAL(10,2)")
                        conn.commit()
                        print("✅ Added invoice_amount column to calculations table")
                    
                    if 'notes' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN notes TEXT")
                        conn.commit()
                        print("✅ Added notes column to calculations table")
                    
                    if 'state_code' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN state_code VARCHAR")
                        conn.commit()
                        print("✅ Added state_code column to calculations table")
                    
                    if 'invoice_date' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN invoice_date DATE")
                        conn.commit()
                        print("✅ Added invoice_date column to calculations table")
                    
                    if 'prelim_deadline' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN prelim_deadline DATE")
                        conn.commit()
                        print("✅ Added prelim_deadline column to calculations table")
                    
                    if 'prelim_deadline_days' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN prelim_deadline_days INTEGER")
                        conn.commit()
                        print("✅ Added prelim_deadline_days column to calculations table")
                    
                    if 'lien_deadline_days' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN lien_deadline_days INTEGER")
                        conn.commit()
                        print("✅ Added lien_deadline_days column to calculations table")
                    
                    if 'reminder_1day' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN reminder_1day BOOLEAN DEFAULT true")
                        conn.commit()
                        print("✅ Added reminder_1day column to calculations table")
                    
                    if 'reminder_7days' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN reminder_7days BOOLEAN DEFAULT true")
                        conn.commit()
                        print("✅ Added reminder_7days column to calculations table")
                    
                    # Check and add quickbooks_invoice_id column if missing
                    if 'quickbooks_invoice_id' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN quickbooks_invoice_id VARCHAR")
                        conn.commit()
                        print("✅ Added quickbooks_invoice_id column to calculations table")
                    
                    # Check and add project_type column if missing
                    if 'project_type' not in existing_columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN project_type VARCHAR DEFAULT 'commercial'")
                        conn.commit()
                        print("✅ Added project_type column to calculations table")
                else:
                    # SQLite: Check and add columns if missing
                    cursor.execute("PRAGMA table_info(calculations)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if 'user_email' not in columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN user_email TEXT")
                        print("✅ Added user_email column to calculations table")
                    if 'quickbooks_invoice_id' not in columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN quickbooks_invoice_id TEXT")
                        print("✅ Added quickbooks_invoice_id column to calculations table")
                    if 'project_type' not in columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN project_type TEXT DEFAULT 'commercial'")
                        print("✅ Added project_type column to calculations table")
                    if 'reminder_1day' not in columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN reminder_1day INTEGER DEFAULT 1")
                        print("✅ Added reminder_1day column to calculations table")
                    if 'reminder_7days' not in columns:
                        cursor.execute("ALTER TABLE calculations ADD COLUMN reminder_7days INTEGER DEFAULT 1")
                        print("✅ Added reminder_7days column to calculations table")
            except Exception as e:
                print(f"⚠️ Migration check error: {e}")
                import traceback
                traceback.print_exc()
                # Don't fail the save if migration has issues - try to continue
            
            # Insert with reminder columns and QuickBooks fields
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    INSERT INTO calculations (
                        user_email, project_name, client_name, invoice_amount, notes,
                        state, state_code, invoice_date, 
                        prelim_deadline, prelim_deadline_days,
                        lien_deadline, lien_deadline_days,
                        reminder_1day, reminder_7days,
                        quickbooks_invoice_id, project_type,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, (
                    user_email,
                    p_name,
                    c_name or "",
                    float(inv_amount) if inv_amount else None,
                    body.notes or "",
                    state_val or state_code_val,  # Use state_code_val if state_val is empty
                    state_code_val,  # CRITICAL: This MUST be the validated 2-char code (TX, not RI)
                    inv_date,
                    prelim_dead,
                    prelim_days,
                    lien_dead,
                    lien_days,
                    reminder_1day,  # Use calculated reminder_1day value
                    reminder_7days,  # Use calculated reminder_7days value (BOTH ON by default)
                    str(quickbooks_invoice_id) if quickbooks_invoice_id else None,
                    project_type_val,
                ))
                result = cursor.fetchone()
                if isinstance(result, dict):
                    calculation_id = result.get('id')
                else:
                    calculation_id = result[0] if result else None
            else:
                cursor.execute("""
                    INSERT INTO calculations (
                        user_email, project_name, client_name, invoice_amount, notes,
                        state, state_code, invoice_date,
                        prelim_deadline, prelim_deadline_days,
                        lien_deadline, lien_deadline_days,
                        reminder_1day, reminder_7days,
                        quickbooks_invoice_id, project_type,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    user_email,
                    p_name,
                    c_name or "",
                    float(inv_amount) if inv_amount else None,
                    body.notes or "",
                    state_val or state_code_val,  # Use state_code_val if state_val is empty
                    state_code_val,  # CRITICAL: This MUST be the validated 2-char code (TX, not RI)
                    inv_date,
                    prelim_dead,
                    prelim_days,
                    lien_dead,
                    lien_days,
                    reminder_1day,  # Use calculated reminder_1day value
                    reminder_7days,  # Use calculated reminder_7days value (BOTH ON by default)
                    str(quickbooks_invoice_id) if quickbooks_invoice_id else None,
                    project_type_val,
                ))
                conn.commit()
                calculation_id = cursor.lastrowid
            
            conn.commit()
            
            # Increment API usage
            increment_api_calls(user_email)
            
            return JSONResponse(content={
                "success": True,
                "id": calculation_id,
                "message": "Calculation saved successfully"
            })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Save calculation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save calculation: {str(e)}")

@router.delete("/api/calculations/{calculation_id}")
async def delete_calculation(calculation_id: int, request: Request):
    """Delete a calculation/project from the database"""
    # 🟢 LAZY IMPORT
    from api.routers.auth import get_user_from_session
    
    # 1. Auth Check
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user_email = user.get("email", "")
    if not user_email:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    # 2. Verify ownership and delete
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # First verify the calculation belongs to the user
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    SELECT id, quickbooks_invoice_id FROM calculations 
                    WHERE id = %s AND user_email = %s
                """, (calculation_id, user_email))
            else:
                cursor.execute("""
                    SELECT id, quickbooks_invoice_id FROM calculations 
                    WHERE id = ? AND user_email = ?
                """, (calculation_id, user_email))
            
            calc_row = cursor.fetchone()
            
            if not calc_row:
                raise HTTPException(status_code=404, detail="Calculation not found or unauthorized")
            
            # Extract quickbooks_invoice_id if it exists
            if isinstance(calc_row, dict):
                qb_invoice_id = calc_row.get('quickbooks_invoice_id')
            else:
                qb_invoice_id = calc_row[1] if len(calc_row) > 1 else None
            
            # Delete the calculation
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    DELETE FROM calculations 
                    WHERE id = %s AND user_email = %s
                """, (calculation_id, user_email))
            else:
                cursor.execute("""
                    DELETE FROM calculations 
                    WHERE id = ? AND user_email = ?
                """, (calculation_id, user_email))
            
            conn.commit()
            
            return JSONResponse(content={
                "success": True,
                "message": "Project deleted successfully",
                "quickbooks_invoice_id": qb_invoice_id  # Return QB ID so frontend can refresh invoices
            })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete calculation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete calculation: {str(e)}")

# Add legacy public endpoint just in case
@router.post("/api/calculate")
async def public_calculate_legacy(request: Request, calc_req: CalculationRequest):
    return await track_calculation(request, calc_req)

@router.get("/api/calculations/{calculation_id}/pdf")
async def generate_calculation_pdf(calculation_id: int, request: Request):
    """Generate PDF for a specific saved calculation"""
    from api.routers.auth import get_user_from_session
    from fastapi.responses import Response
    
    # Check if ReportLab is available
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
        from PIL import Image as PILImage
        import os
        from io import BytesIO
        REPORTLAB_AVAILABLE = True
    except ImportError:
        REPORTLAB_AVAILABLE = False
    
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation is temporarily unavailable. ReportLab library is not installed."
        )
    
    # Auth check
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user_email = user.get("email", "")
    
    # Fetch calculation from database
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    SELECT id, project_name, client_name, state, state_code, invoice_amount,
                           invoice_date, prelim_deadline, prelim_deadline_days,
                           lien_deadline, lien_deadline_days, notes, created_at, user_email
                    FROM calculations 
                    WHERE id = %s AND user_email = %s
                """, (calculation_id, user_email))
            else:
                cursor.execute("""
                    SELECT id, project_name, client_name, state, state_code, invoice_amount,
                           invoice_date, prelim_deadline, prelim_deadline_days,
                           lien_deadline, lien_deadline_days, notes, created_at, user_email
                    FROM calculations 
                    WHERE id = ? AND user_email = ?
                """, (calculation_id, user_email))
            
            calc_row = cursor.fetchone()
            
            if not calc_row:
                raise HTTPException(status_code=404, detail="Calculation not found")
            
            # Extract calculation data
            if isinstance(calc_row, dict):
                calc = {
                    'id': calc_row.get('id'),
                    'project_name': calc_row.get('project_name') or 'Untitled Project',
                    'client_name': calc_row.get('client_name') or 'Unknown Client',
                    'state': calc_row.get('state') or '',
                    'state_code': calc_row.get('state_code') or '',
                    'invoice_amount': calc_row.get('invoice_amount') or 0,
                    'invoice_date': calc_row.get('invoice_date') or '',
                    'prelim_deadline': calc_row.get('prelim_deadline') or '',
                    'prelim_deadline_days': calc_row.get('prelim_deadline_days'),
                    'lien_deadline': calc_row.get('lien_deadline') or '',
                    'lien_deadline_days': calc_row.get('lien_deadline_days') or 0,
                    'notes': calc_row.get('notes') or '',
                    'created_at': calc_row.get('created_at')
                }
            else:
                calc = {
                    'id': calc_row[0] if len(calc_row) > 0 else None,
                    'project_name': calc_row[1] if len(calc_row) > 1 else 'Untitled Project',
                    'client_name': calc_row[2] if len(calc_row) > 2 else 'Unknown Client',
                    'state': calc_row[3] if len(calc_row) > 3 else '',
                    'state_code': calc_row[4] if len(calc_row) > 4 else '',
                    'invoice_amount': calc_row[5] if len(calc_row) > 5 else 0,
                    'invoice_date': calc_row[6] if len(calc_row) > 6 else '',
                    'prelim_deadline': calc_row[7] if len(calc_row) > 7 else '',
                    'prelim_deadline_days': calc_row[8] if len(calc_row) > 8 else None,
                    'lien_deadline': calc_row[9] if len(calc_row) > 9 else '',
                    'lien_deadline_days': calc_row[10] if len(calc_row) > 10 else 0,
                    'notes': calc_row[11] if len(calc_row) > 11 else '',
                    'created_at': calc_row[12] if len(calc_row) > 12 else None
                }
            
            # Generate PDF
            buffer = BytesIO()
            
            # Get state name for footer
            state_name = calc.get('state') or calc.get('state_code') or 'the applicable state'
            
            # Footer function to add on every page
            def add_footer(canv, doc):
                canv.saveState()
                canv.setFont('Helvetica-Oblique', 8)
                canv.setFillColor(HexColor('#6b7280'))
                footer_text = f"Calculated based on {state_name} statutory requirements. This is not legal advice."
                # Position footer at bottom of page (accounting for margins)
                canv.drawString(0.75*inch, 0.5*inch, footer_text)
                canv.restoreState()
            
            doc = SimpleDocTemplate(buffer, pagesize=letter,
                                  rightMargin=0.75*inch, leftMargin=0.75*inch,
                                  topMargin=0.75*inch, bottomMargin=1*inch,  # Increased bottom margin for footer
                                  onFirstPage=add_footer,
                                  onLaterPages=add_footer)
            
            story = []
            styles = getSampleStyleSheet()
            navy = HexColor('#1e3a8a')
            coral = HexColor('#f97316')
            
            # Define urgency color function
            def get_urgency_color(days_remaining):
                """Get color based on days remaining until deadline"""
                if days_remaining is None:
                    return HexColor('#1f2937')  # Default gray
                if days_remaining < 0:
                    return HexColor('#dc2626')  # Red - overdue
                elif days_remaining < 7:
                    return HexColor('#dc2626')  # Red - urgent (< 7 days)
                elif days_remaining < 14:
                    return HexColor('#ea580c')  # Orange (7-14 days)
                elif days_remaining < 30:
                    return HexColor('#f59e0b')  # Yellow (14-30 days)
                else:
                    return HexColor('#16a34a')  # Green (≥ 30 days)
            
            # Calculate days remaining from today
            today = datetime.now().date()
            prelim_days_remaining = None
            lien_days_remaining = None
            
            if calc['prelim_deadline']:
                try:
                    if isinstance(calc['prelim_deadline'], str):
                        prelim_dt = datetime.strptime(calc['prelim_deadline'][:10], '%Y-%m-%d').date()
                    else:
                        prelim_dt = calc['prelim_deadline']
                    prelim_days_remaining = (prelim_dt - today).days
                except:
                    prelim_days_remaining = None
            
            if calc['lien_deadline']:
                try:
                    if isinstance(calc['lien_deadline'], str):
                        lien_dt = datetime.strptime(calc['lien_deadline'][:10], '%Y-%m-%d').date()
                    else:
                        lien_dt = calc['lien_deadline']
                    lien_days_remaining = (lien_dt - today).days
                except:
                    lien_days_remaining = None
            
            # Check if urgent warning needed (< 7 days)
            urgent_deadlines = []
            if prelim_days_remaining is not None and prelim_days_remaining < 7:
                urgent_deadlines.append(('Preliminary Notice', prelim_days_remaining))
            if lien_days_remaining is not None and lien_days_remaining < 7:
                urgent_deadlines.append(('Lien Filing', lien_days_remaining))
            
            # ===== PROFESSIONAL HEADER SECTION =====
            # Add LienDeadline logo
            # Calculate path: api/routers/calculations.py -> api/ -> project root -> images/liendeadline-logo.png
            current_dir = os.path.dirname(__file__)  # api/routers/
            api_dir = os.path.dirname(current_dir)  # api/
            project_root = os.path.dirname(api_dir)  # project root
            logo_path = os.path.join(project_root, 'images', 'liendeadline-logo.png')
            if os.path.exists(logo_path):
                try:
                    # Calculate aspect ratio to maintain proportions
                    img = PILImage.open(logo_path)
                    aspect = img.width / img.height
                    
                    # Set width, calculate height proportionally
                    logo_width = 2*inch
                    logo_height = logo_width / aspect
                    
                    logo = Image(logo_path, width=logo_width, height=logo_height)
                    logo.hAlign = 'CENTER'
                    story.append(logo)
                    story.append(Spacer(1, 0.28*inch))  # 20pt spacing between logo and header
                except Exception as e:
                    logger.warning(f"Could not load logo: {e}")
                    # Fallback to text header
                    header_text = f"<b>LienDeadline</b>"
                    header_style = ParagraphStyle(
                        'Header',
                        parent=styles['Normal'],
                        fontSize=18,
                        textColor=navy,
                        alignment=TA_CENTER,
                        fontName='Helvetica-Bold',
                        spaceAfter=6
                    )
                    story.append(Paragraph(header_text, header_style))
            else:
                # Fallback to text header if logo not found
                header_text = f"<b>LienDeadline</b>"
                header_style = ParagraphStyle(
                    'Header',
                    parent=styles['Normal'],
                    fontSize=18,
                    textColor=navy,
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold',
                    spaceAfter=6
                )
                story.append(Paragraph(header_text, header_style))
            
            # ===== URGENT WARNING BOX =====
            if urgent_deadlines:
                min_days = min(days for name, days in urgent_deadlines)
                warning_text = f"⚠️ <b>URGENT:</b> Deadline approaching in {min_days} day{'s' if min_days != 1 else ''}"
                if min_days < 0:
                    warning_text = f"⚠️ <b>OVERDUE:</b> Deadline has passed ({abs(min_days)} day{'s' if abs(min_days) != 1 else ''} ago)"
                
                warning_style = ParagraphStyle(
                    'Warning',
                    parent=styles['Normal'],
                    fontSize=12,
                    textColor=HexColor('#ffffff'),
                    alignment=TA_CENTER,
                    fontName='Helvetica-Bold',
                    spaceAfter=12,
                    spaceBefore=12
                )
                warning_para = Paragraph(warning_text, warning_style)
                
                # Create warning box with red background
                warning_table = Table([[warning_para]], colWidths=[5.5*inch])
                warning_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), HexColor('#dc2626')),
                    ('BOX', (0, 0), (-1, -1), 2, HexColor('#991b1b')),
                    ('PADDING', (0, 0), (-1, -1), 14),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                story.append(warning_table)
                story.append(Spacer(1, 0.3*inch))
            
            # Title - Left-aligned
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Heading1'],
                fontSize=24,
                textColor=navy,
                spaceAfter=12,
                alignment=TA_LEFT,
                fontName='Helvetica-Bold'
            )
            story.append(Paragraph("Lien Deadline Report", title_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Project Information - Left-aligned
            heading_style = ParagraphStyle(
                'Heading',
                parent=styles['Heading2'],
                fontSize=16,
                textColor=navy,
                spaceAfter=8,
                spaceBefore=12,
                alignment=TA_LEFT,
                fontName='Helvetica-Bold'
            )
            
            story.append(Paragraph("Project Information", heading_style))
            
            # Format dates
            def format_date(date_str):
                if not date_str:
                    return 'N/A'
                try:
                    if isinstance(date_str, str):
                        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
                    else:
                        dt = date_str
                    return dt.strftime('%B %d, %Y')
                except:
                    return str(date_str)
            
            # Create info table
            info_data = [
                ['Project Name:', calc['project_name']],
                ['Client Name:', calc['client_name']],
                ['State:', calc['state'] or calc['state_code']],
                ['Invoice Date:', format_date(calc['invoice_date'])],
                ['Invoice Amount:', f"${float(calc['invoice_amount']):,.2f}" if calc['invoice_amount'] else 'N/A'],
            ]
            
            if calc['notes']:
                info_data.append(['Notes:', calc['notes']])
            
            info_table = Table(info_data, colWidths=[2.5*inch, 3.5*inch])
            info_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), HexColor('#f97316')),  # Brand orange for header column
                ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#ffffff')),  # White text on orange
                ('TEXTCOLOR', (1, 0), (1, -1), HexColor('#1f2937')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb'))
            ]))
            story.append(info_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Deadline Information - Left-aligned
            story.append(Paragraph("Deadline Information", heading_style))
            
            deadline_data = []
            deadline_table_style = [
                ('BACKGROUND', (0, 0), (0, -1), HexColor('#f97316')),  # Brand orange for header column
                ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#ffffff')),  # White text on orange
                ('TEXTCOLOR', (1, 0), (1, -1), HexColor('#1f2937')),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTNAME', (2, 0), (2, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb')),
            ]
            
            row_idx = 0
            
            if calc['prelim_deadline']:
                deadline_date = format_date(calc['prelim_deadline'])
                if prelim_days_remaining is not None:
                    if prelim_days_remaining < 0:
                        days_text = f"OVERDUE ({abs(prelim_days_remaining)} days)"
                    else:
                        days_text = f"{prelim_days_remaining} days remaining"
                    prelim_color = get_urgency_color(prelim_days_remaining)
                    deadline_data.append(['Preliminary Notice Deadline:', deadline_date, days_text])
                    deadline_table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), prelim_color))
                    deadline_table_style.append(('FONTNAME', (2, row_idx), (2, row_idx), 'Helvetica-Bold'))
                else:
                    deadline_data.append(['Preliminary Notice Deadline:', deadline_date, 'N/A'])
                row_idx += 1
            else:
                deadline_data.append(['Preliminary Notice Deadline:', 'Not Required', ''])
                row_idx += 1
            
            if calc['lien_deadline']:
                deadline_date = format_date(calc['lien_deadline'])
                if lien_days_remaining is not None:
                    if lien_days_remaining < 0:
                        days_text = f"OVERDUE ({abs(lien_days_remaining)} days)"
                    else:
                        days_text = f"{lien_days_remaining} days remaining"
                    lien_color = get_urgency_color(lien_days_remaining)
                    deadline_data.append(['Lien Filing Deadline:', deadline_date, days_text])
                    deadline_table_style.append(('TEXTCOLOR', (2, row_idx), (2, row_idx), lien_color))
                    deadline_table_style.append(('FONTNAME', (2, row_idx), (2, row_idx), 'Helvetica-Bold'))
                else:
                    deadline_data.append(['Lien Filing Deadline:', deadline_date, 'N/A'])
                row_idx += 1
            else:
                deadline_data.append(['Lien Filing Deadline:', 'N/A', ''])
            
            deadline_table = Table(deadline_data, colWidths=[2.5*inch, 2.2*inch, 1.3*inch])
            deadline_table.setStyle(TableStyle(deadline_table_style))
            story.append(deadline_table)
            story.append(Spacer(1, 0.3*inch))
            
            # ===== FOOTER SECTION =====
            gen_date_footer = datetime.now().strftime('%B %d, %Y')
            footer_text = f"Generated {gen_date_footer} | liendeadline.com | Not Legal Advice"
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=HexColor('#9ca3af'),
                alignment=TA_CENTER,
                spaceAfter=4
            )
            story.append(Paragraph(footer_text, footer_style))
            
            # Disclaimer
            disclaimer_text = """
            <b>DISCLAIMER</b><br/>
            This is general information only, NOT legal advice. Always consult a licensed construction 
            attorney before taking any legal action. Deadlines vary based on project specifics, and this 
            tool cannot account for all variables. LienDeadline assumes no liability for missed deadlines 
            or legal consequences.
            """
            
            disclaimer_style = ParagraphStyle(
                'Disclaimer',
                parent=styles['Normal'],
                fontSize=9,
                textColor=HexColor('#6b7280'),
                alignment=TA_LEFT,
                leftIndent=0,
                rightIndent=0,
                spaceAfter=8
            )
            disclaimer = Paragraph(disclaimer_text, disclaimer_style)
            
            # Create disclaimer box with border
            disclaimer_table = Table([[disclaimer]], colWidths=[5.5*inch])
            disclaimer_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f3f4f6')),
                ('BOX', (0, 0), (-1, -1), 1, HexColor('#d1d5db')),
                ('PADDING', (0, 0), (-1, -1), 12),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(disclaimer_table)
            
            # Add test credentials at the end
            story.append(Spacer(1, 0.4*inch))
            
            credentials_style = ParagraphStyle(
                'Credentials',
                parent=styles['Normal'],
                fontSize=11,
                textColor=HexColor('#1f2937'),
                alignment=TA_LEFT,
                fontName='Helvetica-Bold',
                spaceAfter=4
            )
            
            credentials_text = """
            <b>Test Login Credentials:</b><br/>
            Email: reviewer@liendeadline.com<br/>
            Password: IntuitReview2026!
            """
            
            credentials_para = Paragraph(credentials_text, credentials_style)
            
            # Create credentials box
            credentials_table = Table([[credentials_para]], colWidths=[5.5*inch])
            credentials_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), HexColor('#fff7ed')),  # Light orange background
                ('BOX', (0, 0), (-1, -1), 1, HexColor('#f97316')),  # Orange border
                ('PADDING', (0, 0), (-1, -1), 12),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            
            story.append(credentials_table)
            
            # Build PDF
            doc.build(story)
            buffer.seek(0)
            
            # Return PDF response
            return Response(
                content=buffer.read(),
                media_type='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename="lien-deadline-{calculation_id}.pdf"'
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating calculation PDF: {e}")
        import traceback
        traceback.print_exc()
