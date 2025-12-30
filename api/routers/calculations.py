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
    project_name: str
    client_name: Optional[str] = None
    state: str
    state_code: Optional[str] = None
    invoice_date: str
    invoice_amount: Optional[float] = None
    prelim_deadline: Optional[str] = None
    prelim_deadline_days: Optional[int] = None
    lien_deadline: str
    lien_deadline_days: int
    notes: Optional[str] = None
    project_type: Optional[str] = None

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
        if DB_TYPE == "postgresql":
            with get_db_cursor() as cur:
                # Ensure your table/column names match your schema
                cur.execute("""
                    SELECT id, project_name, state, amount, created_at, result 
                    FROM calculations 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                """, (user.get("id"),))
                rows = cur.fetchall()
                
                history = []
                for row in rows:
                    history.append({
                        "id": row[0],
                        "project_name": row[1],
                        "state": row[2],
                        "amount": float(row[3]) if row[3] else 0.0,
                        "created_at": str(row[4]),
                        "result": row[5]
                    })
                return JSONResponse(content={"history": history})
        return JSONResponse(content={"history": []})
    except Exception as e:
        logger.error(f"History DB Error: {e}")
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

        # 4. Return with "Double Payload" strategy:
        # - Wrapped in "data" for frontend expecting a wrapper
        # - Spread at root level for backward compatibility
        return JSONResponse(content={
            "status": "success",
            "data": response_data,  # <-- For frontend expecting a wrapper
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
    
    # 1. Auth Check
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    user_id = user.get("id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user")
    
    # 2. Save to database
    try:
        import json
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Prepare result JSON (store calculation data)
            result_data = {
                "state": body.state,
                "state_code": body.state_code or body.state,
                "invoice_date": body.invoice_date,
                "prelim_deadline": body.prelim_deadline,
                "lien_deadline": body.lien_deadline,
                "prelim_deadline_days": body.prelim_deadline_days,
                "lien_deadline_days": body.lien_deadline_days,
                "project_type": body.project_type
            }
            
            if DB_TYPE == "postgresql":
                cursor.execute("""
                    INSERT INTO calculations (
                        user_id, project_name, client_name, state, amount,
                        invoice_date, prelim_deadline, lien_deadline, result, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id
                """, (
                    user_id,
                    body.project_name,
                    body.client_name,
                    body.state,
                    body.invoice_amount,
                    body.invoice_date,
                    body.prelim_deadline,
                    body.lien_deadline,
                    json.dumps(result_data)
                ))
                calculation_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    INSERT INTO calculations (
                        user_id, project_name, client_name, state, amount,
                        invoice_date, prelim_deadline, lien_deadline, result, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    user_id,
                    body.project_name,
                    body.client_name,
                    body.state,
                    body.invoice_amount,
                    body.invoice_date,
                    body.prelim_deadline,
                    body.lien_deadline,
                    json.dumps(result_data)
                ))
                calculation_id = cursor.lastrowid
            
            conn.commit()
            
            return JSONResponse(content={
                "success": True,
                "id": calculation_id,
                "message": "Calculation saved successfully"
            })
    except Exception as e:
        logger.error(f"Save calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save calculation: {str(e)}")

# Add legacy public endpoint just in case
@router.post("/api/calculate")
async def public_calculate_legacy(request: Request, calc_req: CalculationRequest):
    return await track_calculation(request, calc_req)