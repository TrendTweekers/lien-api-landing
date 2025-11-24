from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from pathlib import Path
import json

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
    project_type: str = "commercial"
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
