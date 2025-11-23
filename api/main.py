from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from admin import router as admin_router
from portal import router as portal_router

app = FastAPI(title="Lien Deadline API", version="1.0.0")

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

# Stripe webhook endpoint (no auth - Stripe signs it)
# Note: This is at root level, not under /admin, because Stripe webhooks don't use Basic Auth
from admin import stripe_webhook
@app.post("/webhook/stripe")
async def stripe_webhook_handler(request: Request):
    """Stripe webhook endpoint - delegates to admin router webhook handler"""
    return await stripe_webhook(request)

# Request model
class CalculateRequest(BaseModel):
    invoice_date: str
    state: str
    role: str

# You manually fill this dict by reading state lien laws
# Start with Texas, add states one at a time (1 hour per state)
LIEN_RULES = {
    "TX": {
        "preliminary_notice_days": 15,
        "lien_filing_days": 90,
        "serving": ["owner", "gc"]
    },
    # Add more states as you research them:
    # "CA": { ... },
    # "FL": { ... },
    # etc.
}

@app.get("/")
def root():
    return {
        "message": "Lien Deadline API",
        "version": "1.0.0",
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
    # Check test key if provided
    if api_key and api_key.startswith("test_"):
        import sqlite3
        con = sqlite3.connect("admin.db")
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
        "supported_states": list(LIEN_RULES.keys()),
        "count": len(LIEN_RULES)
    }

