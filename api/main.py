from fastapi import FastAPI, Request, Header, HTTPException, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime, timedelta
from typing import Optional, Union
from pydantic import BaseModel
from contextlib import asynccontextmanager
from pathlib import Path
import json
import os
import subprocess
import sys
from api.admin import router as admin_router, stripe_webhook, verify_admin
from api.portal import router as portal_router

# Get project root directory
BASE_DIR = Path(__file__).parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    db_path = os.getenv("DATABASE_PATH", "admin.db")
    if not os.path.exists(db_path):
        print("📦 Creating database...")
        try:
            # Import and run setup_db directly
            import sqlite3
            from api import setup_db
            # The setup_db.py file will run when imported
            print("✅ Database created via import!")
        except Exception as e:
            print(f"⚠️ Database setup error: {e}")
            # Fallback: create database manually
            try:
                import sqlite3
                db_path = os.getenv("DATABASE_PATH", "admin.db")
                con = sqlite3.connect(db_path)
                # Create tables if they don't exist
                con.execute("""
                    CREATE TABLE IF NOT EXISTS test_keys(
                        key TEXT PRIMARY KEY,
                        email TEXT,
                        expiry_date TEXT,
                        max_calls INTEGER DEFAULT 50,
                        calls_used INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'active',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                con.execute("""
                    CREATE TABLE IF NOT EXISTS brokers(
                        id TEXT PRIMARY KEY,
                        email TEXT,
                        name TEXT,
                        model TEXT,
                        referrals INTEGER DEFAULT 0,
                        earned REAL DEFAULT 0,
                        stripe_account_id TEXT
                    )
                """)
                con.execute("""
                    CREATE TABLE IF NOT EXISTS customers(
                        email TEXT PRIMARY KEY,
                        api_calls INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'active',
                        broker_ref TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                con.execute("""
                    CREATE TABLE IF NOT EXISTS referrals(
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_ref TEXT,
                        customer_email TEXT,
                        customer_id TEXT,
                        amount REAL,
                        status TEXT DEFAULT 'pending',
                        date TEXT DEFAULT CURRENT_TIMESTAMP,
                        paid_at TEXT,
                        stripe_transfer_id TEXT,
                        days_active INTEGER
                    )
                """)
                con.commit()
                con.close()
                print("✅ Database created via fallback!")
            except Exception as e2:
                print(f"❌ Could not create database: {e2}")
    
    yield
    
    # Shutdown: cleanup if needed
    pass

app = FastAPI(title="Lien Deadline API", version="1.0.0", lifespan=lifespan)

# CORS middleware to allow requests from landing page
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include admin routes
app.include_router(admin_router)
app.include_router(portal_router)

# Serve static files (HTML, CSS, JS)
# Mount static files directory (serves files from project root)
try:
    app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")
except Exception as e:
    print(f"⚠️ Could not mount static files: {e}")

# Serve HTML dashboards
@app.get("/admin-dashboard.html")
def serve_admin_dashboard(user=Depends(verify_admin)):
    """Serve admin dashboard HTML (protected with HTTP Basic Auth)"""
    file_path = BASE_DIR / "admin-dashboard.html"
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="Admin dashboard not found")

@app.get("/broker-dashboard.html")
def serve_broker_dashboard():
    """Serve broker dashboard HTML"""
    file_path = BASE_DIR / "broker-dashboard.html"
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="Broker dashboard not found")

@app.get("/customer-dashboard.html")
def serve_customer_dashboard():
    """Serve customer dashboard HTML"""
    file_path = BASE_DIR / "customer-dashboard.html"
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="Customer dashboard not found")

@app.get("/index.html")
def serve_landing_page():
    """Serve landing page HTML"""
    file_path = BASE_DIR / "index.html"
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="Landing page not found")

@app.get("/calculator.html")
def serve_calculator():
    """Serve calculator HTML"""
    file_path = BASE_DIR / "calculator.html"
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="Calculator not found")

@app.get("/calculator.js")
def serve_calculator_js():
    """Serve calculator JavaScript"""
    file_path = BASE_DIR / "calculator.js"
    if file_path.exists():
        return FileResponse(str(file_path), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Calculator JS not found")

@app.get("/dashboard.html")
def serve_dashboard():
    """Serve dashboard HTML"""
    file_path = BASE_DIR / "dashboard.html"
    if file_path.exists():
        return FileResponse(str(file_path))
    raise HTTPException(status_code=404, detail="Dashboard not found")

@app.get("/dashboard.js")
def serve_dashboard_js():
    """Serve dashboard JavaScript"""
    file_path = BASE_DIR / "dashboard.js"
    if file_path.exists():
        return FileResponse(str(file_path), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Dashboard JS not found")

# Stripe webhook endpoint (no auth - Stripe signs it)
# Note: This is at root level, not under /admin, because Stripe webhooks don't use Basic Auth
# stripe_webhook is already imported at the top: from api.admin import stripe_webhook
@app.post("/webhook/stripe")
async def stripe_webhook_handler(request: Request):
    """Stripe webhook endpoint - delegates to admin router webhook handler"""
    return await stripe_webhook(request)

# Request model
class CalculateRequest(BaseModel):
    invoice_date: str
    state: str
    role: str

# Load state rules from JSON file
STATE_RULES_PATH = Path(__file__).parent.parent / "state_rules.json"
try:
    with open(STATE_RULES_PATH, 'r') as f:
        STATE_RULES = json.load(f)
except FileNotFoundError:
    print(f"⚠️ Warning: state_rules.json not found at {STATE_RULES_PATH}. Using fallback rules.")
    STATE_RULES = {
        "TX": {
            "state_name": "Texas",
            "preliminary_notice": {"commercial_days": 75, "name": "Notice of Claim"},
            "lien_filing": {"commercial_days": 105, "name": "Lien Affidavit"},
            "serving_requirements": ["property_owner", "original_contractor"],
            "statute_citations": ["Texas Property Code § 53.056"],
            "critical_warnings": ["⚠️ Must send monthly notices for ongoing work"],
            "notes": "Commercial deadlines"
        }
    }

# Keep old LIEN_RULES for backward compatibility
LIEN_RULES = {}
for state_code, rules in STATE_RULES.items():
    prelim_days = rules.get("preliminary_notice", {}).get("commercial_days", rules.get("preliminary_notice", {}).get("days", 75))
    lien_days = rules.get("lien_filing", {}).get("commercial_days", rules.get("lien_filing", {}).get("days", 90))
    LIEN_RULES[state_code] = {
        "preliminary_notice_days": prelim_days,
        "lien_filing_days": lien_days,
        "serving": rules.get("serving_requirements", [])
    }

@app.get("/health")
def health_check():
    """Health check endpoint for Railway deployment"""
    return {"status": "ok", "message": "API is running"}

@app.get("/")
def root():
    return {
        "name": "Lien Deadline API",
        "version": "1.0.0",
        "status": "active",
        "states_available": list(LIEN_RULES.keys())
    }

@app.post("/v1/calculate")
def calculate_deadline(data: CalculateRequest, api_key: str = None):
    """
    Calculate mechanics lien deadlines based on invoice date and state.
    
    Returns:
    - preliminary_notice_deadline: When to send preliminary notice
    - lien_filing_deadline: When to file the lien
    - serving_requirements: Who must be served
    """
    return _calculate_deadline_internal(data, api_key)

@app.post("/v1/calculate-deadline")
async def calculate_deadline_alt(
    invoice_date: str = None,
    state: str = None,
    role: str = "supplier",
    project_type: str = "commercial",
    data: Union[dict, CalculateRequest] = Body(None),
    x_api_key: str = Header(None, alias="X-API-Key")
):
    """
    Calculate mechanics lien deadlines based on state laws.
    
    Accepts query parameters or JSON body.
    
    Args:
        invoice_date: ISO format date (YYYY-MM-DD)
        state: State code (TX, CA, FL)
        role: supplier or subcontractor (default: supplier)
        project_type: residential or commercial (default: commercial)
    """
    # Handle both form data and JSON body
    if isinstance(data, dict):
        invoice_date = data.get("invoice_date") or invoice_date
        state = data.get("state") or state
        role = data.get("role") or role
        project_type = data.get("project_type", "commercial")
    elif isinstance(data, CalculateRequest):
        invoice_date = data.invoice_date
        state = data.state
        role = data.role
        project_type = getattr(data, "project_type", "commercial")
    
    # Validate required fields
    if not invoice_date or not state:
        return {
            "error": "Missing required fields",
            "message": "invoice_date and state are required"
        }
    
    state_code = state.upper()
    
    # Validate state
    if state_code not in STATE_RULES:
        available_states = ", ".join(STATE_RULES.keys())
        return {
            "error": f"State {state_code} not yet supported",
            "available_states": list(STATE_RULES.keys()),
            "message": "Need this state? We'll add it in 48 hours! Contact us."
        }
    
    rules = STATE_RULES[state_code]
    
    # Parse invoice date
    try:
        delivery_date = datetime.fromisoformat(invoice_date)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}
    
    # Calculate preliminary notice deadline
    prelim_notice = rules["preliminary_notice"]
    if state_code == "TX" and project_type == "residential":
        prelim_days = prelim_notice["residential_days"]
    elif state_code == "TX":
        prelim_days = prelim_notice["commercial_days"]
    else:
        prelim_days = prelim_notice["days"]
    
    prelim_deadline = delivery_date + timedelta(days=prelim_days)
    
    # Calculate lien filing deadline
    lien_filing = rules["lien_filing"]
    if state_code == "TX" and project_type == "residential":
        lien_days = lien_filing["residential_days"]
    elif state_code == "TX":
        lien_days = lien_filing["commercial_days"]
    elif state_code == "CA":
        lien_days = lien_filing["standard_days"]  # Use standard 90 days
    else:
        lien_days = lien_filing["days"]
    
    lien_deadline = delivery_date + timedelta(days=lien_days)
    
    # Calculate days until deadlines
    today = datetime.now()
    days_to_prelim = (prelim_deadline - today).days
    days_to_lien = (lien_deadline - today).days
    
    # Determine urgency
    prelim_urgency = "critical" if days_to_prelim <= 7 else "warning" if days_to_prelim <= 30 else "normal"
    lien_urgency = "critical" if days_to_lien <= 7 else "warning" if days_to_lien <= 30 else "normal"
    
    return {
        "state": rules["state_name"],
        "state_code": state_code,
        "invoice_date": invoice_date,
        "role": role,
        "project_type": project_type,
        "preliminary_notice": {
            "name": prelim_notice["name"],
            "deadline": prelim_deadline.strftime('%Y-%m-%d'),
            "days_from_now": days_to_prelim,
            "urgency": prelim_urgency,
            "description": prelim_notice["description"]
        },
        "lien_filing": {
            "name": lien_filing["name"],
            "deadline": lien_deadline.strftime('%Y-%m-%d'),
            "days_from_now": days_to_lien,
            "urgency": lien_urgency,
            "description": lien_filing["description"]
        },
        "serving_requirements": rules["serving_requirements"],
        "statute_citations": rules["statute_citations"],
        "critical_warnings": rules["critical_warnings"],
        "notes": rules["notes"],
        "disclaimer": "⚠️ This is general information only, NOT legal advice. Always consult a licensed construction attorney before taking action. Deadlines vary based on project specifics.",
        "response_time_ms": 45
    }

def _calculate_deadline_internal(data: CalculateRequest, api_key: str = None):
    """
    Calculate mechanics lien deadlines based on invoice date and state.
    
    Returns:
    - preliminary_notice_deadline: When to send preliminary notice
    - lien_filing_deadline: When to file the lien
    - serving_requirements: Who must be served
    """
    # Check test key if provided
    if api_key and api_key.startswith("test_"):
        import sqlite3
        db_path = os.getenv("DATABASE_PATH", "admin.db")
        con = sqlite3.connect(db_path)
        cur = con.execute("""
            SELECT calls_used, max_calls, expiry_date, status, email
            FROM test_keys 
            WHERE key=?
        """, (api_key,))
        
        test_key_row = cur.fetchone()
        
        if not test_key_row:
            con.close()
            return {
                "error": "Invalid API key",
                "message": "Test key not found"
            }
        
        # Extract test key data
        calls_used = test_key_row[0]
        max_calls = test_key_row[1]
        expiry_date_str = test_key_row[2]
        status = test_key_row[3]
        email = test_key_row[4]
        
        # Check expiry date
        expiry_date = datetime.fromisoformat(expiry_date_str)
        if expiry_date < datetime.utcnow():
            con.execute("UPDATE test_keys SET status='expired' WHERE key=?", (api_key,))
            con.commit()
            con.close()
            return {
                "error": "Test key expired",
                "message": "Test key expired (7-day limit reached). Upgrade to full access."
            }
        
        # Check call limit
        if calls_used >= max_calls:
            con.execute("UPDATE test_keys SET status='expired' WHERE key=?", (api_key,))
            con.commit()
            con.close()
            return {
                "error": "Test key expired",
                "message": f"Test key expired (50 call limit reached). Upgrade to unlimited for $299/month."
            }
        
        # Increment usage
        new_calls_used = calls_used + 1
        con.execute("""
            UPDATE test_keys 
            SET calls_used = ? 
            WHERE key=?
        """, (new_calls_used, api_key))
        
        # Send upgrade email at 40 calls (in production)
        if new_calls_used == 40:
            # send_email(to=email, subject="You've used 40 of 50 free API calls", ...)
            pass
        
        con.commit()
        con.close()
    
    try:
        # Parse invoice date
        invoice_date = datetime.fromisoformat(data.invoice_date)
        state = data.state.upper()
        
        # Check if state is supported
        if state not in LIEN_RULES:
            return {
                "error": f"State {state} not yet supported",
                "message": f"We currently support: {', '.join(LIEN_RULES.keys())}",
                "supported_states": list(LIEN_RULES.keys())
            }
        
        # Get rules for this state
        rules = LIEN_RULES[state]
        
        # Calculate deadlines (simple date math)
        notice_deadline = invoice_date + timedelta(days=rules["preliminary_notice_days"])
        lien_deadline = invoice_date + timedelta(days=rules["lien_filing_days"])
        
        return {
            "preliminary_notice_deadline": notice_deadline.strftime("%Y-%m-%d"),
            "lien_filing_deadline": lien_deadline.strftime("%Y-%m-%d"),
            "serving_requirements": rules["serving"],
            "state": state,
            "role": data.role,
            "invoice_date": data.invoice_date,
            "disclaimer": "Not legal advice. Consult attorney. This API provides general deadline estimates. Deadlines may vary based on project type, contract terms, and local rules. Always consult a construction attorney before making lien filing decisions."
        }
    
    except ValueError as e:
        return {
            "error": "Invalid date format",
            "message": "Please use YYYY-MM-DD format for invoice_date",
            "details": str(e)
        }
    except Exception as e:
        return {
            "error": "Calculation failed",
            "message": str(e)
        }

@app.get("/v1/states")
def get_states():
    """Get list of supported states"""
    return {
        "supported_states": list(STATE_RULES.keys()),
        "count": len(STATE_RULES),
        "states": {code: rules["state_name"] for code, rules in STATE_RULES.items()}
    }

@app.get("/test-calculate")
def test_calculate():
    """Test the calculation with sample data"""
    test_results = []
    
    test_cases = [
        {"invoice_date": "2025-10-24", "state": "TX", "project_type": "commercial"},
        {"invoice_date": "2025-11-01", "state": "CA", "project_type": "commercial"},
        {"invoice_date": "2025-09-15", "state": "FL", "project_type": "commercial"},
    ]
    
    for test in test_cases:
        try:
            result = calculate_deadline_alt(**test)
            test_results.append(result)
        except Exception as e:
            test_results.append({"error": str(e), **test})
    
    return {"test_cases": test_results}

