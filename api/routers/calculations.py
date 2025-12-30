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
    print(f"🔍 DEBUG: /api/calculations/history hit!")
    
    # 🟢 LAZY IMPORT
    try:
        from api.routers.auth import get_user_from_session
    except ImportError:
        print("❌ CRITICAL: Could not import get_user_from_session from api.routers.auth")
        raise HTTPException(status_code=500, detail="Auth Config Error")

    # 1. Auth Check (Debug Logs included)
    user = get_user_from_session(request)
    print(f"🔍 DEBUG: Session User: {user.get('email') if user else 'None'}")
    
    if not user:
        # Check raw cookies to debug 401
        print(f"🔍 DEBUG: Cookies present: {request.cookies.keys()}")
        raise HTTPException(status_code=401, detail="Unauthorized")

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
    print(f"🔍 DEBUG: /api/v1/calculate-deadline hit for state: {calc_req.state}")

    # 🟢 LAZY IMPORTS
    from api.routers.auth import get_user_from_session
    from api.calculators import calculate_state_deadline

    # 1. Auth & Quota
    user = get_user_from_session(request)
    quota_remaining = 3
    if user:
        quota_remaining = "Unlimited"
        print(f"✅ DEBUG: User {user.get('email')} detected.")

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
        print(f"🔍 DEBUG: Math Result: {result}")

        # Extract and ensure we work with .date() objects
        raw_prelim = result.get("preliminary_deadline") or result.get("prelim_deadline")
        raw_lien = result.get("lien_deadline")

        # Convert datetime to date if needed
        prelim_deadline = raw_prelim.date() if isinstance(raw_prelim, datetime) else raw_prelim
        lien_deadline = raw_lien.date() if isinstance(raw_lien, datetime) else raw_lien

        # Calculate days remaining (both must be date objects)
        today = datetime.now().date()
        prelim_days = (prelim_deadline - today).days if prelim_deadline else 0
        lien_days = (lien_deadline - today).days if lien_deadline else 0

        # 3. Response (Universal Format)
        return JSONResponse(content={
            "status": "success",
            "quota_remaining": quota_remaining,
            "preliminary_notice_deadline": str(prelim_deadline) if prelim_deadline else None,
            "prelim_deadline": str(prelim_deadline) if prelim_deadline else None,
            "preliminary_notice": {
                "deadline": str(prelim_deadline) if prelim_deadline else None,
                "required": True,
                "days_remaining": prelim_days
            },
            "lien_filing": {
                "deadline": str(lien_deadline) if lien_deadline else None,
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