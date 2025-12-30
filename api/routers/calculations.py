from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging

# We assume database imports are safe. If not, move them inside too.
from api.database import get_db_cursor, DB_TYPE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/calculations", tags=["calculations"])

# --- Request Models ---
class CalculationRequest(BaseModel):
    state: str
    invoice_date: str
    project_type: Optional[str] = "Commercial"
    notice_date: Optional[str] = None

# --- Endpoints ---

@router.get("/history")
async def get_history(request: Request):
    """
    Fetch history. Uses Lazy Import to avoid circular dependencies.
    """
    try:
        # 🟢 LAZY IMPORT: Fixes 'Could not import from api.routers.auth'
        from api.routers.auth import get_user_from_session
    except ImportError as e:
        logger.error(f"CRITICAL: Auth Import Failed: {e}")
        raise HTTPException(status_code=500, detail="Server Auth Config Error")

    # 1. Auth Check
    user = get_user_from_session(request)
    
    # Fallback to Header if Session is missing
    if not user:
        auth_header = request.headers.get("Authorization")
        if auth_header: 
            pass # (Add manual token logic here if needed)

    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # 2. Fetch History
    try:
        if DB_TYPE == "postgresql":
            with get_db_cursor() as cur:
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


@router.post("/v1/calculate-deadline")
async def track_calculation(request: Request, calc_req: CalculationRequest):
    """
    Calculates deadline. Uses Lazy Import to avoid startup crashes.
    """
    # 🟢 LAZY IMPORTS
    from api.routers.auth import get_user_from_session
    from api.calculators import calculate_deadlines_for_state

    # 1. Auth
    user = get_user_from_session(request)
    quota_remaining = 3
    if user:
        quota_remaining = "Unlimited"

    # 2. Calculation
    try:
        inv_date = datetime.strptime(calc_req.invoice_date, "%Y-%m-%d").date()
        noc_date = None
        if calc_req.notice_date:
             noc_date = datetime.strptime(calc_req.notice_date, "%Y-%m-%d").date()

        # RUN MATH
        result = calculate_deadlines_for_state(
            state=calc_req.state,
            invoice_date=inv_date,
            project_type=calc_req.project_type,
            notice_of_completion_date=noc_date
        )

        prelim_deadline = result.get("prelim_deadline")
        lien_deadline = result.get("lien_deadline")

        # 3. Response
        return JSONResponse(content={
            "status": "success",
            "quota_remaining": quota_remaining,
            "preliminary_notice_deadline": str(prelim_deadline) if prelim_deadline else None,
            "prelim_deadline": str(prelim_deadline) if prelim_deadline else None,
            "preliminary_notice": {
                "deadline": str(prelim_deadline) if prelim_deadline else None,
                "required": True,
                "days_remaining": (prelim_deadline - datetime.now().date()).days if prelim_deadline else 0
            },
            "lien_filing": {
                "deadline": str(lien_deadline) if lien_deadline else None,
                "days_remaining": (lien_deadline - datetime.now().date()).days if lien_deadline else 0
            }
        })
    except Exception as e:
        logger.error(f"Calculation Error: {e}")
        # Return a clean error so we see it in frontend console
        return JSONResponse(status_code=500, content={"error": str(e)})