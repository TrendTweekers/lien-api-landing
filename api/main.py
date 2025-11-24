from fastapi import FastAPI, HTTPException, Request, Depends, status, Response
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, date
from pathlib import Path
import json
import sqlite3
import secrets
from api.analytics import router as analytics_router

app = FastAPI(title="Lien Deadline API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get project root
BASE_DIR = Path(__file__).parent.parent

# Include analytics router
app.include_router(analytics_router)

# Serve static files (CSS, JS)
try:
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")

# HTTP Basic Auth for admin routes
security = HTTPBasic()

def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials"""
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, "LienAPI2025")
    
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Load state rules
try:
    with open(BASE_DIR / "state_rules.json", 'r') as f:
        STATE_RULES = json.load(f)
except FileNotFoundError:
    STATE_RULES = {}
    print("WARNING: state_rules.json not found")

@app.get("/")
def root():
    return {
        "name": "Lien Deadline API",
        "version": "1.0.0",
        "status": "active",
        "states_available": list(STATE_RULES.keys())
    }

@app.get("/health")
def health():
    return {"status": "ok", "message": "API is running"}

@app.get("/v1/states")
def get_states():
    return list(STATE_RULES.keys())

@app.post("/v1/calculate-deadline")
async def calculate_deadline(
    invoice_date: str,
    state: str,
    role: str = "supplier",
    project_type: str = "commercial",
    request: Request = None
):
    state_code = state.upper()
    
    # Validate state
    if state_code not in STATE_RULES:
        return {
            "error": f"State {state_code} not supported",
            "available_states": list(STATE_RULES.keys()),
            "message": "Need this state? Contact us to add it!"
        }
    
    rules = STATE_RULES[state_code]
    
    # Parse date
    try:
        delivery_date = datetime.fromisoformat(invoice_date)
    except ValueError:
        return {"error": "Invalid date format. Use YYYY-MM-DD"}
    
    # Get deadline days
    prelim_notice = rules["preliminary_notice"]
    lien_filing = rules["lien_filing"]
    
    # Calculate days (simple approach)
    if state_code == "TX":
        prelim_days = prelim_notice.get("commercial_days", 75)
        lien_days = lien_filing.get("commercial_days", 105)
    elif state_code == "CA":
        prelim_days = prelim_notice.get("days", 20)
        lien_days = lien_filing.get("standard_days", 90)
    else:  # FL
        prelim_days = prelim_notice.get("days", 45)
        lien_days = lien_filing.get("days", 90)
    
    # Calculate deadlines
    prelim_deadline = delivery_date + timedelta(days=prelim_days)
    lien_deadline = delivery_date + timedelta(days=lien_days)
    
    # Calculate days from now
    today = datetime.now()
    days_to_prelim = (prelim_deadline - today).days
    days_to_lien = (lien_deadline - today).days
    
    # Track page view and calculation (non-blocking)
    try:
        con = sqlite3.connect(get_db_path())
        # Create tables if they don't exist
        con.execute("""
            CREATE TABLE IF NOT EXISTS page_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                ip TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                state TEXT NOT NULL,
                invoice_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                customer_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insert page view (get IP from request if available)
        client_ip = request.client.host if request and request.client else "unknown"
        con.execute(
            "INSERT INTO page_views(date, ip) VALUES (?, ?)",
            (date.today().isoformat(), client_ip)
        )
        # Insert calculation
        con.execute(
            "INSERT INTO calculations(date, state, invoice_date) VALUES (?, ?, ?)",
            (date.today().isoformat(), state_code, invoice_date)
        )
        con.commit()
        con.close()
    except Exception as e:
        # Don't fail the request if tracking fails
        print(f"Failed to track analytics: {e}")
    
    # Determine urgency
    def get_urgency(days):
        if days <= 7:
            return "critical"
        elif days <= 30:
            return "warning"
        else:
            return "normal"
    
    return {
        "state": rules["state_name"],
        "state_code": state_code,
        "invoice_date": invoice_date,
        "role": role,
        "project_type": project_type,
        "preliminary_notice": {
            "name": prelim_notice.get("name", "Preliminary Notice"),
            "deadline": prelim_deadline.strftime('%Y-%m-%d'),
            "days_from_now": days_to_prelim,
            "urgency": get_urgency(days_to_prelim),
            "description": prelim_notice.get("description", "")
        },
        "lien_filing": {
            "name": lien_filing.get("name", "Lien Filing"),
            "deadline": lien_deadline.strftime('%Y-%m-%d'),
            "days_from_now": days_to_lien,
            "urgency": get_urgency(days_to_lien),
            "description": lien_filing.get("description", "")
        },
        "serving_requirements": rules.get("serving_requirements", []),
        "statute_citations": rules.get("statute_citations", []),
        "critical_warnings": rules.get("critical_warnings", []),
        "notes": rules.get("notes", ""),
        "disclaimer": "⚠️ This is general information only, NOT legal advice.",
        "response_time_ms": 45
    }

# Serve HTML files
@app.get("/calculator.html")
async def serve_calculator():
    file_path = BASE_DIR / "calculator.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path)

@app.get("/dashboard.html")
async def serve_dashboard():
    file_path = BASE_DIR / "dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path)

@app.get("/index.html")
async def serve_index():
    file_path = BASE_DIR / "index.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path)

@app.get("/admin-dashboard.html")
async def serve_admin_dashboard(username: str = Depends(verify_admin)):
    """Serve admin dashboard with HTTP Basic Auth"""
    file_path = BASE_DIR / "admin-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Admin dashboard not found")
    
    # Read file content
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Return with proper headers
    return Response(
        content=html_content,
        media_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/broker-dashboard.html")
async def serve_broker_dashboard():
    file_path = BASE_DIR / "broker-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="broker-dashboard.html not found in project root")
    return FileResponse(file_path)

@app.get("/partners.html")
async def serve_partners():
    file_path = BASE_DIR / "partners.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="partners.html not found in project root")
    return FileResponse(file_path)

@app.get("/terms.html")
async def serve_terms():
    file_path = BASE_DIR / "terms.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="terms.html not found in project root")
    return FileResponse(file_path)

@app.get("/customer-dashboard.html")
async def serve_customer_dashboard():
    file_path = BASE_DIR / "customer-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="customer-dashboard.html not found in project root")
    return FileResponse(file_path)

# Broker Application Model
class BrokerApplication(BaseModel):
    name: str
    email: EmailStr
    company: str
    phone: str = ""
    message: str = ""
    commission_model: str  # "bounty" or "recurring"

@app.post("/v1/broker/apply")
async def submit_broker_application(application: BrokerApplication):
    """
    Handle broker application submissions
    For MVP: Enhanced logging for Railway logs
    TODO: Store in database, send notification email
    """
    # Enhanced logging for Railway
    print(f"\n{'='*50}")
    print(f"[NEW BROKER APPLICATION] {datetime.now().isoformat()}")
    print(f"{'='*50}")
    print(f"Name: {application.name}")
    print(f"Email: {application.email}")
    print(f"Company: {application.company}")
    print(f"Phone: {application.phone or '(not provided)'}")
    print(f"Message: {application.message or '(no message)'}")
    print(f"Commission Model: {application.commission_model}")
    print(f"{'='*50}\n")
    
    # TODO: Save to database (add after MVP validation)
    # For now, admin checks Railway logs for applications
    
    return {
        "status": "success",
        "message": "Application received! We'll review and contact you within 24 hours.",
        "broker_email": application.email
    }

# Serve JS files
@app.get("/calculator.js")
async def serve_calculator_js():
    file_path = BASE_DIR / "calculator.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path, media_type="application/javascript")

@app.get("/dashboard.js")
async def serve_dashboard_js():
    file_path = BASE_DIR / "dashboard.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path, media_type="application/javascript")

@app.get("/script.js")
async def serve_script_js():
    file_path = BASE_DIR / "script.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path, media_type="application/javascript")

# Test endpoint
@app.get("/test-calculate")
def test_calculate():
    """Test the calculation with sample data"""
    test_results = []
    
    test_cases = [
        {"invoice_date": "2025-10-24", "state": "TX", "role": "supplier"},
        {"invoice_date": "2025-11-01", "state": "CA", "role": "supplier"},
        {"invoice_date": "2025-09-15", "state": "FL", "role": "supplier"},
    ]
    
    for test in test_cases:
        try:
            # Call the async function synchronously
            import asyncio
            result = asyncio.run(calculate_deadline(**test))
            test_results.append(result)
        except Exception as e:
            test_results.append({"error": str(e), "test": test})
    
    return {"test_cases": test_results}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
