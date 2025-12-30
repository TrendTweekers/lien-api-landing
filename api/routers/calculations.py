from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
import sys

# We assume database imports are safe.
from api.database import get_db_cursor, DB_TYPE

logger = logging.getLogger(__name__)

# 🟢 CRITICAL CHANGE: No Prefix. We define full paths manually.
router = APIRouter(tags=["calculations"])

# --- Request Models ---
class CalculationRequest(BaseModel):
    state: str
    invoice_date: str
    project_type: Optional[str] = "Commercial"
    notice_date: Optional[str] = None

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
    quota_remaining = 3
    if user:
        quota_remaining = "Unlimited"

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
        prelim_days = (prelim_date - today).days if prelim_date else 0
        lien_days = (lien_date - today).days if lien_date else 0

        # For RESPONSE: Use ISO format to preserve time component
        prelim_deadline_str = raw_prelim.isoformat() if raw_prelim else None
        lien_deadline_str = raw_lien.isoformat() if raw_lien else None

        # 3. Response (Universal Format)
        return JSONResponse(content={
            "status": "success",
            "quota_remaining": quota_remaining,
            "warnings": warnings,
            "preliminary_notice_deadline": prelim_deadline_str,
            "prelim_deadline": prelim_deadline_str,
            # Shotgun approach: Multiple variations of days remaining keys
            "prelim_days_remaining": prelim_days,
            "preliminary_days_remaining": prelim_days,
            "days_until_prelim": prelim_days,
            "lien_days_remaining": lien_days,
            "days_remaining": lien_days,  # Fallback for the main deadline
            # Nested objects (for Dashboard compatibility)
            "preliminary_notice": {
                "deadline": prelim_deadline_str,
                "required": True,
                "days_remaining": prelim_days,
                "days_until": prelim_days,
                "days": prelim_days
            },
            "lien_filing": {
                "deadline": lien_deadline_str,
                "days_remaining": lien_days
            }
        })
    except Exception as e:
        logger.error(f"Calculation Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Add legacy public endpoint just in case
@router.post("/api/calculate")
async def public_calculate_legacy(request: Request, calc_req: CalculationRequest):
    return await track_calculation(request, calc_req)