from fastapi import FastAPI, HTTPException, Request, Depends, status, Response, Header
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, date
from pathlib import Path
import json
import sqlite3
import secrets
import os
import bcrypt
import stripe
from api.analytics import router as analytics_router
from api.admin import router as admin_router

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
    
    db = get_db()
    try:
        with open(schema_path, 'r') as f:
            db.executescript(f.read())
        db.commit()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
    finally:
        db.close()

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Include routers
app.include_router(analytics_router)
app.include_router(admin_router)

# Initialize database on startup
@app.on_event("startup")
async def startup():
    init_db()

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

@app.post("/v1/calculate")
@app.post("/api/v1/calculate-deadline")
async def calculate_deadline(
    request_data: CalculateDeadlineRequest,
    request: Request = None
):
    invoice_date = request_data.invoice_date
    state = request_data.state
    role = request_data.role
    project_type = request_data.project_type
    state_code = state.upper()
    
    # Validate state
    if state_code not in STATE_RULES:
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
async def login(req: LoginRequest):
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

@app.post("/track-email")
async def track_email(request_data: TrackEmailRequest, request: Request):
    """Track email submissions from calculator email gate"""
    try:
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Store email tracking (you can add this to a database table if needed)
        # For now, just log it
        print(f"📧 Email tracked: {request_data.email} from IP: {client_ip} at {request_data.timestamp}")
        
        # Optional: Store in database for analytics
        # db = get_db()
        # db.execute("""
        #     INSERT INTO email_tracking (email, ip, timestamp)
        #     VALUES (?, ?, ?)
        # """, (request_data.email, client_ip, request_data.timestamp))
        # db.commit()
        # db.close()
        
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
    db = get_db()
    try:
        # Count active customers
        customers_count = db.execute(
            "SELECT COUNT(*) FROM customers WHERE status='active'"
        ).fetchone()[0] or 0
        
        # Count approved brokers
        brokers_count = db.execute(
            "SELECT COUNT(*) FROM brokers WHERE status='approved'"
        ).fetchone()[0] or 0
        
        # Calculate revenue (sum of active subscriptions)
        revenue_result = db.execute(
            "SELECT SUM(amount) FROM customers WHERE status='active'"
        ).fetchone()[0] or 0
        
        return {
            "customers": customers_count,
            "brokers": brokers_count,
            "revenue": float(revenue_result)
        }
    finally:
        db.close()

@app.get("/api/admin/customers")
async def get_customers_api(username: str = Depends(verify_admin)):
    """Return list of customers"""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT email, calls_used, status 
            FROM customers 
            ORDER BY created_at DESC
        """).fetchall()
        
        return [
            {
                "email": row['email'],
                "calls": row['calls_used'] or 0,
                "status": row['status'] or 'active'
            }
            for row in rows
        ]
    finally:
        db.close()

@app.get("/api/admin/brokers")
async def get_brokers_api(username: str = Depends(verify_admin)):
    """Return list of brokers"""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT id, name, email, referrals, earned, status
            FROM brokers
            ORDER BY created_at DESC
        """).fetchall()
        
        return [
            {
                "name": row['name'] or row['email'],
                "email": row['email'],
                "referrals": row['referrals'] or 0,
                "earned": float(row['earned'] or 0),
                "status": row['status'] or 'pending'
            }
            for row in rows
        ]
    finally:
        db.close()

@app.get("/api/admin/payouts/pending")
async def get_pending_payouts_api(username: str = Depends(verify_admin)):
    """Return pending broker payouts"""
    db = get_db()
    try:
        rows = db.execute("""
            SELECT r.id, r.broker_id, r.customer_email, r.amount, r.payout, r.status,
                   b.name as broker_name
            FROM referrals r
            LEFT JOIN brokers b ON r.broker_id = b.id
            WHERE r.status = 'pending'
            ORDER BY r.created_at DESC
        """).fetchall()
        
        return [
            {
                "id": row['id'],
                "broker_name": row['broker_name'] or 'Unknown',
                "broker_id": row['broker_id'],
                "customer_email": row['customer_email'],
                "amount": float(row['amount'] or 0),
                "payout": float(row['payout'] or 0),
                "status": row['status'] or 'pending'
            }
            for row in rows
        ]
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
