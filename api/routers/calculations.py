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

# --- Endpoints ---

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
            
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    SELECT id, project_name, client_name, state, state_code, invoice_amount, 
                           invoice_date, prelim_deadline, prelim_deadline_days,
                           lien_deadline, lien_deadline_days, notes, created_at
                    FROM calculations 
                    WHERE user_email = %s 
                    ORDER BY created_at DESC
                """, (user_email,))
            else:
                cursor.execute("""
                    SELECT id, project_name, client_name, state, state_code, invoice_amount,
                           invoice_date, prelim_deadline, prelim_deadline_days,
                           lien_deadline, lien_deadline_days, notes, created_at
                    FROM calculations 
                    WHERE user_email = ? 
                    ORDER BY created_at DESC
                """, (user_email,))
            
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                if isinstance(row, dict):
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
                        "created_at": str(row.get('created_at') or "")
                    })
                else:
                    # Handle tuple/row format
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
                        "created_at": str(row[12]) if len(row) > 12 else ""
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
        prelim_days = int((prelim_date - today).days) if prelim_date else 0
        lien_days = int((lien_date - today).days) if lien_date else 0

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
    inv_date = body.invoice_date or body.invoiceDate or ""
    inv_amount = body.invoice_amount or body.invoiceAmount
    prelim_dead = body.prelim_deadline or body.prelimDeadline
    prelim_days = body.prelim_deadline_days or body.prelimDeadlineDays
    lien_dead = body.lien_deadline or body.lienDeadline or ""
    lien_days = body.lien_deadline_days or body.lienDeadlineDays
    project_type_val = body.project_type or body.projectType
    
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
        if not state_code_val:
            state_code_val = state_val[:2].upper() if len(state_val) >= 2 else "XX"
        if not inv_date:
            inv_date = datetime.now().strftime("%Y-%m-%d")
        if not lien_dead:
            lien_dead = inv_date  # Default to invoice date if not provided
        
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
            
            # Use the migration schema: user_email, project_name, client_name, invoice_amount, notes,
            # state, state_code, invoice_date, prelim_deadline, prelim_deadline_days, lien_deadline, lien_deadline_days
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    INSERT INTO calculations (
                        user_email, project_name, client_name, invoice_amount, notes,
                        state, state_code, invoice_date, 
                        prelim_deadline, prelim_deadline_days,
                        lien_deadline, lien_deadline_days,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, (
                    user_email,
                    p_name,
                    c_name or "",
                    float(inv_amount) if inv_amount else None,
                    body.notes or "",
                    state_val,
                    state_code_val,
                    inv_date,
                    prelim_dead,
                    prelim_days,
                    lien_dead,
                    lien_days,
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
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    user_email,
                    p_name,
                    c_name or "",
                    float(inv_amount) if inv_amount else None,
                    body.notes or "",
                    state_val,
                    state_code_val,
                    inv_date,
                    prelim_dead,
                    prelim_days,
                    lien_dead,
                    lien_days,
                ))
                calculation_id = cursor.lastrowid
            
            conn.commit()
            
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

# Add legacy public endpoint just in case
@router.post("/api/calculate")
async def public_calculate_legacy(request: Request, calc_req: CalculationRequest):
    return await track_calculation(request, calc_req)