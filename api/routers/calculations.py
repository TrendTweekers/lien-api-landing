from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import logging
import json

from api.database import get_db_cursor, DB_TYPE
from api.auth import get_user_from_session
# Ensure this matches your file structure exactly
from api.calculators import calculate_deadlines_for_state 

# Configure Logging
logger = logging.getLogger(__name__)

# 🦄 MARKER: If you don't see this in logs, the file didn't update!
print("🦄 RELOADING CALCULATIONS ROUTER - VERSION X-RAY")

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
    print("🔍 DEBUG: /history called")
    
    # 1. Try Session Auth
    user = get_user_from_session(request)
    print(f"🔍 DEBUG: Session User: {user.get('email') if user else 'None'}")

    # 2. Try Token Auth (Fallback)
    if not user:
        auth_header = request.headers.get("Authorization")
        print(f"🔍 DEBUG: Auth Header: {auth_header}")
        # (Add token verification logic here if you strictly need it, 
        # but for Dashboard, Session should have worked)

    if not user:
        print("❌ DEBUG: Auth Failed. Raising 401.")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Fetch History logic...
    # (Simplified for debug - just return empty list to prove auth works)
    return JSONResponse(content={"history": []})


@router.post("/v1/calculate-deadline")
async def track_calculation(request: Request, calc_req: CalculationRequest):
    print(f"🔍 DEBUG: /calculate-deadline called for {calc_req.state}")
    
    # 1. Auth & Quota
    user = get_user_from_session(request)
    quota_remaining = 3
    if user:
        quota_remaining = "Unlimited"
        print(f"✅ DEBUG: User {user.get('email')} - Quota Unlimited")
    
    # 2. PERFORM CALCULATION
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
        
        # 🔍 DEBUG: PRINT THE EXACT RESULT FROM THE MATH FUNCTION
        print(f"🔍 DEBUG: Math Result Keys: {result.keys()}")
        print(f"🔍 DEBUG: Prelim Deadline: {result.get('prelim_deadline')}")

        # Extract
        prelim_deadline = result.get("prelim_deadline")
        lien_deadline = result.get("lien_deadline")
        
        # 3. CONSTRUCT RESPONSE
        response_payload = {
            "status": "success",
            "quota_remaining": quota_remaining,
            
            # Universal Keys
            "preliminary_notice_deadline": str(prelim_deadline) if prelim_deadline else None,
            "prelim_deadline": str(prelim_deadline) if prelim_deadline else None,
            
            # Nested Objects
            "preliminary_notice": {
                "deadline": str(prelim_deadline) if prelim_deadline else None,
                "required": True,
                "days_remaining": (prelim_deadline - datetime.now().date()).days if prelim_deadline else 0
            },
            "lien_filing": {
                "deadline": str(lien_deadline) if lien_deadline else None,
                 # Just to be safe, adding lien_deadline key too
                "lien_deadline": str(lien_deadline) if lien_deadline else None,
                "days_remaining": (lien_deadline - datetime.now().date()).days if lien_deadline else 0
            }
        }
        
        print("✅ DEBUG: Sending Response")
        return JSONResponse(content=response_payload)

    except Exception as e:
        logger.error(f"Calculation Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})