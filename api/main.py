from fastapi import FastAPI, HTTPException, Request, Depends, status, Response, Header
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, date
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
import json
import sqlite3
import secrets
import os
import bcrypt
import stripe
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.rate_limiter import limiter
from api.analytics import router as analytics_router
from api.admin import router as admin_router

app = FastAPI(title="Lien Deadline API")

# Rate limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# HTTPS Redirect Middleware
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Check if behind a proxy (Railway/Cloudflare)
        forwarded_proto = request.headers.get("x-forwarded-proto")
        
        if forwarded_proto == "http":
            # Redirect to HTTPS
            url = str(request.url).replace("http://", "https://", 1)
            return RedirectResponse(url=url, status_code=301)
        
        response = await call_next(request)
        return response

# Add HTTPS redirect middleware (before CORS)
app.add_middleware(HTTPSRedirectMiddleware)

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

# Database connection
def get_db():
    """Get database connection"""
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database
def init_db():
    """Initialize database with schema"""
    schema_path = BASE_DIR / "database" / "schema.sql"
    if not schema_path.exists():
        print(f"⚠️ Schema file not found: {schema_path}")
        return
    
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    db = sqlite3.connect(str(db_path))
    try:
        with open(schema_path, 'r') as f:
            db.executescript(f.read())
        db.commit()
        
        # Run migrations
        migrations_dir = BASE_DIR / "database" / "migrations"
        if migrations_dir.exists():
            for migration_file in sorted(migrations_dir.glob("*.sql")):
                try:
                    with open(migration_file, 'r') as f:
                        db.executescript(f.read())
                    db.commit()
                    print(f"✅ Migration applied: {migration_file.name}")
                except Exception as e:
                    print(f"⚠️ Migration error ({migration_file.name}): {e}")
        
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
    finally:
        db.close()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Include routers with full paths to match frontend calls
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()
    # Log registered routes for debugging
    print("\n=== REGISTERED ROUTES ===")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            methods = list(route.methods) if hasattr(route.methods, '__iter__') else [str(route.methods)]
            print(f"{methods} {route.path}")
    print("========================\n")

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
async def root():
    """Serve index.html landing page at root"""
    file_path = BASE_DIR / "index.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/test-api")
async def test_api():
    """Serve test-api.html API tester page"""
    file_path = BASE_DIR / "test-api.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="test-api.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/health")
def health():
    return {"status": "ok", "message": "API is running"}

@app.get("/v1/states")
def get_states():
    return list(STATE_RULES.keys())

# Calculate deadline request model
class CalculateDeadlineRequest(BaseModel):
    invoice_date: str
    state: str
    role: str = "supplier"
    project_type: str = "commercial"

def get_client_ip(request: Request) -> str:
    """Get real client IP from headers (works with Railway/Cloudflare)"""
    return (
        request.headers.get("cf-connecting-ip") or 
        request.headers.get("x-forwarded-for", "").split(",")[0].strip() or
        request.headers.get("x-real-ip") or
        (request.client.host if request.client else "unknown")
    )

@app.post("/v1/calculate")
@app.post("/api/v1/calculate-deadline")
@limiter.limit("10/minute")
async def calculate_deadline(
    request: Request,
    request_data: CalculateDeadlineRequest
):
    invoice_date = request_data.invoice_date
    state = request_data.state
    role = request_data.role
    project_type = request_data.project_type
    state_code = state.upper()
    
    # Get client IP for email gate tracking
    client_ip = get_client_ip(request)
    
    # Email gate tracking - check if IP has exceeded free limit
    db = get_db()
    try:
        # Create email_gate_tracking table if it doesn't exist
        db.execute("""
            CREATE TABLE IF NOT EXISTS email_gate_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                email TEXT,
                calculation_count INTEGER DEFAULT 1,
                first_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_captured_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_ip ON email_gate_tracking(ip_address)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_email ON email_gate_tracking(email)")
        
        # Check if IP has exceeded free limit without providing email
        tracking = db.execute("""
            SELECT calculation_count, email, email_captured_at 
            FROM email_gate_tracking 
            WHERE ip_address = ? 
            ORDER BY last_calculation_at DESC 
            LIMIT 1
        """, (client_ip,)).fetchone()
        
        if tracking:
            count = tracking[0] if tracking else 0
            email = tracking[1] if tracking and len(tracking) > 1 else None
            
            # If no email and already used 3 calculations
            if not email and count >= 3:
                db.close()
                raise HTTPException(
                    status_code=403,
                    detail="Free trial limit reached. Please provide your email for 7 more calculations."
                )
            
            # If email provided but exceeded 10 total
            if email and count >= 10:
                db.close()
                raise HTTPException(
                    status_code=403,
                    detail="Free trial limit reached (10 calculations). Upgrade to unlimited for $299/month."
                )
            
            # Update count
            db.execute("""
                UPDATE email_gate_tracking 
                SET calculation_count = calculation_count + 1,
                    last_calculation_at = CURRENT_TIMESTAMP
                WHERE ip_address = ?
            """, (client_ip,))
        else:
            # First calculation from this IP
            db.execute("""
                INSERT INTO email_gate_tracking (ip_address, calculation_count)
                VALUES (?, 1)
            """, (client_ip,))
        
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in email gate tracking: {e}")
        # Continue with calculation even if tracking fails
    
    # Validate state
    if state_code not in STATE_RULES:
        if db:
            db.close()
        return {
            "error": f"State {state_code} not supported",
            "available_states": list(STATE_RULES.keys()),
            "message": "Need this state? Contact us to add it!"
        }
    
    rules = STATE_RULES[state_code]
    
    # Parse date - handle both MM/DD/YYYY and YYYY-MM-DD formats
    delivery_date = None
    try:
        # Try MM/DD/YYYY format first (common in US)
        delivery_date = datetime.strptime(invoice_date, "%m/%d/%Y")
    except ValueError:
        try:
            # Try YYYY-MM-DD format (ISO format)
            delivery_date = datetime.strptime(invoice_date, "%Y-%m-%d")
        except ValueError:
            try:
                # Try ISO format with fromisoformat
                delivery_date = datetime.fromisoformat(invoice_date)
            except ValueError:
                return {"error": "Invalid date format. Use MM/DD/YYYY or YYYY-MM-DD"}
    
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
        db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
        con = sqlite3.connect(str(db_path))
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
# Serve HTML files (with .html extension)
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

@app.get("/api.html")
async def serve_api():
    file_path = BASE_DIR / "api.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path)

@app.get("/admin-dashboard.html")
async def serve_admin_dashboard_html(username: str = Depends(verify_admin)):
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
async def serve_broker_dashboard_html():
    file_path = BASE_DIR / "broker-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="broker-dashboard.html not found in project root")
    return FileResponse(file_path)

@app.get("/partners.html")
async def serve_partners_html():
    file_path = BASE_DIR / "partners.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="partners.html not found in project root")
    return FileResponse(file_path)

@app.get("/terms.html")
async def serve_terms_html():
    file_path = BASE_DIR / "terms.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="terms.html not found in project root")
    return FileResponse(file_path)

@app.get("/customer-dashboard.html")
async def serve_customer_dashboard_html():
    file_path = BASE_DIR / "customer-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="customer-dashboard.html not found in project root")
    return FileResponse(file_path)

# Clean URLs (without .html extension)
@app.get("/calculator")
async def serve_calculator_clean():
    """Clean URL: /calculator → calculator.html"""
    file_path = BASE_DIR / "calculator.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Calculator not found")
    return FileResponse(file_path)

@app.get("/dashboard")
async def serve_dashboard_clean():
    """Clean URL: /dashboard → dashboard.html"""
    file_path = BASE_DIR / "dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(file_path)

@app.get("/admin-dashboard")
async def serve_admin_dashboard_clean(username: str = Depends(verify_admin)):
    """Clean URL: /admin-dashboard → admin-dashboard.html"""
    file_path = BASE_DIR / "admin-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Admin dashboard not found")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    return Response(
        content=html_content,
        media_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/broker-dashboard")
async def serve_broker_dashboard_clean():
    """Clean URL: /broker-dashboard → broker-dashboard.html"""
    file_path = BASE_DIR / "broker-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Broker dashboard not found")
    return FileResponse(file_path)

@app.get("/partners")
async def serve_partners_clean():
    """Clean URL: /partners → partners.html"""
    file_path = BASE_DIR / "partners.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Partners page not found")
    return FileResponse(file_path)

@app.get("/terms")
async def serve_terms_clean():
    """Clean URL: /terms → terms.html"""
    file_path = BASE_DIR / "terms.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Terms page not found")
    return FileResponse(file_path)

@app.get("/customer-dashboard")
async def serve_customer_dashboard_clean():
    """Clean URL: /customer-dashboard → customer-dashboard.html"""
    file_path = BASE_DIR / "customer-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Customer dashboard not found")
    return FileResponse(file_path)

# Broker Application Model
class BrokerApplication(BaseModel):
    name: str
    email: EmailStr
    company: str
    phone: str = ""
    message: str = ""
    commission_model: str  # "bounty" or "recurring"

# Broker storage (replace with database after MVP)
# This stores pending broker applications
pending_brokers = {}

# This stores approved brokers
approved_brokers = {
    # Example format (empty for now):
    # "john@example.com": {
    #     "name": "John Smith",
    #     "company": "ABC Insurance",
    #     "approved_date": "2025-11-24",
    #     "commission_model": "bounty"
    # }
}

@app.post("/v1/broker/apply")
async def submit_broker_application(application: BrokerApplication):
    """Handle broker application submissions"""
    
    email = application.email.lower()
    
    # Save to pending list
    pending_brokers[email] = {
        "name": application.name,
        "email": email,
        "company": application.company,
        "phone": application.phone or "(not provided)",
        "message": application.message or "(no message)",
        "commission_model": application.commission_model,
        "applied_date": datetime.now().isoformat(),
        "status": "pending"
    }
    
    # Enhanced logging
    print(f"\n{'='*50}")
    print(f"[NEW BROKER APPLICATION] {datetime.now().isoformat()}")
    print(f"{'='*50}")
    print(f"Name: {application.name}")
    print(f"Email: {email}")
    print(f"Company: {application.company}")
    print(f"Phone: {application.phone or '(not provided)'}")
    print(f"Message: {application.message or '(no message)'}")
    print(f"Commission Model: {application.commission_model}")
    print(f"{'='*50}\n")
    
    return {
        "status": "success",
        "message": "Application received! We'll review and contact you within 24 hours.",
        "broker_email": email
    }

@app.post("/v1/broker/check-approval")
async def check_broker_approval(data: dict):
    """Check if broker email is approved"""
    email = data.get('email', '').lower()
    
    if email in approved_brokers:
        return {
            "approved": True,
            "name": approved_brokers[email]["name"],
            "commission_model": approved_brokers[email].get("commission_model", "bounty")
        }
    elif email in pending_brokers:
        return {
            "approved": False,
            "pending": True,
            "name": pending_brokers[email]["name"]
        }
    else:
        return {
            "approved": False,
            "pending": False
        }

# Authentication Models
class LoginRequest(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    email: str
    old_password: str
    new_password: str

# Authentication Endpoints
@app.post("/api/login")
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest):
    """Login endpoint - validates credentials and returns session token"""
    db = get_db()
    
    try:
        # Get user
        user = db.execute("SELECT * FROM users WHERE email = ?", (req.email,)).fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Check password
        if not bcrypt.checkpw(req.password.encode(), user['password_hash'].encode()):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Check subscription active
        if user['subscription_status'] not in ['active', 'trialing']:
            raise HTTPException(status_code=403, detail="Subscription expired or cancelled")
        
        # Generate session token
        token = secrets.token_urlsafe(32)
        
        db.execute("""
            UPDATE users 
            SET session_token = ?, last_login = ?
            WHERE email = ?
        """, (token, datetime.now().isoformat(), req.email))
        db.commit()
        
        return {
            "success": True,
            "token": token,
            "email": req.email
        }
    finally:
        db.close()

@app.get("/api/verify-session")
async def verify_session(authorization: str = Header(None)):
    """Verify session token"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="No token provided")
    
    token = authorization.replace('Bearer ', '')
    
    db = get_db()
    try:
        user = db.execute("SELECT * FROM users WHERE session_token = ?", (token,)).fetchone()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        if user['subscription_status'] not in ['active', 'trialing']:
            raise HTTPException(status_code=403, detail="Subscription expired")
        
        return {
            "valid": True,
            "email": user['email'],
            "subscription_status": user['subscription_status']
        }
    finally:
        db.close()

@app.post("/api/change-password")
async def change_password(req: ChangePasswordRequest):
    """Change user password"""
    db = get_db()
    
    try:
        user = db.execute("SELECT * FROM users WHERE email = ?", (req.email,)).fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Verify old password
        if not bcrypt.checkpw(req.old_password.encode(), user['password_hash'].encode()):
            raise HTTPException(status_code=401, detail="Current password incorrect")
        
        # Hash new password
        new_hash = bcrypt.hashpw(req.new_password.encode(), bcrypt.gensalt())
        
        db.execute("UPDATE users SET password_hash = ? WHERE email = ?", 
                   (new_hash.decode(), req.email))
        db.commit()
        
        return {"success": True, "message": "Password changed successfully"}
    finally:
        db.close()

@app.post("/api/logout")
async def logout(authorization: str = Header(None)):
    """Logout - invalidate session token"""
    if not authorization or not authorization.startswith('Bearer '):
        return {"success": True}
    
    token = authorization.replace('Bearer ', '')
    
    db = get_db()
    try:
        db.execute("UPDATE users SET session_token = NULL WHERE session_token = ?", (token,))
        db.commit()
        return {"success": True}
    finally:
        db.close()

# Track email endpoint for calculator gating
class TrackEmailRequest(BaseModel):
    email: str
    timestamp: str

@app.post("/partner-application")
async def partner_application(data: dict):
    """Handle partner application form submission"""
    try:
        db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        
        # Create table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS partner_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT NOT NULL,
                client_count TEXT,
                message TEXT,
                commission_model TEXT,
                timestamp TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        # Insert application
        cur.execute("""
            INSERT INTO partner_applications 
            (name, email, company, client_count, message, commission_model, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('name', ''),
            data.get('email', ''),
            data.get('company', ''),
            data.get('client_count', ''),
            data.get('message', ''),
            data.get('commission_model', ''),
            datetime.now().isoformat()
        ))
        
        con.commit()
        con.close()
        return {"status": "success", "message": "Application submitted!"}
    except Exception as e:
        print(f"Error saving partner application: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/capture-email")
async def capture_email(request: Request, request_data: TrackEmailRequest):
    """Store email and extend calculation limit to 10"""
    db = get_db()
    try:
        # Create email_gate_tracking table if it doesn't exist
        db.execute("""
            CREATE TABLE IF NOT EXISTS email_gate_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                email TEXT,
                calculation_count INTEGER DEFAULT 1,
                first_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                email_captured_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        client_ip = get_client_ip(request)
        
        # Update email for this IP
        cursor = db.execute("""
            UPDATE email_gate_tracking 
            SET email = ?,
                email_captured_at = CURRENT_TIMESTAMP
            WHERE ip_address = ?
        """, (request_data.email, client_ip))
        
        if cursor.rowcount == 0:
            # No existing record, create one
            db.execute("""
                INSERT INTO email_gate_tracking (ip_address, email, email_captured_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (client_ip, request_data.email))
        
        db.commit()
        print(f"📧 Email captured: {request_data.email} from IP: {client_ip}")
        
        return {
            "status": "success",
            "message": "Email captured! You now have 7 more calculations (10 total).",
            "new_limit": 10
        }
    except Exception as e:
        print(f"Error capturing email: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@app.post("/track-email")
async def track_email(request_data: TrackEmailRequest, request: Request):
    """Track email submissions from calculator email gate"""
    try:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Store email tracking in database
        db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        
        # Create table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS email_captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                ip TEXT,
                timestamp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert email capture
        cur.execute("""
            INSERT INTO email_captures (email, ip, timestamp)
            VALUES (?, ?, ?)
        """, (request_data.email, client_ip, request_data.timestamp))
        
        con.commit()
        con.close()
        
        print(f"📧 Email tracked: {request_data.email} from IP: {client_ip} at {request_data.timestamp}")
        
        return {"success": True, "message": "Email tracked"}
    except Exception as e:
        print(f"Error tracking email: {e}")
        return {"success": False, "error": str(e)}

# Stripe Webhook Handler
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks for subscription events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    db = get_db()
    
    # IDEMPOTENCY CHECK - Check if we've already processed this event
    try:
        # Create stripe_events table if it doesn't exist
        db.execute("""
            CREATE TABLE IF NOT EXISTS stripe_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_stripe_events_event_id ON stripe_events(event_id)")
        
        # Check if we've already processed this event
        existing = db.execute(
            "SELECT 1 FROM stripe_events WHERE event_id = ?",
            (event['id'],)
        ).fetchone()
        
        if existing:
            print(f"⚠️ Duplicate event {event['id']} - skipping")
            return {"status": "duplicate", "message": "Event already processed"}
        
        # Record this event
        db.execute(
            "INSERT INTO stripe_events (event_id, event_type) VALUES (?, ?)",
            (event['id'], event['type'])
        )
        db.commit()
    except Exception as e:
        print(f"Error checking idempotency: {e}")
        # Continue processing even if idempotency check fails
    
    try:
    
    try:
        # New subscription
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            email = session.get('customer_details', {}).get('email')
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            
            if not email:
                print("⚠️ No email in checkout session")
                return {"status": "skipped"}
            
            # Check for referral
            metadata = session.get('metadata', {})
            ref_code = metadata.get('ref_code', '')
            
            # Generate secure temporary password
            temp_password = secrets.token_urlsafe(12)
            password_hash = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt())
            
            # Create user account
            try:
                db.execute("""
                    INSERT INTO users (email, password_hash, stripe_customer_id, subscription_id, subscription_status)
                    VALUES (?, ?, ?, ?, 'active')
                """, (email, password_hash.decode(), customer_id, subscription_id))
                
                # Also create customer record
                db.execute("""
                    INSERT INTO customers (email, stripe_customer_id, subscription_id, status, plan, amount)
                    VALUES (?, ?, ?, 'active', 'unlimited', 299.00)
                """, (email, customer_id, subscription_id))
                
                db.commit()
                
                # Send welcome email
                send_welcome_email(email, temp_password)
                
                # Handle referral if exists
                if ref_code and ref_code.startswith('broker_'):
                    broker = db.execute("SELECT * FROM brokers WHERE id = ?", (ref_code,)).fetchone()
                    if broker:
                        # Create referral record
                        db.execute("""
                            INSERT INTO referrals (broker_id, customer_email, customer_id, amount, payout, status)
                            VALUES (?, ?, ?, 299.00, 500.00, 'pending')
                        """, (ref_code, email, customer_id))
                        
                        # Update broker stats
                        db.execute("""
                            UPDATE brokers 
                            SET referrals = referrals + 1 
                            WHERE id = ?
                        """, (ref_code,))
                        
                        db.commit()
                        
                        # Notify broker
                        send_broker_notification(broker['email'], email)
                
            except sqlite3.IntegrityError:
                # User already exists - just update subscription
                db.execute("""
                    UPDATE users 
                    SET subscription_status = 'active', subscription_id = ?
                    WHERE email = ?
                """, (subscription_id, email))
                db.commit()
        
        # Subscription cancelled
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            customer_id = subscription['customer']
            
            db.execute("""
                UPDATE users 
                SET subscription_status = 'cancelled'
                WHERE stripe_customer_id = ?
            """, (customer_id,))
            
            db.execute("""
                UPDATE customers 
                SET status = 'cancelled'
                WHERE stripe_customer_id = ?
            """, (customer_id,))
            
            db.commit()
        
        # Payment failed
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            customer_id = invoice['customer']
            
            db.execute("""
                UPDATE users 
                SET subscription_status = 'past_due'
                WHERE stripe_customer_id = ?
            """, (customer_id,))
            
            db.commit()
        
        return {"status": "success"}
    finally:
        db.close()

def send_welcome_email(email: str, password: str):
    """Send welcome email with login credentials"""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To
        
        sg = SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY', ''))
        
        if not os.getenv('SENDGRID_API_KEY'):
            print(f"⚠️ SENDGRID_API_KEY not set - skipping email to {email}")
            print(f"   Temporary password: {password}")
            return
        
        message = Mail(
            from_email=Email("support@liendeadline.com"),
            to_emails=To(email),
            subject="Welcome to LienDeadline - Your Login Credentials",
            html_content=f"""
            <h2>Welcome to LienDeadline!</h2>
            <p>Your account is now active. Here are your login credentials:</p>
            
            <p><strong>Login:</strong> <a href="https://liendeadline.com/dashboard">https://liendeadline.com/dashboard</a></p>
            <p><strong>Email:</strong> {email}</p>
            <p><strong>Temporary Password:</strong> {password}</p>
            
            <p><em>Please change your password after your first login for security.</em></p>
            
            <h3>Getting Started:</h3>
            <ol>
                <li>Login to your dashboard</li>
                <li>Use the calculator for unlimited lien deadline calculations</li>
                <li>Access covers 23 states (TX, CA, FL, NY, PA, IL, GA, NC, WA, OH, AZ, CO, VA, MI, TN, MA, NJ, MD, WI, MN, IN, MO, SC)</li>
            </ol>
            
            <p>Questions? Reply to this email or contact support@liendeadline.com</p>
            
            <p>Best,<br>The LienDeadline Team</p>
            """
        )
        
        response = sg.send(message)
        print(f"✅ Welcome email sent to {email}")
    except Exception as e:
        print(f"❌ Email failed: {e}")

def send_broker_notification(broker_email: str, customer_email: str):
    """Notify broker of new referral"""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To
        
        if not os.getenv('SENDGRID_API_KEY'):
            print(f"⚠️ SENDGRID_API_KEY not set - skipping broker notification")
            return
        
        sg = SendGridAPIClient(api_key=os.getenv('SENDGRID_API_KEY'))
        
        message = Mail(
            from_email=Email("support@liendeadline.com"),
            to_emails=To(broker_email),
            subject="New Referral - $500 Commission Earned!",
            html_content=f"""
            <h2>Congratulations! New Referral</h2>
            <p>Your referral just signed up:</p>
            
            <p><strong>Customer:</strong> {customer_email}</p>
            <p><strong>Plan:</strong> Unlimited ($299/month)</p>
            <p><strong>Your Commission:</strong> $500 (payable after 30 days)</p>
            
            <p>Track your earnings: <a href="https://liendeadline.com/broker-dashboard">Broker Dashboard</a></p>
            
            <p>Best,<br>The LienDeadline Team</p>
            """
        )
        
        sg.send(message)
        print(f"✅ Broker notification sent to {broker_email}")
    except Exception as e:
        print(f"❌ Broker notification failed: {e}")

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

@app.get("/admin-dashboard.js")
async def serve_admin_dashboard_js():
    file_path = BASE_DIR / "admin-dashboard.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path, media_type="application/javascript")

@app.get("/script.js")
async def serve_script_js():
    file_path = BASE_DIR / "script.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path, media_type="application/javascript")

@app.get("/styles.css")
async def serve_styles_css():
    file_path = BASE_DIR / "styles.css"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path, media_type="text/css")

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

@app.post("/v1/send-email")
async def send_email(data: dict):
    """Send calculation results via email using SendGrid"""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        # Get SendGrid API key from environment variable
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        if not sendgrid_api_key:
            raise HTTPException(status_code=500, detail="SendGrid API key not configured. Please set SENDGRID_API_KEY environment variable.")
        
        to_email = data.get('to_email')
        results = data.get('results', {})
        
        if not to_email:
            raise HTTPException(status_code=400, detail="Email address required")
        
        # Build email content
        state = results.get('state', 'N/A')
        prelim_deadline = results.get('prelimDeadline', 'N/A')
        lien_deadline = results.get('lienDeadline', 'N/A')
        
        html_content = f'''
        <h2>Your Lien Deadline Calculation</h2>
        <p><strong>State:</strong> {state}</p>
        <p><strong>Preliminary Notice Deadline:</strong> {prelim_deadline}</p>
        <p><strong>Lien Filing Deadline:</strong> {lien_deadline}</p>
        <hr>
        <p><em>This is general information only, NOT legal advice. Always consult a licensed construction attorney before taking any legal action.</em></p>
        <p>Visit <a href="https://liendeadline.com">LienDeadline.com</a> for more calculations!</p>
        '''
        
        message = Mail(
            from_email='support@liendeadline.com',
            to_emails=to_email,
            subject='Your Lien Deadline Calculation - LienDeadline.com',
            html_content=html_content
        )
        
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        
        return {"status": "success", "message": "Email sent successfully!"}
        
    except ImportError:
        raise HTTPException(status_code=500, detail="SendGrid library not installed. Run: pip install sendgrid")
    except Exception as e:
        print(f"SendGrid error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

# Admin API endpoints (for admin dashboard)
@app.get("/api/admin/stats")
async def get_admin_stats_api(username: str = Depends(verify_admin)):
    """Return real dashboard stats"""
    db = None
    try:
        db = get_db()
        
        # Check if tables exist
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        
        # Count active customers (with table check)
        customers_count = 0
        if 'customers' in table_names:
            try:
                result = db.execute(
                    "SELECT COUNT(*) FROM customers WHERE status='active'"
                ).fetchone()
                customers_count = result[0] if result else 0
            except Exception as e:
                print(f"Error counting customers: {e}")
        
        # Count approved brokers (with table check)
        brokers_count = 0
        if 'brokers' in table_names:
            try:
                result = db.execute(
                    "SELECT COUNT(*) FROM brokers"
                ).fetchone()
                brokers_count = result[0] if result else 0
            except Exception as e:
                print(f"Error counting brokers: {e}")
        
        # Calculate revenue (sum of active subscriptions)
        revenue_result = 0
        if 'customers' in table_names:
            try:
                result = db.execute(
                    "SELECT SUM(amount) FROM customers WHERE status='active'"
                ).fetchone()
                revenue_result = float(result[0]) if result and result[0] else 0
            except Exception as e:
                print(f"Error calculating revenue: {e}")
        
        return {
            "customers": customers_count,
            "brokers": brokers_count,
            "revenue": float(revenue_result)
        }
    except Exception as e:
        print(f"Error in get_admin_stats_api: {e}")
        import traceback
        traceback.print_exc()
        return {
            "customers": 0,
            "brokers": 0,
            "revenue": 0,
            "error": str(e)
        }
    finally:
        if db:
            db.close()

@app.get("/api/admin/customers")
async def get_customers_api(username: str = Depends(verify_admin)):
    """Return list of customers"""
    db = None
    try:
        db = get_db()
        
        # Check if table exists
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        
        if 'customers' not in table_names:
            print("Customers table does not exist")
            return []
        
        # Try different column names for compatibility
        try:
            rows = db.execute("""
                SELECT email, calls_used, status 
                FROM customers 
                ORDER BY created_at DESC
            """).fetchall()
        except sqlite3.OperationalError:
            # Fallback if created_at doesn't exist
            try:
                rows = db.execute("""
                    SELECT email, api_calls, status 
                    FROM customers 
                    ORDER BY email
                """).fetchall()
            except sqlite3.OperationalError as e:
                print(f"Error querying customers: {e}")
                return []
        
        return [
            {
                "email": row['email'] if 'email' in row.keys() else row[0],
                "calls": row.get('calls_used') or row.get('api_calls') or 0,
                "status": row.get('status') or 'active'
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error in get_customers_api: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if db:
            db.close()

@app.get("/api/admin/brokers")
async def get_brokers_api(username: str = Depends(verify_admin)):
    """Return list of brokers"""
    db = None
    try:
        db = get_db()
        
        # Check if table exists
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        
        if 'brokers' not in table_names:
            print("Brokers table does not exist")
            return []
        
        # Try query with created_at, fallback without it
        try:
            rows = db.execute("""
                SELECT id, name, email, referrals, earned, status
                FROM brokers
                ORDER BY created_at DESC
            """).fetchall()
        except sqlite3.OperationalError:
            try:
                rows = db.execute("""
                    SELECT id, name, email, referrals, earned, status
                    FROM brokers
                    ORDER BY id DESC
                """).fetchall()
            except sqlite3.OperationalError as e:
                print(f"Error querying brokers: {e}")
                return []
        
        return [
            {
                "name": row.get('name') or row.get('email') or 'N/A',
                "email": row.get('email') or 'N/A',
                "referrals": row.get('referrals') or 0,
                "earned": float(row.get('earned') or 0),
                "status": row.get('status') or 'pending'
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error in get_brokers_api: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if db:
            db.close()

@app.get("/api/admin/partner-applications")
async def get_partner_applications_api(username: str = Depends(verify_admin)):
    """Get all partner applications"""
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    
    try:
        # Check if table exists
        cur.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='partner_applications'
        """)
        if not cur.fetchone():
            con.close()
            return []  # Return empty list if table doesn't exist
        
        cur.execute("""
            SELECT name, email, company, client_count, timestamp, status, message, commission_model
            FROM partner_applications 
            ORDER BY timestamp DESC
        """)
        apps = cur.fetchall()
        
        return [
            {
                "name": app[0] if app[0] else "N/A",
                "email": app[1] if app[1] else "N/A",
                "company": app[2] if app[2] else "N/A",
                "client_count": app[3] if app[3] else "N/A",
                "timestamp": app[4] if app[4] else None,
                "status": app[5] if app[5] else "pending",
                "message": app[6] if app[6] else "",
                "commission_model": app[7] if len(app) > 7 and app[7] else ""
            }
            for app in apps
        ]
    except Exception as e:
        print(f"Error loading partner applications: {e}")
        con.close()
        return []  # Return empty list on error
    finally:
        if con:
            con.close()

@app.get("/api/admin/email-captures")
async def get_email_captures_api(username: str = Depends(verify_admin)):
    """Get all email captures from calculator email gate"""
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    con = None
    try:
        con = sqlite3.connect(str(db_path))
        cur = con.cursor()
        
        # Create table if it doesn't exist (in case it hasn't been created yet)
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS email_captures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    ip TEXT,
                    timestamp TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.commit()
        except Exception as e:
            print(f"Error creating email_captures table: {e}")
        
        cur.execute("""
            SELECT email, ip, timestamp
            FROM email_captures 
            ORDER BY timestamp DESC
        """)
        captures = cur.fetchall()
        
        return [
            {
                "email": c[0] if len(c) > 0 else "",
                "ip": c[1] if len(c) > 1 and c[1] else "N/A",
                "timestamp": c[2] if len(c) > 2 else ""
            }
            for c in captures
        ]
    except Exception as e:
        print(f"Error in get_email_captures_api: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if con:
            con.close()

@app.post("/api/admin/approve-partner")
async def approve_partner_api(data: dict, username: str = Depends(verify_admin)):
    """Approve a partner application"""
    email = data.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    
    try:
        # Update status to approved
        cur.execute("UPDATE partner_applications SET status = ? WHERE email = ?", ('approved', email))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Partner application not found")
        
        con.commit()
        
        # TODO: Send email to partner with referral link
        # (You'll implement this later with EmailJS or SendGrid)
        
        return {"status": "ok", "message": "Partner approved"}
    finally:
        con.close()

@app.get("/api/admin/payouts/pending")
async def get_pending_payouts_api(username: str = Depends(verify_admin)):
    """Return pending broker payouts"""
    db = None
    try:
        db = get_db()
        
        # Check if tables exist
        tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        
        if 'referrals' not in table_names:
            print("Referrals table does not exist")
            return []
        
        # Try query with different column names for compatibility
        try:
            rows = db.execute("""
                SELECT r.id, r.broker_id, r.customer_email, r.amount, r.payout, r.status,
                       b.name as broker_name
                FROM referrals r
                LEFT JOIN brokers b ON r.broker_id = b.id
                WHERE r.status = 'pending'
                ORDER BY r.created_at DESC
            """).fetchall()
        except sqlite3.OperationalError:
            # Fallback if columns don't match
            try:
                rows = db.execute("""
                    SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.status,
                           b.name as broker_name, r.days_active
                    FROM referrals r
                    LEFT JOIN brokers b ON r.broker_ref = b.id
                    WHERE r.status = 'ready'
                    ORDER BY r.date ASC
                """).fetchall()
            except sqlite3.OperationalError as e:
                print(f"Error querying pending payouts: {e}")
                return []
        
        return [
            {
                "id": row.get('id') or 0,
                "broker_name": row.get('broker_name') or 'Unknown',
                "broker_id": row.get('broker_id') or row.get('broker_ref') or '',
                "customer_email": row.get('customer_email') or '',
                "amount": float(row.get('amount') or 0),
                "payout": float(row.get('payout') or row.get('amount') or 0),
                "status": row.get('status') or 'pending',
                "days_active": row.get('days_active') or 0
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error in get_pending_payouts_api: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if db:
            db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
