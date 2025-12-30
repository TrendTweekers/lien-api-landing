import os
import sys
import logging
from typing import Optional, Any
from datetime import datetime

# -------------------------------------------------------------------------
# 🦄 STARTUP DIAGNOSTICS (Prints file structure to logs)
# -------------------------------------------------------------------------
logger = logging.getLogger(__name__)
print("🦄 RELOADING CALCULATIONS ROUTER - VERSION SELF-HEALING")

try:
    print(f"📂 CONTENTS of 'api': {os.listdir('api')}")
    if os.path.exists('api/routers'):
        print(f"📂 CONTENTS of 'api/routers': {os.listdir('api/routers')}")
except Exception as e:
    print(f"⚠️ Could not list directories: {e}")

# -------------------------------------------------------------------------
# 🧩 DYNAMIC IMPORTS (Finds Auth where it lives)
# -------------------------------------------------------------------------
get_user_from_session = None
get_current_user = None

# Attempt 1: Try api.auth
try:
    from api.auth import get_user_from_session as gufs, get_current_user as gcu
    get_user_from_session = gufs
    get_current_user = gcu
    print("✅ Found Auth in: api.auth")
except ImportError:
    print("⚠️ Could not import from api.auth")

# Attempt 2: Try api.routers.auth (fallback)
if not get_user_from_session:
    try:
        from api.routers.auth import get_user_from_session as gufs, get_current_user as gcu
        get_user_from_session = gufs
        get_current_user = gcu
        print("✅ Found Auth in: api.routers.auth")
    except ImportError:
        print("⚠️ Could not import from api.routers.auth")

# Fallback: Define Mock functions if Auth is completely missing
# (This ensures the server STARTS so we can see logs)
if not get_user_from_session:
    print("❌ AUTH NOT FOUND - Using Mock Functions to prevent crash")
    def get_user_from_session(request):
        return None
    def get_current_user():
        return None

# -------------------------------------------------------------------------
# 🧱 MAIN ROUTER CODE
# -------------------------------------------------------------------------
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from api.database import get_db_cursor, DB_TYPE

# Try importing calculator logic, or mock it if missing
try:
    from api.calculators import calculate_deadlines_for_state
except ImportError:
    print("⚠️ api.calculators not found. Using Mock Calculator.")
    def calculate_deadlines_for_state(**kwargs):
        return {"prelim_deadline": None, "lien_deadline": None}

router = APIRouter(prefix="/api/calculations", tags=["calculations"])

class CalculationRequest(BaseModel):
    state: str
    invoice_date: str
    project_type: Optional[str] = "Commercial"
    notice_date: Optional[str] = None

@router.get("/history")
async def get_history(request: Request):
    print("🔍 DEBUG: /history called")
    
    # 1. Try Session Auth
    user = get_user_from_session(request)
    print(f"🔍 DEBUG: Session User: {user.get('email') if user else 'None'}")

    if not user:
        # 2. Try Token Auth (Manual Header Check)
        auth_header = request.headers.get("Authorization")
        print(f"🔍 DEBUG: Auth Header: {auth_header}")
        # Note: If you need strict token validation, integrate it here.
        # For Dashboard access, we prioritize Session.

    if not user:
        print("❌ DEBUG: Auth Failed. Raising 401.")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Return empty list for debug (Confirms Auth worked)
    return JSONResponse(content={"history": []})

@router.post("/v1/calculate-deadline")
async def track_calculation(request: Request, calc_req: CalculationRequest):
    print(f"🔍 DEBUG: /calculate-deadline called for {calc_req.state}")
    
    user = get_user_from_session(request)
    quota_remaining = 3
    if user:
        quota_remaining = "Unlimited"
        print(f"✅ DEBUG: User {user.get('email')} - Quota Unlimited")
    
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
        
        # LOG RESULTS
        print(f"🔍 DEBUG: Math Result: {result}")

        prelim_deadline = result.get("prelim_deadline")
        lien_deadline = result.get("lien_deadline")
        
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
        return JSONResponse(status_code=500, content={"error": str(e)})