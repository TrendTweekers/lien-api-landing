from fastapi import FastAPI, HTTPException, Request, Depends, status, Response, Header, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, date
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
import json
import secrets
import os
import bcrypt
import stripe
import asyncio
import anyio
import smtplib
import ssl
from email.message import EmailMessage
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.rate_limiter import limiter

# Import database functions FIRST (before other local imports to avoid circular dependencies)
from api.database import get_db, get_db_cursor, DB_TYPE, execute_query, BASE_DIR

# THEN import routers (after database is defined)
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

# Bot protection: Trusted Host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["liendeadline.com", "www.liendeadline.com", "*.railway.app", "localhost", "127.0.0.1"]
)

# CORS - must specify origins when allow_credentials=True (cannot use "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://liendeadline.com",
        "https://www.liendeadline.com",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Email configuration check
print("=" * 60)
print("📧 EMAIL CONFIGURATION CHECK")
print("=" * 60)

sendgrid_configured = bool(os.getenv('SENDGRID_API_KEY'))
smtp_configured = bool(os.getenv('SMTP_EMAIL')) and bool(os.getenv('SMTP_PASSWORD'))

if sendgrid_configured:
    print("✅ SendGrid: CONFIGURED")
    print("   From: support@liendeadline.com")
elif smtp_configured:
    print("✅ SMTP: CONFIGURED")
    smtp_email = os.getenv('SMTP_EMAIL')
    print(f"   From: {smtp_email}")
else:
    print("⚠️  NO EMAIL SERVICE CONFIGURED")
    print("   Emails will be logged to console only")
    print("   Users won't receive welcome emails or password resets")

print("=" * 60)

# Initialize database
def init_db():
    """Initialize database with schema"""
    schema_path = BASE_DIR / "database" / "schema.sql"
    if not schema_path.exists():
        print(f"⚠️ Schema file not found: {schema_path}")
        # Still create essential tables even without schema.sql
        pass
    else:
        # Only run schema.sql if it exists (usually for SQLite)
        if DB_TYPE == 'sqlite':
            import sqlite3
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
            finally:
                db.close()
        # For PostgreSQL, schema should be managed via migrations or manual setup
    
    # Create essential tables if they don't exist (works for both DB types)
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Check which tables exist (for debugging)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                rows = cursor.fetchall()
                existing_tables = []
                for row in rows:
                    if isinstance(row, dict):
                        existing_tables.append(row.get('table_name'))
                    elif isinstance(row, tuple):
                        existing_tables.append(row[0])
                    else:
                        existing_tables.append(str(row))
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                rows = cursor.fetchall()
                existing_tables = []
                for row in rows:
                    if isinstance(row, dict) and 'name' in row:
                        existing_tables.append(row['name'])
                    elif isinstance(row, tuple) and len(row) > 0:
                        existing_tables.append(row[0])
                    elif hasattr(row, '_fields') and 'name' in row._fields:
                        existing_tables.append(row['name'])
                    else:
                        # Handle sqlite3.Row objects - try dictionary access
                        try:
                            existing_tables.append(row['name'])
                        except (TypeError, KeyError, IndexError):
                            # Last fallback: try to get first element or convert to string
                            try:
                                existing_tables.append(row[0])
                            except:
                                existing_tables.append(str(row))
            print(f"📊 Existing tables: {existing_tables}")
            
            if DB_TYPE == 'postgresql':
                # Failed emails table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS failed_emails (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR NOT NULL,
                        password VARCHAR NOT NULL,
                        reason TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Password reset tokens table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR NOT NULL,
                        token VARCHAR UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        used INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_email ON password_reset_tokens(email)")
                
                # Error logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS error_logs (
                        id SERIAL PRIMARY KEY,
                        url VARCHAR,
                        method VARCHAR,
                        error_message TEXT,
                        stack_trace TEXT,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Activity logs table (PostgreSQL)
                if 'activity_logs' not in existing_tables:
                    print("Creating activity_logs table...")
                    cursor.execute("""
                        CREATE TABLE activity_logs (
                            id SERIAL PRIMARY KEY,
                            type VARCHAR NOT NULL,
                            description TEXT NOT NULL,
                            user_id INTEGER,
                            broker_id INTEGER,
                            amount DECIMAL(10, 2),
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_logs(type)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at)")
                    print("✅ Created activity_logs table")
                
                # Partner applications table (PostgreSQL)
                if 'partner_applications' not in existing_tables:
                    print("Creating partner_applications table...")
                    cursor.execute("""
                        CREATE TABLE partner_applications (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR NOT NULL,
                            email VARCHAR NOT NULL UNIQUE,
                            company VARCHAR,
                            commission_model VARCHAR DEFAULT 'bounty',
                            status VARCHAR DEFAULT 'pending',
                            applied_at TIMESTAMP DEFAULT NOW(),
                            created_at TIMESTAMP DEFAULT NOW(),
                            approved_at TIMESTAMP,
                            notes TEXT,
                            timestamp VARCHAR,
                            client_count VARCHAR,
                            message TEXT
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_partner_app_email ON partner_applications(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_partner_app_status ON partner_applications(status)")
                    print("✅ Created partner_applications table")
                else:
                    # Add missing columns if they don't exist (PostgreSQL)
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'partner_applications' 
                                AND column_name = 'created_at'
                            ) THEN
                                ALTER TABLE partner_applications ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
                                RAISE NOTICE 'Added created_at column';
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'partner_applications' 
                                AND column_name = 'applied_at'
                            ) THEN
                                ALTER TABLE partner_applications ADD COLUMN applied_at TIMESTAMP DEFAULT NOW();
                                RAISE NOTICE 'Added applied_at column';
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'partner_applications' 
                                AND column_name = 'commission_model'
                            ) THEN
                                ALTER TABLE partner_applications ADD COLUMN commission_model VARCHAR DEFAULT 'bounty';
                                RAISE NOTICE 'Added commission_model column';
                            END IF;
                            
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'partner_applications' 
                                AND column_name = 'company'
                            ) THEN
                                ALTER TABLE partner_applications ADD COLUMN company VARCHAR;
                                RAISE NOTICE 'Added company column';
                            END IF;
                        END $$;
                    """)
                    
                    # Update existing rows with current timestamp
                    cursor.execute("UPDATE partner_applications SET created_at = NOW() WHERE created_at IS NULL")
                    cursor.execute("UPDATE partner_applications SET applied_at = NOW() WHERE applied_at IS NULL")
                
                # Brokers table (PostgreSQL)
                if 'brokers' not in existing_tables:
                    print("Creating brokers table...")
                    cursor.execute("""
                        CREATE TABLE brokers (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR NOT NULL,
                            email VARCHAR NOT NULL UNIQUE,
                            company VARCHAR,
                            commission_model VARCHAR DEFAULT 'bounty',
                            referral_code VARCHAR UNIQUE,
                            status VARCHAR DEFAULT 'active',
                            approved_at TIMESTAMP DEFAULT NOW(),
                            total_referrals INTEGER DEFAULT 0,
                            total_earned DECIMAL(10, 2) DEFAULT 0
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brokers_email ON brokers(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brokers_referral_code ON brokers(referral_code)")
                    print("✅ Created brokers table")
            else:
                # SQLite tables
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS failed_emails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        password TEXT NOT NULL,
                        reason TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        token TEXT UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        used INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_token ON password_reset_tokens(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_reset_email ON password_reset_tokens(email)")
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS error_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT,
                        method TEXT,
                        error_message TEXT,
                        stack_trace TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Activity logs table (SQLite)
                if 'activity_logs' not in existing_tables:
                    print("Creating activity_logs table...")
                    cursor.execute("""
                        CREATE TABLE activity_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            type TEXT NOT NULL,
                            description TEXT NOT NULL,
                            user_id INTEGER,
                            broker_id INTEGER,
                            amount DECIMAL(10, 2),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_type ON activity_logs(type)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_logs(created_at)")
                    print("✅ Created activity_logs table")
                
                # Partner applications table (SQLite)
                if 'partner_applications' not in existing_tables:
                    print("Creating partner_applications table...")
                    cursor.execute("""
                        CREATE TABLE partner_applications (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            email TEXT NOT NULL UNIQUE,
                            company TEXT,
                            commission_model TEXT DEFAULT 'bounty',
                            status TEXT DEFAULT 'pending',
                            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            approved_at TIMESTAMP,
                            notes TEXT,
                            timestamp TEXT,
                            client_count TEXT,
                            message TEXT
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_partner_app_email ON partner_applications(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_partner_app_status ON partner_applications(status)")
                    print("✅ Created partner_applications table")
                    
                    # Insert sample data immediately after creation
                    try:
                        cursor.execute('''
                            INSERT OR IGNORE INTO partner_applications (name, email, company, commission_model, status)
                            VALUES 
                            ('John Smith', 'john@insurance.com', 'Smith Insurance', 'bounty', 'pending'),
                            ('Jane Doe', 'jane@consulting.com', 'Doe Consulting', 'recurring', 'pending'),
                            ('Bob Wilson', 'bob@brokerage.com', 'Wilson Brokerage', 'bounty', 'pending')
                        ''')
                        print("✅ Inserted 3 sample partner applications")
                    except Exception as e:
                        print(f"Note: Could not insert sample data: {e}")
                else:
                    # Add missing columns if they don't exist (SQLite)
                    try:
                        cursor.execute("ALTER TABLE partner_applications ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                        print("✅ Added created_at column to partner_applications")
                    except:
                        pass  # Column already exists
                    try:
                        cursor.execute("ALTER TABLE partner_applications ADD COLUMN applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                        print("✅ Added applied_at column to partner_applications")
                    except:
                        pass  # Column already exists
                    try:
                        cursor.execute("ALTER TABLE partner_applications ADD COLUMN commission_model TEXT DEFAULT 'bounty'")
                        print("✅ Added commission_model column to partner_applications")
                    except:
                        pass  # Column already exists
                    try:
                        cursor.execute("ALTER TABLE partner_applications ADD COLUMN company TEXT")
                        print("✅ Added company column to partner_applications")
                    except:
                        pass  # Column already exists
                    
                    # Update existing rows with current timestamp
                    cursor.execute("UPDATE partner_applications SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
                    cursor.execute("UPDATE partner_applications SET applied_at = CURRENT_TIMESTAMP WHERE applied_at IS NULL")
                
                # Brokers table (SQLite)
                if 'brokers' not in existing_tables:
                    print("Creating brokers table...")
                    cursor.execute("""
                        CREATE TABLE brokers (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            email TEXT NOT NULL UNIQUE,
                            company TEXT,
                            commission_model TEXT DEFAULT 'bounty',
                            referral_code TEXT UNIQUE,
                            status TEXT DEFAULT 'active',
                            approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            total_referrals INTEGER DEFAULT 0,
                            total_earned DECIMAL(10, 2) DEFAULT 0
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brokers_email ON brokers(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brokers_referral_code ON brokers(referral_code)")
                    print("✅ Created brokers table")
                
                # Create calculations table (SQLite)
                if 'calculations' not in existing_tables:
                    print("Creating calculations table...")
                    cursor.execute("""
                        CREATE TABLE calculations (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            state TEXT NOT NULL,
                            notice_date DATE NOT NULL,
                            calculation_date DATE NOT NULL,
                            preliminary_notice DATE,
                            lien_deadline DATE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calculations_created_at ON calculations(created_at)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calculations_state ON calculations(state)")
                    print("✅ Created calculations table")
                    
                    # Insert some sample calculations for testing
                    cursor.execute("""
                        INSERT INTO calculations (state, notice_date, calculation_date, preliminary_notice, lien_deadline)
                        VALUES 
                        ('CA', '2024-01-01', '2024-01-01', '2024-01-20', '2024-02-01'),
                        ('TX', '2024-01-02', '2024-01-02', '2024-01-22', '2024-02-02'),
                        ('FL', '2024-01-03', '2024-01-03', '2024-01-25', '2024-02-05')
                    """)
                    print("✅ Inserted sample calculations")
            
            if DB_TYPE == 'postgresql':
                # Create calculations table (PostgreSQL)
                if 'calculations' not in existing_tables:
                    print("Creating calculations table...")
                    cursor.execute("""
                        CREATE TABLE calculations (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER,
                            state VARCHAR NOT NULL,
                            notice_date DATE NOT NULL,
                            calculation_date DATE NOT NULL,
                            preliminary_notice DATE,
                            lien_deadline DATE,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calculations_created_at ON calculations(created_at)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_calculations_state ON calculations(state)")
                    print("✅ Created calculations table")
                    
                    # Insert some sample calculations for testing
                    cursor.execute("""
                        INSERT INTO calculations (state, notice_date, calculation_date, preliminary_notice, lien_deadline)
                        VALUES 
                        ('CA', '2024-01-01', '2024-01-01', '2024-01-20', '2024-02-01'),
                        ('TX', '2024-01-02', '2024-01-02', '2024-01-22', '2024-02-02'),
                        ('FL', '2024-01-03', '2024-01-03', '2024-01-25', '2024-02-05')
                    """)
                    print("✅ Inserted sample calculations")
            
            # Create triggers for SQLite
            if DB_TYPE == 'sqlite':
                # Check if users table exists before creating trigger
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                if cursor.fetchone():
                    # Trigger to log user signups (SQLite)
                    cursor.execute("""
                        CREATE TRIGGER IF NOT EXISTS log_user_signup
                        AFTER INSERT ON users
                        BEGIN
                            INSERT INTO activity_logs (type, description, user_id)
                            VALUES ('user_signup', 'New user signed up - ' || NEW.email, NEW.id);
                        END
                    """)
                
                # Trigger to log broker approvals (SQLite)
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS log_broker_approval
                    AFTER UPDATE ON partner_applications
                    WHEN NEW.status = 'approved' AND OLD.status != 'approved'
                    BEGIN
                        INSERT INTO activity_logs (type, description, broker_id)
                        VALUES ('broker_approved', 'Broker approved - ' || NEW.email, NEW.id);
                    END
                """)
            
            # Create PostgreSQL triggers
            if DB_TYPE == 'postgresql':
                # Check if users table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'users'
                    )
                """)
                if cursor.fetchone()[0]:
                    # Trigger function to log user signups (PostgreSQL)
                    cursor.execute("""
                        CREATE OR REPLACE FUNCTION log_user_signup()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            INSERT INTO activity_logs (type, description, user_id)
                            VALUES ('user_signup', 'New user signed up - ' || NEW.email, NEW.id);
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql;
                    """)
                    cursor.execute("""
                        DROP TRIGGER IF EXISTS log_user_signup ON users;
                        CREATE TRIGGER log_user_signup
                        AFTER INSERT ON users
                        FOR EACH ROW EXECUTE FUNCTION log_user_signup();
                    """)
                
                # Trigger function to log broker approvals (PostgreSQL)
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION log_broker_approval()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        IF NEW.status = 'approved' AND OLD.status != 'approved' THEN
                            INSERT INTO activity_logs (type, description, broker_id)
                            VALUES ('broker_approved', 'Broker approved - ' || NEW.email, NEW.id);
                        END IF;
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;
                """)
                cursor.execute("""
                    DROP TRIGGER IF EXISTS log_broker_approval ON partner_applications;
                    CREATE TRIGGER log_broker_approval
                    AFTER UPDATE ON partner_applications
                    FOR EACH ROW EXECUTE FUNCTION log_broker_approval();
                """)
            
            # Insert sample data if table is empty
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM partner_applications")
                    result = cursor.fetchone()
                    count = result['count'] if isinstance(result, dict) else (result[0] if isinstance(result, tuple) else 0)
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM partner_applications")
                    result = cursor.fetchone()
                    if isinstance(result, dict):
                        count = result.get('count', 0)
                    elif isinstance(result, tuple):
                        count = result[0] if len(result) > 0 else 0
                    elif hasattr(result, '_fields'):
                        count = result['count'] if 'count' in result._fields else 0
                    else:
                        count = 0
                
                if count == 0:
                    print("Inserting sample partner applications...")
                    try:
                        if DB_TYPE == 'postgresql':
                            cursor.execute('''
                                INSERT INTO partner_applications (name, email, company, commission_model, status)
                                VALUES 
                                ('John Smith', 'john@insurance.com', 'Smith Insurance', 'bounty', 'pending'),
                                ('Jane Doe', 'jane@consulting.com', 'Doe Consulting', 'recurring', 'pending'),
                                ('Bob Wilson', 'bob@brokerage.com', 'Wilson Brokerage', 'bounty', 'pending')
                                ON CONFLICT (email) DO NOTHING
                            ''')
                        else:
                            cursor.execute('''
                                INSERT OR IGNORE INTO partner_applications (name, email, company, commission_model, status)
                                VALUES 
                                ('John Smith', 'john@insurance.com', 'Smith Insurance', 'bounty', 'pending'),
                                ('Jane Doe', 'jane@consulting.com', 'Doe Consulting', 'recurring', 'pending'),
                                ('Bob Wilson', 'bob@brokerage.com', 'Wilson Brokerage', 'bounty', 'pending')
                            ''')
                        print(f"✅ Inserted sample data")
                    except Exception as insert_error:
                        print(f"⚠️ Could not insert sample data: {insert_error}")
                        # Table might already have data
                else:
                    print(f"⚠️ Table already has {count} rows, skipping sample data")
            except Exception as e:
                print(f"Note: Could not check/insert sample data: {e}")
            
            # Commit is handled automatically by context manager
            print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()

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
    
    # Email gate tracking - check if IP has exceeded free limit (PostgreSQL compatible)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create email_gate_tracking table if it doesn't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_gate_tracking (
                        id SERIAL PRIMARY KEY,
                        ip_address VARCHAR NOT NULL,
                        email VARCHAR,
                        calculation_count INTEGER DEFAULT 1,
                        first_calculation_at TIMESTAMP DEFAULT NOW(),
                        last_calculation_at TIMESTAMP DEFAULT NOW(),
                        email_captured_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_ip ON email_gate_tracking(ip_address)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_email ON email_gate_tracking(email)")
                
                # Check if IP has exceeded free limit without providing email
                cursor.execute("""
                    SELECT calculation_count, email, email_captured_at 
                    FROM email_gate_tracking 
                    WHERE ip_address = %s 
                    ORDER BY last_calculation_at DESC 
                    LIMIT 1
                """, (client_ip,))
            else:
                cursor.execute("""
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
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_ip ON email_gate_tracking(ip_address)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_email ON email_gate_tracking(email)")
                
                cursor.execute("""
                    SELECT calculation_count, email, email_captured_at 
                    FROM email_gate_tracking 
                    WHERE ip_address = ? 
                    ORDER BY last_calculation_at DESC 
                    LIMIT 1
                """, (client_ip,))
            
            tracking = cursor.fetchone()
            
            if tracking:
                # Handle different row formats
                if isinstance(tracking, dict):
                    count = tracking.get('calculation_count', 0)
                    email = tracking.get('email')
                elif hasattr(tracking, 'keys'):
                    count = tracking['calculation_count'] if 'calculation_count' in tracking.keys() else tracking[0]
                    email = tracking['email'] if 'email' in tracking.keys() else (tracking[1] if len(tracking) > 1 else None)
                else:
                    count = tracking[0] if tracking else 0
                    email = tracking[1] if tracking and len(tracking) > 1 else None
                
                # TEMPORARY: Disable backend 403 blocking - let frontend handle the flow
                # Frontend will show modals at calculation 3 and 6
                # if not email and count >= 3:
                #     raise HTTPException(
                #         status_code=403,
                #         detail="Free trial limit reached. Please provide your email for 3 more calculations."
                #     )
                
                # if email and count >= 6:
                #     raise HTTPException(
                #         status_code=403,
                #         detail="Free trial limit reached (6 calculations). Upgrade to unlimited for $299/month."
                #     )
                
                # Log for debugging
                if not email and count >= 3:
                    print(f"⚠️ User at calculation {count} without email - frontend will handle modal")
                if email and count >= 6:
                    print(f"⚠️ User at calculation {count} with email - frontend will handle upgrade modal")
                
                # Update count
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE email_gate_tracking 
                        SET calculation_count = calculation_count + 1,
                            last_calculation_at = NOW()
                        WHERE ip_address = %s
                    """, (client_ip,))
                else:
                    cursor.execute("""
                        UPDATE email_gate_tracking 
                        SET calculation_count = calculation_count + 1,
                            last_calculation_at = CURRENT_TIMESTAMP
                        WHERE ip_address = ?
                    """, (client_ip,))
            else:
                # First calculation from this IP
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        INSERT INTO email_gate_tracking (ip_address, calculation_count)
                        VALUES (%s, 1)
                    """, (client_ip,))
                else:
                    cursor.execute("""
                        INSERT INTO email_gate_tracking (ip_address, calculation_count)
                        VALUES (?, 1)
                    """, (client_ip,))
            
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in email gate tracking: {e}")
        import traceback
        traceback.print_exc()
        # Continue with calculation even if tracking fails
    
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
    
    # Track page view and calculation (non-blocking, PostgreSQL compatible)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Format dates for database
            today_str = date.today().isoformat()
            prelim_date_str = prelim_deadline.date().isoformat()
            lien_date_str = lien_deadline.date().isoformat()
            notice_date_str = delivery_date.date().isoformat()
            
            # Create tables if they don't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS page_views (
                        id SERIAL PRIMARY KEY,
                        date VARCHAR NOT NULL,
                        ip VARCHAR NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calculations (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER,
                        state VARCHAR NOT NULL,
                        notice_date DATE NOT NULL,
                        calculation_date DATE NOT NULL,
                        preliminary_notice DATE,
                        lien_deadline DATE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id SERIAL PRIMARY KEY,
                        date VARCHAR NOT NULL,
                        amount DECIMAL(10, 2) NOT NULL,
                        customer_email VARCHAR,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Insert page view
                client_ip = request.client.host if request and request.client else "unknown"
                cursor.execute(
                    "INSERT INTO page_views(date, ip) VALUES (%s, %s)",
                    (today_str, client_ip)
                )
                
                # Insert calculation with detailed dates (PostgreSQL)
                cursor.execute('''
                    INSERT INTO calculations 
                    (state, notice_date, calculation_date, preliminary_notice, lien_deadline)
                    VALUES (%s, %s, %s, %s, %s)
                ''', (
                    state_code,
                    notice_date_str,
                    today_str,
                    prelim_date_str,
                    lien_date_str
                ))
                
                print(f"✅ Calculation saved to PostgreSQL: {state_code} - Notice: {notice_date_str}, Prelim: {prelim_date_str}, Lien: {lien_date_str}")
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS page_views (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        ip TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS calculations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        state TEXT NOT NULL,
                        notice_date DATE NOT NULL,
                        calculation_date DATE NOT NULL,
                        preliminary_notice DATE,
                        lien_deadline DATE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        amount REAL NOT NULL,
                        customer_email TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Insert page view
                client_ip = request.client.host if request and request.client else "unknown"
                cursor.execute(
                    "INSERT INTO page_views(date, ip) VALUES (?, ?)",
                    (today_str, client_ip)
                )
                
                # Insert calculation with detailed dates (SQLite)
                cursor.execute('''
                    INSERT INTO calculations 
                    (state, notice_date, calculation_date, preliminary_notice, lien_deadline)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    state_code,
                    notice_date_str,
                    today_str,
                    prelim_date_str,
                    lien_date_str
                ))
                
                print(f"✅ Calculation saved to SQLite: {state_code} - Notice: {notice_date_str}, Prelim: {prelim_date_str}, Lien: {lien_date_str}")
            
            conn.commit()
    except Exception as e:
        # Don't fail the request if tracking fails
        print(f"⚠️ Could not save calculation: {e}")
        import traceback
        traceback.print_exc()
        # Continue even if saving fails
    
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
@app.post("/api/v1/apply-partner")
async def apply_partner(request: Request):
    """Handle partner application submissions"""
    print("=" * 60)
    print("🎯 PARTNER APPLICATION RECEIVED")
    print("=" * 60)
    
    try:
        data = await request.json()
        print(f"📝 Form data received: {data}")
        
        name = data.get('name')
        email = data.get('email')
        company = data.get('company')
        phone = data.get('phone')
        client_count = data.get('client_count')
        commission_model = data.get('commission_model')
        message = data.get('message', '')
        
        print(f"👤 Name: {name}")
        print(f"📧 Email: {email}")
        print(f"🏢 Company: {company}")
        print(f"📞 Phone: {phone}")
        print(f"💰 Commission: {commission_model}")
        
        # Validate required fields
        if not name or not email or not company or not client_count or not commission_model:
            print("❌ VALIDATION FAILED: Missing required fields")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Missing required fields"}
            )
        
        # Insert into database
        print("💾 Attempting database insert...")
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create table if it doesn't exist (with phone field)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS partner_applications (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        email VARCHAR NOT NULL,
                        company VARCHAR NOT NULL,
                        phone VARCHAR,
                        client_count VARCHAR,
                        commission_model VARCHAR DEFAULT 'bounty',
                        message TEXT,
                        timestamp VARCHAR NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        status VARCHAR DEFAULT 'pending'
                    )
                """)
                # Add phone column if it doesn't exist (PostgreSQL)
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 
                            FROM information_schema.columns 
                            WHERE table_name = 'partner_applications' 
                            AND column_name = 'phone'
                        ) THEN
                            ALTER TABLE partner_applications ADD COLUMN phone VARCHAR;
                        END IF;
                    END $$;
                """)
                # Add commission_model column if it doesn't exist (PostgreSQL)
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 
                            FROM information_schema.columns 
                            WHERE table_name = 'partner_applications' 
                            AND column_name = 'commission_model'
                        ) THEN
                            ALTER TABLE partner_applications ADD COLUMN commission_model VARCHAR DEFAULT 'bounty';
                        END IF;
                    END $$;
                """)
                # Update existing records
                cursor.execute("UPDATE partner_applications SET commission_model = 'bounty' WHERE commission_model IS NULL")
                
                # Ensure email has unique constraint for UPSERT
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_constraint 
                                WHERE conname = 'partner_applications_email_key'
                            ) THEN
                                ALTER TABLE partner_applications ADD CONSTRAINT partner_applications_email_key UNIQUE (email);
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass  # Constraint might already exist
                
                # UPSERT: Insert or update on email conflict (PostgreSQL)
                timestamp = datetime.now().isoformat()
                sql = """
                    INSERT INTO partner_applications
                      (name, email, company, phone, client_count, commission_model, message, timestamp, status)
                    VALUES
                      (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT (email)
                    DO UPDATE SET
                      name = EXCLUDED.name,
                      company = EXCLUDED.company,
                      phone = EXCLUDED.phone,
                      client_count = EXCLUDED.client_count,
                      commission_model = EXCLUDED.commission_model,
                      message = EXCLUDED.message,
                      timestamp = EXCLUDED.timestamp,
                      status = 'pending',
                      approved_at = NULL,
                      referral_link = NULL
                    RETURNING id
                """
                cursor.execute(sql, (name, email, company, phone, client_count, commission_model, message, timestamp))
                result = cursor.fetchone()
                application_id = result['id'] if isinstance(result, dict) else (result[0] if result else None)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS partner_applications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        company TEXT NOT NULL,
                        phone TEXT,
                        client_count TEXT,
                        commission_model TEXT DEFAULT 'bounty',
                        message TEXT,
                        timestamp TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending'
                    )
                """)
                # Add phone column if it doesn't exist (SQLite)
                try:
                    cursor.execute("ALTER TABLE partner_applications ADD COLUMN phone TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                # Add commission_model column if it doesn't exist (SQLite)
                try:
                    cursor.execute("ALTER TABLE partner_applications ADD COLUMN commission_model TEXT DEFAULT 'bounty'")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                # Update existing records
                cursor.execute("UPDATE partner_applications SET commission_model = 'bounty' WHERE commission_model IS NULL")
                
                # Ensure email has unique constraint for UPSERT (SQLite)
                try:
                    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_partner_applications_email ON partner_applications(email)")
                except Exception:
                    pass  # Index might already exist
                
                # UPSERT: Insert or replace on email conflict (SQLite)
                timestamp = datetime.now().isoformat()
                # First try to update existing record
                cursor.execute("""
                    UPDATE partner_applications 
                    SET name = ?, company = ?, phone = ?, client_count = ?, 
                        commission_model = ?, message = ?, timestamp = ?, 
                        status = 'pending', approved_at = NULL, referral_link = NULL
                    WHERE email = ?
                """, (name, company, phone, client_count, commission_model, message, timestamp, email))
                
                if cursor.rowcount == 0:
                    # No existing record, insert new one
                    sql = """
                        INSERT INTO partner_applications 
                        (name, email, company, phone, client_count, commission_model, message, timestamp, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                    """
                    cursor.execute(sql, (name, email, company, phone, client_count, commission_model, message, timestamp))
                    application_id = cursor.lastrowid
                else:
                    # Get the ID of the updated record
                    cursor.execute("SELECT id FROM partner_applications WHERE email = ?", (email,))
                    result = cursor.fetchone()
                    application_id = result[0] if result else None
            
            conn.commit()
            
        print(f"✅ Partner application saved with ID: {application_id}")
        print("=" * 60)
        
        return {
            "status": "success",
            "message": "Application submitted successfully",
            "application_id": application_id
        }
        
    except Exception as e:
        print(f"❌ ERROR saving partner application: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

@app.post("/api/v1/capture-email")
@limiter.limit("5/minute")
async def capture_email(request: Request):
    """Capture email from calculator gate"""
    from fastapi.responses import JSONResponse
    
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()
        
        # Basic validation
        if not email:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Email is required"}
            )
        
        if '@' not in email or '.' not in email.split('@')[-1]:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Invalid email format"}
            )
        
        # Check disposable domains (optional)
        disposable_domains = ['tempmail.com', 'throwaway.email', 'mailinator.com']
        domain = email.split('@')[1]
        if any(disposable in domain for disposable in disposable_domains):
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Disposable emails not allowed"}
            )
        
        # Save to database
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Create email_captures table if it doesn't exist
            if DB_TYPE == 'postgresql':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS email_captures (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR NOT NULL UNIQUE,
                        ip_address VARCHAR,
                        user_agent TEXT,
                        calculation_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                ''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_captures_email ON email_captures(email)")
                
                # Insert or update (PostgreSQL)
                cursor.execute('''
                    INSERT INTO email_captures 
                    (email, ip_address, user_agent, calculation_count)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET
                        calculation_count = EXCLUDED.calculation_count,
                        ip_address = EXCLUDED.ip_address,
                        user_agent = EXCLUDED.user_agent
                ''', (
                    email,
                    request.client.host,
                    request.headers.get('user-agent', ''),
                    3  # Give them 3 more calculations
                ))
            else:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS email_captures (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL UNIQUE,
                        ip_address TEXT,
                        user_agent TEXT,
                        calculation_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_captures_email ON email_captures(email)")
                
                # Insert or update (SQLite)
                cursor.execute('''
                    INSERT OR REPLACE INTO email_captures 
                    (email, ip_address, user_agent, calculation_count)
                    VALUES (?, ?, ?, ?)
                ''', (
                    email,
                    request.client.host,
                    request.headers.get('user-agent', ''),
                    3  # Give them 3 more calculations
                ))
        
        print(f"✅ Email captured: {email}")
        
        return {
            "status": "success",
            "message": "Email saved! You have 3 more calculations.",
            "calculations_remaining": 3
        }
        
    except Exception as e:
        print(f"❌ Error capturing email: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Internal server error"}
        )

# UTM tracking endpoint
class UTMTrackingRequest(BaseModel):
    source: str = None
    medium: str = None
    campaign: str = None
    term: str = None
    content: str = None
    timestamp: str

@app.post("/api/v1/track-utm")
async def track_utm(request: Request, utm_data: UTMTrackingRequest):
    """Track UTM parameters for marketing attribution - PostgreSQL compatible"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create utm_tracking table if it doesn't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS utm_tracking (
                        id SERIAL PRIMARY KEY,
                        ip_address VARCHAR NOT NULL,
                        utm_source VARCHAR,
                        utm_medium VARCHAR,
                        utm_campaign VARCHAR,
                        utm_term VARCHAR,
                        utm_content VARCHAR,
                        timestamp VARCHAR NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_utm_ip ON utm_tracking(ip_address)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_utm_source ON utm_tracking(utm_source)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_utm_campaign ON utm_tracking(utm_campaign)")
                
                client_ip = get_client_ip(request)
                
                # Insert UTM data (PostgreSQL)
                cursor.execute("""
                    INSERT INTO utm_tracking 
                    (ip_address, utm_source, utm_medium, utm_campaign, utm_term, utm_content, timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    client_ip,
                    utm_data.source,
                    utm_data.medium,
                    utm_data.campaign,
                    utm_data.term,
                    utm_data.content,
                    utm_data.timestamp
                ))
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS utm_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        utm_source TEXT,
                        utm_medium TEXT,
                        utm_campaign TEXT,
                        utm_term TEXT,
                        utm_content TEXT,
                        timestamp TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_utm_ip ON utm_tracking(ip_address)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_utm_source ON utm_tracking(utm_source)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_utm_campaign ON utm_tracking(utm_campaign)")
                
                client_ip = get_client_ip(request)
                
                # Insert UTM data (SQLite)
                cursor.execute("""
                    INSERT INTO utm_tracking 
                    (ip_address, utm_source, utm_medium, utm_campaign, utm_term, utm_content, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    client_ip,
                    utm_data.source,
                    utm_data.medium,
                    utm_data.campaign,
                    utm_data.term,
                    utm_data.content,
                    utm_data.timestamp
                ))
            
            conn.commit()
            print(f"📊 UTM tracked: source={utm_data.source}, medium={utm_data.medium}, campaign={utm_data.campaign} from IP: {client_ip}")
        
        return {"status": "success", "message": "UTM parameters tracked"}
    except Exception as e:
        print(f"❌ UTM tracking error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

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

# Fraud Detection Functions
def check_fraud_signals(broker_id: str, customer_email: str, customer_stripe_id: str, session_data: dict):
    """
    Multi-layer fraud detection for broker referrals.
    Returns: (fraud_flags: list, risk_score: int, should_flag: bool)
    """
    flags = []
    risk_score = 0
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get broker info
            cursor.execute("""
                SELECT email, stripe_customer_id, created_at, ip_address 
                FROM brokers 
                WHERE referral_code = ?
            """, (broker_id,))
            broker = cursor.fetchone()
            
            if not broker:
                return [], 0, False
            
            broker_email = broker[0]
            broker_stripe_id = broker[1] if len(broker) > 1 else None
            broker_created = broker[2] if len(broker) > 2 else None
            broker_ip = broker[3] if len(broker) > 3 else None
            
            # LAYER 1: Payment Method Check (Strongest) ⭐⭐⭐
            if broker_stripe_id and customer_stripe_id:
                # Check if same Stripe customer (catches shared payment methods)
                if broker_stripe_id == customer_stripe_id:
                    flags.append('SAME_STRIPE_CUSTOMER')
                    risk_score += 50  # Critical flag
            
            # LAYER 2: Email Similarity Check ⭐⭐
            broker_base = broker_email.split('@')[0].lower()
            customer_base = customer_email.split('@')[0].lower()
            broker_domain = broker_email.split('@')[1].lower()
            customer_domain = customer_email.split('@')[1].lower()
            
            # Check for similar usernames
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, broker_base, customer_base).ratio()
            
            if similarity > 0.8:  # 80% similar
                flags.append('SIMILAR_EMAIL')
                risk_score += 30
            
            # Check for sequential numbers (john1@, john2@)
            import re
            broker_no_nums = re.sub(r'\d+', '', broker_base)
            customer_no_nums = re.sub(r'\d+', '', customer_base)
            if broker_no_nums == customer_no_nums:
                flags.append('SEQUENTIAL_EMAIL')
                risk_score += 25
            
            # Same domain (company.com)
            if broker_domain == customer_domain and broker_domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']:
                flags.append('SAME_COMPANY_DOMAIN')
                risk_score += 20
            
            # LAYER 3: Timing Analysis ⭐⭐
            if broker_created:
                from datetime import datetime
                try:
                    broker_created_dt = datetime.fromisoformat(broker_created.replace('Z', '+00:00'))
                    signup_time = datetime.now()
                    time_diff = (signup_time - broker_created_dt.replace(tzinfo=None)).total_seconds() / 3600  # hours
                    
                    if time_diff < 1:  # Signup within 1 hour
                        flags.append('IMMEDIATE_SIGNUP')
                        risk_score += 35
                    elif time_diff < 24:  # Within 24 hours
                        flags.append('FAST_SIGNUP')
                        risk_score += 15
                except:
                    pass
            
            # LAYER 4: IP Address Check (if available)
            customer_ip = session_data.get('customer_details', {}).get('ip_address')
            if broker_ip and customer_ip and broker_ip == customer_ip:
                flags.append('SAME_IP')
                risk_score += 40
            
            # LAYER 5: Stripe Risk Evaluation (if available)
            stripe_risk = session_data.get('payment_intent', {}).get('charges', {}).get('data', [{}])[0].get('outcome', {}).get('risk_level')
            if stripe_risk in ['elevated', 'highest']:
                flags.append(f'STRIPE_RISK_{stripe_risk.upper()}')
                risk_score += 30 if stripe_risk == 'elevated' else 50
            
            # LAYER 6: Check for multiple referrals from same broker
            cursor.execute("""
                SELECT COUNT(*) 
                FROM referrals 
                WHERE broker_id = ? AND created_at < datetime('now', '-7 days')
            """, (broker_id,))
            referral_count = cursor.fetchone()[0]
            
            if referral_count == 0:
                # First referral = more scrutiny
                flags.append('FIRST_REFERRAL')
                risk_score += 10
            
            # LAYER 7: Email Age Check (new Gmail accounts are suspicious)
            # Note: This requires external API, skip for now or add later
            
            # LAYER 8: Device Fingerprint (if available)
            # Note: Requires frontend implementation, skip for now
            
            # Determine if should flag for manual review
            should_flag = risk_score >= 50 or 'SAME_STRIPE_CUSTOMER' in flags
            
            return flags, risk_score, should_flag
            
    except Exception as e:
        print(f"❌ Fraud check error: {e}")
        import traceback
        traceback.print_exc()
        return ['ERROR_DURING_CHECK'], 0, False


def send_admin_fraud_alert(broker_email: str, customer_email: str, flags: list, risk_score: int):
    """Send admin alert for flagged referrals"""
    print(f"""
    🚨 FRAUD ALERT 🚨
    Broker: {broker_email}
    Customer: {customer_email}
    Risk Score: {risk_score}
    Flags: {', '.join(flags)}
    
    Review at: https://liendeadline.com/admin-dashboard
    """)
    # TODO: Send email/Slack notification in production


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
        # New subscription
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            
            email = session.get('customer_details', {}).get('email')
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            
            if not email:
                print("⚠️ No email in checkout session")
                return {"status": "skipped"}
            
            # Get referral code from Stripe metadata (client_reference_id)
            referral_code = session.get('client_reference_id', 'direct')
            
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
                
                # CRITICAL: Send welcome email and track failures
                email_sent = send_welcome_email(email, temp_password)
                
                if email_sent:
                    print(f"✅ Welcome email sent to {email}")
                else:
                    print(f"⚠️ Welcome email failed for {email}. Temp password: {temp_password}")
                    # Log to failed_emails table for manual follow-up
                    try:
                        db.execute("""
                            CREATE TABLE IF NOT EXISTS failed_emails (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                email TEXT NOT NULL,
                                password TEXT NOT NULL,
                                reason TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        db.execute("""
                            INSERT INTO failed_emails (email, password, reason)
                            VALUES (?, ?, 'Welcome email send failed')
                        """, (email, temp_password))
                        db.commit()
                        print(f"⚠️ Failed email logged to database for manual follow-up")
                    except Exception as e:
                        print(f"❌ Failed to log failed email: {e}")
                
                # If referral exists, create pending commission
                if referral_code.startswith('broker_'):
                    broker = db.execute(
                        "SELECT * FROM brokers WHERE referral_code = ?", 
                        (referral_code,)
                    ).fetchone()
                    
                    if broker:
                        # Create referrals table if it doesn't exist (with fraud detection fields)
                        db.execute("""
                            CREATE TABLE IF NOT EXISTS referrals (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                broker_id TEXT NOT NULL,
                                broker_email TEXT NOT NULL,
                                customer_email TEXT NOT NULL,
                                customer_stripe_id TEXT,
                                amount DECIMAL(10,2) NOT NULL,
                                payout DECIMAL(10,2) NOT NULL,
                                payout_type TEXT NOT NULL,
                                status TEXT DEFAULT 'on_hold',
                                fraud_flags TEXT,
                                hold_until DATE,
                                clawback_until DATE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                paid_at TIMESTAMP,
                                FOREIGN KEY (broker_id) REFERENCES brokers(referral_code)
                            )
                        """)
                        db.execute("CREATE INDEX IF NOT EXISTS idx_referral_status ON referrals(status)")
                        db.execute("CREATE INDEX IF NOT EXISTS idx_referral_broker ON referrals(broker_id)")
                        
                        # Determine payout based on broker's commission model
                        commission_model = broker.get('commission_model', 'bounty')
                        if commission_model == 'recurring':
                            payout_amount = 50.00
                            payout_type = 'recurring'
                        else:
                            payout_amount = 500.00
                            payout_type = 'bounty'
                        
                        # RUN FRAUD DETECTION
                        fraud_flags, risk_score, should_flag = check_fraud_signals(
                            referral_code, 
                            email, 
                            customer_id,
                            session
                        )
                        
                        # Calculate hold dates
                        from datetime import datetime, timedelta
                        hold_until = datetime.now() + timedelta(days=30)
                        clawback_until = datetime.now() + timedelta(days=90)
                        
                        # Determine status
                        status = 'flagged_for_review' if should_flag else 'on_hold'
                        
                        # Store referral with fraud data
                        db.execute("""
                            INSERT INTO referrals 
                            (broker_id, broker_email, customer_email, customer_stripe_id,
                             amount, payout, payout_type, status, fraud_flags, 
                             hold_until, clawback_until, created_at)
                            VALUES (?, ?, ?, ?, 299.00, ?, ?, ?, ?, ?, ?, datetime('now'))
                        """, (
                            broker['referral_code'],
                            broker['email'],
                            email,
                            customer_id,
                            payout_amount,
                            payout_type,
                            status,
                            json.dumps({'flags': fraud_flags, 'risk_score': risk_score}),
                            hold_until,
                            clawback_until
                        ))
                        
                        # Update broker pending count
                        db.execute("""
                            UPDATE brokers 
                            SET pending_commissions = pending_commissions + 1 
                            WHERE referral_code = ?
                        """, (referral_code,))
                        
                        db.commit()
                        
                        print(f"✓ Referral tracked: {email} → {broker['email']} (${payout_amount} {payout_type} {status})")
                        print(f"   Risk Score: {risk_score}, Flags: {fraud_flags}")
                        
                        # Send alerts
                        if should_flag:
                            print(f"🚨 FLAGGED FOR REVIEW: {referral_code}")
                            send_admin_fraud_alert(broker['email'], email, fraud_flags, risk_score)
                        else:
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
            
            # Check if this was a referral that should be clawed back
            cursor = db.cursor()
            
            # Find referral
            cursor.execute("""
                SELECT id, payout, status, created_at
                FROM referrals
                WHERE customer_stripe_id = ?
                  AND status IN ('on_hold', 'ready', 'paid')
            """, (customer_id,))
            
            referral = cursor.fetchone()
            
            if referral:
                from datetime import datetime
                created = datetime.fromisoformat(referral[3])
                days_active = (datetime.now() - created).days
                
                # If cancelled before 90 days, claw back
                if days_active < 90:
                    cursor.execute("""
                        UPDATE referrals
                        SET status = 'clawed_back',
                            notes = 'Customer cancelled before 90 days'
                        WHERE id = ?
                    """, (referral[0],))
                    
                    print(f"🚨 CLAWBACK: Referral {referral[0]} cancelled after {days_active} days")
            
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

def send_welcome_email(email: str, temp_password: str):
    """Send welcome email with login credentials"""
    try:
        # Try SendGrid first (if configured)
        sendgrid_key = os.getenv('SENDGRID_API_KEY')
        if sendgrid_key:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To
            
            sg = SendGridAPIClient(api_key=sendgrid_key)
            
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
                    <h1 style="margin: 0;">Welcome to LienDeadline! 🎉</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Your account is ready to protect your receivables</p>
                </div>
                
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h2 style="color: #1e293b; margin-top: 0;">Your Login Credentials</h2>
                    <p style="margin: 10px 0;"><strong>Email:</strong> {email}</p>
                    <p style="margin: 10px 0;"><strong>Temporary Password:</strong> <code style="background: white; padding: 5px 10px; border-radius: 4px; font-size: 16px;">{temp_password}</code></p>
                    <p style="margin: 20px 0 0 0;">
                        <a href="https://liendeadline.com/dashboard.html" style="display: inline-block; background: #c1554e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                            Login to Dashboard →
                        </a>
                    </p>
                </div>
                
                <div style="margin: 30px 0;">
                    <h3 style="color: #1e293b;">What's Next?</h3>
                    <ul style="color: #475569; line-height: 1.8;">
                        <li>Change your password in Account Settings</li>
                        <li>Run <strong>unlimited</strong> lien deadline calculations</li>
                        <li>View your calculation history anytime</li>
                        <li>Save calculations as PDF (coming soon)</li>
                    </ul>
                </div>
                
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <p style="margin: 0; color: #92400e;"><strong>Pro Tip:</strong> Bookmark the calculator page for instant access when you need to check deadlines.</p>
                </div>
                
                <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e2e8f0; margin-top: 30px;">
                    <p style="color: #64748b; font-size: 14px; margin: 0;">
                        Questions? Just reply to this email.<br>
                        Thank you for trusting LienDeadline to protect your receivables.
                    </p>
                </div>
            </body>
            </html>
            """
            
            message = Mail(
                from_email=Email("support@liendeadline.com"),
                to_emails=To(email),
                subject="🎉 Welcome to LienDeadline - Your Account is Ready",
                html_content=html
            )
            
            sg.send(message)
            print(f"✅ Welcome email sent to {email}")
            return True
        else:
            # Fallback: Try SMTP if SendGrid not configured
            smtp_email = os.getenv('SMTP_EMAIL')
            # Remove spaces from Gmail app password (Railway may store as "xxxx xxxx xxxx xxxx")
            smtp_password = (os.getenv('SMTP_PASSWORD') or "").replace(" ", "")
            
            if smtp_email and smtp_password:
                import smtplib
                from email.mime.text import MIMEText
                from email.mime.multipart import MIMEMultipart
                
                msg = MIMEMultipart('alternative')
                msg['Subject'] = '🎉 Welcome to LienDeadline - Your Account is Ready'
                msg['From'] = smtp_email
                msg['To'] = email
                
                html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
                        <h1 style="margin: 0;">Welcome to LienDeadline! 🎉</h1>
                        <p style="margin: 10px 0 0 0; opacity: 0.9;">Your account is ready to protect your receivables</p>
                    </div>
                    
                    <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h2 style="color: #1e293b; margin-top: 0;">Your Login Credentials</h2>
                        <p style="margin: 10px 0;"><strong>Email:</strong> {email}</p>
                        <p style="margin: 10px 0;"><strong>Temporary Password:</strong> <code style="background: white; padding: 5px 10px; border-radius: 4px; font-size: 16px;">{temp_password}</code></p>
                        <p style="margin: 20px 0 0 0;">
                            <a href="https://liendeadline.com/dashboard.html" style="display: inline-block; background: #c1554e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                                Login to Dashboard →
                            </a>
                        </p>
                    </div>
                    
                    <div style="margin: 30px 0;">
                        <h3 style="color: #1e293b;">What's Next?</h3>
                        <ul style="color: #475569; line-height: 1.8;">
                            <li>Change your password in Account Settings</li>
                            <li>Run <strong>unlimited</strong> lien deadline calculations</li>
                            <li>View your calculation history anytime</li>
                            <li>Save calculations as PDF (coming soon)</li>
                        </ul>
                    </div>
                    
                    <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px; margin: 20px 0;">
                        <p style="margin: 0; color: #92400e;"><strong>Pro Tip:</strong> Bookmark the calculator page for instant access when you need to check deadlines.</p>
                    </div>
                    
                    <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e2e8f0; margin-top: 30px;">
                        <p style="color: #64748b; font-size: 14px; margin: 0;">
                            Questions? Just reply to this email.<br>
                            Thank you for trusting LienDeadline to protect your receivables.
                        </p>
                    </div>
                </body>
                </html>
                """
                
                msg.attach(MIMEText(html, 'html'))
                
                # Try Gmail SMTP
                try:
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(smtp_email, smtp_password)
                        server.send_message(msg)
                    print(f"✅ Welcome email sent via SMTP to {email}")
                    return True
                except Exception as smtp_error:
                    print(f"⚠️ SMTP failed: {smtp_error}")
            
            # If no email service configured, just log
            print(f"⚠️ No email service configured - skipping email to {email}")
            print(f"   Temporary password: {temp_password}")
            print(f"   Email: {email}")
            return False
            
    except Exception as e:
        print(f"❌ Welcome email failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_broker_welcome_email(email: str, name: str, link: str, code: str):
    """Send broker welcome email with referral link"""
    try:
        sendgrid_key = os.getenv('SENDGRID_API_KEY')
        if sendgrid_key:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To
            
            sg = SendGridAPIClient(api_key=sendgrid_key)
            
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
                    <h1 style="margin: 0;">Welcome to LienDeadline Partner Program! 🎉</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Start earning commissions today</p>
                </div>
                
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h2 style="color: #1e293b; margin-top: 0;">Congratulations, {name}!</h2>
                    <p style="color: #475569; line-height: 1.8;">Your partner account is now active. Share your referral link with construction clients and start earning commissions.</p>
                </div>
                
                <div style="background: white; border: 2px solid #e2e8f0; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #1e293b; margin-top: 0;">Your Referral Details</h3>
                    <p style="margin: 10px 0;"><strong>Referral Code:</strong> <code style="background: #f1f5f9; padding: 5px 10px; border-radius: 4px; font-size: 16px;">{code}</code></p>
                    <p style="margin: 10px 0;"><strong>Referral Link:</strong></p>
                    <p style="margin: 10px 0;">
                        <a href="{link}" style="color: #2563eb; word-break: break-all;">{link}</a>
                    </p>
                </div>
                
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <h3 style="color: #92400e; margin-top: 0;">💰 Commission Structure</h3>
                    <ul style="color: #92400e; line-height: 1.8; margin: 0;">
                        <li><strong>$500 one-time</strong> per signup (bounty model)</li>
                        <li><strong>$50/month recurring</strong> per active subscriber (recurring model)</li>
                        <li>Commissions paid after 30-day customer retention period</li>
                    </ul>
                </div>
                
                <div style="margin: 30px 0;">
                    <h3 style="color: #1e293b;">How It Works</h3>
                    <ol style="color: #475569; line-height: 1.8;">
                        <li>Share your referral link with construction clients</li>
                        <li>When they sign up for LienDeadline Pro ($299/month), you earn a commission</li>
                        <li>Track all referrals in your dashboard</li>
                        <li>Get paid monthly via PayPal or bank transfer</li>
                    </ol>
                </div>
                
                <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e2e8f0; margin-top: 30px;">
                    <a href="https://liendeadline.com/broker-dashboard" style="display: inline-block; background: #c1554e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-bottom: 15px;">
                        View Your Dashboard →
                    </a>
                    <p style="color: #64748b; font-size: 14px; margin: 0;">
                        Questions? Reply to this email or contact partners@liendeadline.com
                    </p>
                </div>
            </body>
            </html>
            """
            
            message = Mail(
                from_email=Email("partners@liendeadline.com"),
                to_emails=To(email),
                subject="🎉 Welcome to LienDeadline Partner Program!",
                html_content=html
            )
            
            sg.send(message)
            print(f"✅ Broker welcome email sent to {email}")
            return True
        else:
            # Fallback: log it
            print(f"""
            ===== BROKER WELCOME EMAIL =====
            To: {email}
            Subject: Welcome to LienDeadline Partner Program!
            
            Congrats {name}!
            
            Your referral link: {link}
            Your referral code: {code}
            
            Share this link with construction clients.
            You earn $500 per signup (after 30 days).
            
            Track referrals: https://liendeadline.com/broker-dashboard
            ================================
            """)
            return False
            
    except Exception as e:
        print(f"Error sending broker email: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_broker_notification(broker_email: str, customer_email: str):
    """Notify broker of new referral"""
    try:
        sendgrid_key = os.getenv('SENDGRID_API_KEY')
        if sendgrid_key:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To
            
            sg = SendGridAPIClient(api_key=sendgrid_key)
            
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
                    <h1 style="margin: 0;">💰 New Referral! 🎉</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">You just earned a commission</p>
                </div>
                
                <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h2 style="color: #1e293b; margin-top: 0;">Congratulations!</h2>
                    <p style="color: #475569; line-height: 1.8;">Your referral just signed up for LienDeadline Pro.</p>
                </div>
                
                <div style="background: white; border: 2px solid #e2e8f0; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #1e293b; margin-top: 0;">Referral Details</h3>
                    <p style="margin: 10px 0;"><strong>Customer Email:</strong> {customer_email}</p>
                    <p style="margin: 10px 0;"><strong>Plan:</strong> Professional ($299/month)</p>
                    <p style="margin: 10px 0;"><strong>Commission Status:</strong> <span style="color: #f59e0b; font-weight: bold;">Pending (30-day retention period)</span></p>
                    <p style="margin: 10px 0;"><strong>Commission Amount:</strong> <span style="color: #059669; font-size: 20px; font-weight: bold;">$500</span> (one-time bounty)</p>
                </div>
                
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <p style="margin: 0; color: #92400e;">
                        <strong>⏰ Payment Timeline:</strong> Your commission will be paid after the customer completes their 30-day retention period. You'll receive an email when payment is processed.
                    </p>
                </div>
                
                <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e2e8f0; margin-top: 30px;">
                    <a href="https://liendeadline.com/broker-dashboard" style="display: inline-block; background: #c1554e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-bottom: 15px;">
                        View All Referrals →
                    </a>
                    <p style="color: #64748b; font-size: 14px; margin: 0;">
                        Keep sharing your referral link to earn more commissions!
                    </p>
                </div>
            </body>
            </html>
            """
            
            message = Mail(
                from_email=Email("partners@liendeadline.com"),
                to_emails=To(broker_email),
                subject="💰 New Referral - $500 Commission Earned!",
                html_content=html
            )
            
            sg.send(message)
            print(f"✅ Broker notification sent to {broker_email}")
            return True
        else:
            print(f"⚠️ SENDGRID_API_KEY not set - skipping broker notification to {broker_email}")
            print(f"   New referral: {customer_email}")
            return False
            
    except Exception as e:
        print(f"❌ Broker notification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

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
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(
        content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )

@app.get("/script.js")
async def serve_script_js():
    file_path = BASE_DIR / "script.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(
        content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )

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
async def get_partner_applications_api(request: Request, status: str = "all", username: str = Depends(verify_admin)):
    """Get partner applications for admin dashboard"""
    print("=" * 60)
    print("📊 ADMIN: Fetching partner applications")
    print(f"   Status filter: {status}")
    print("=" * 60)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Use EXACT same query as debug endpoint (which works)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            else:
                # Check if table exists (SQLite)
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='partner_applications'
                """)
                if not cursor.fetchone():
                    print("⚠️ Table 'partner_applications' does not exist")
                    print("=" * 60)
                    return {
                        "applications": [],
                        "total": 0
                    }
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            
            print(f"   Raw rows fetched: {len(rows)}")
            
            # Convert to list of dicts (same as debug endpoint)
            applications = []
            for row in rows:
                if isinstance(row, dict):
                    applications.append(row)
                else:
                    # Convert sqlite3.Row to dict
                    applications.append(dict(row))
            
            # Apply status filter AFTER fetching (if needed)
            if status != "all":
                applications = [app for app in applications if app.get('status') == status]
            
            print(f"   After status filter: {len(applications)} applications")
            if applications:
                print(f"   First application: {applications[0].get('name')} ({applications[0].get('email')}) - Status: {applications[0].get('status')}")
            else:
                print(f"   First application: None")
            print("=" * 60)
            
            return {
                "applications": applications,
                "total": len(applications)
            }
            
    except Exception as e:
        print(f"❌ ERROR fetching applications: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        
        return {
            "applications": [],
            "total": 0,
            "error": str(e)
        }

@app.get("/api/debug/partner-applications")
async def debug_partner_applications():
    """Debug endpoint to check partner_applications table"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Count total rows
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT COUNT(*) as count FROM partner_applications")
            else:
                # Check if table exists (SQLite)
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='partner_applications'
                """)
                if not cursor.fetchone():
                    return {
                        "total_count": 0,
                        "rows_returned": 0,
                        "applications": [],
                        "message": "Table 'partner_applications' does not exist"
                    }
                cursor.execute("SELECT COUNT(*) as count FROM partner_applications")
            
            count_result = cursor.fetchone()
            if isinstance(count_result, dict):
                total = count_result.get('count', 0)
            elif isinstance(count_result, tuple):
                total = count_result[0] if len(count_result) > 0 else 0
            else:
                total = count_result if count_result else 0
            
            # Get all rows
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            else:
                cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            
            rows = cursor.fetchall()
            
            # Convert to list of dicts
            applications = []
            for row in rows:
                if isinstance(row, dict):
                    applications.append(row)
                else:
                    # Convert sqlite3.Row to dict
                    applications.append(dict(row))
            
            return {
                "total_count": total,
                "rows_returned": len(applications),
                "applications": applications
            }
            
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/api/admin/email-captures")
async def get_email_captures_api(username: str = Depends(verify_admin)):
    """Get all email captures from calculator email gate - PostgreSQL compatible"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Query email captures
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT email, ip_address as ip, created_at::text as timestamp
                    FROM email_captures 
                    ORDER BY created_at DESC
                """)
            else:
                cursor.execute("""
                    SELECT email, ip, timestamp
                    FROM email_captures 
                    ORDER BY timestamp DESC
                """)
            
            captures = cursor.fetchall()
            
            result = []
            for c in captures:
                if isinstance(c, dict):
                    result.append({
                        "email": c.get('email', ''),
                        "ip": c.get('ip') or "N/A",
                        "timestamp": c.get('timestamp', '')
                    })
                elif hasattr(c, 'keys'):
                    result.append({
                        "email": c['email'] if 'email' in c.keys() else (c[0] if len(c) > 0 else ""),
                        "ip": (c['ip'] if 'ip' in c.keys() else (c[1] if len(c) > 1 else "N/A")) or "N/A",
                        "timestamp": c['timestamp'] if 'timestamp' in c.keys() else (c[2] if len(c) > 2 else "")
                    })
                else:
                    result.append({
                        "email": c[0] if len(c) > 0 else "",
                        "ip": c[1] if len(c) > 1 and c[1] else "N/A",
                        "timestamp": c[2] if len(c) > 2 else ""
                    })
            
            return result
    except Exception as e:
        print(f"Error in get_email_captures_api: {e}")
        import traceback
        traceback.print_exc()
        return []

@app.post("/api/admin/approve-partner")
async def approve_partner_api(data: dict, username: str = Depends(verify_admin)):
    """Approve a partner application - PostgreSQL compatible"""
    email = data.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Update status to approved
            if DB_TYPE == 'postgresql':
                cursor.execute("UPDATE partner_applications SET status = %s WHERE email = %s", ('approved', email))
            else:
                cursor.execute("UPDATE partner_applications SET status = ? WHERE email = ?", ('approved', email))
            
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Partner application not found")
            
            conn.commit()
        
        # TODO: Send email to partner with referral link
        # (You'll implement this later with EmailJS or SendGrid)
        
        return {"status": "ok", "message": "Partner approved"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error approving partner: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/v1/admin/flagged-referrals")
async def get_flagged_referrals(request: Request):
    """Get all referrals flagged for manual review"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    r.id,
                    r.broker_id,
                    r.broker_email,
                    r.customer_email,
                    r.payout,
                    r.payout_type,
                    r.fraud_flags,
                    r.status,
                    r.hold_until,
                    r.created_at,
                    b.name as broker_name
                FROM referrals r
                LEFT JOIN brokers b ON r.broker_id = b.referral_code
                WHERE r.status = 'flagged_for_review'
                ORDER BY r.created_at DESC
            """)
            
            flagged = []
            for row in cursor.fetchall():
                fraud_data = json.loads(row[6]) if row[6] else {}
                flagged.append({
                    'id': row[0],
                    'broker_id': row[1],
                    'broker_email': row[2],
                    'broker_name': row[10],
                    'customer_email': row[3],
                    'payout': row[4],
                    'payout_type': row[5],
                    'fraud_flags': fraud_data.get('flags', []),
                    'risk_score': fraud_data.get('risk_score', 0),
                    'status': row[7],
                    'hold_until': row[8],
                    'created_at': row[9]
                })
            
            return {'flagged_referrals': flagged}
            
    except Exception as e:
        print(f"❌ Error fetching flagged referrals: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@app.post("/api/v1/admin/approve-referral/{referral_id}")
async def approve_referral(referral_id: int):
    """Manually approve a flagged referral"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE referrals 
                SET status = 'on_hold'
                WHERE id = ?
            """, (referral_id,))
            conn.commit()
        
        return {"status": "approved"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/v1/admin/deny-referral/{referral_id}")
async def deny_referral(referral_id: int):
    """Deny a fraudulent referral"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE referrals 
                SET status = 'denied'
                WHERE id = ?
            """, (referral_id,))
            conn.commit()
        
        return {"status": "denied"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


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

# ==========================================
# TEST EMAIL ENDPOINT (REMOVE AFTER TESTING)
# ==========================================
def _send_test_email_sync(email: str, password: str):
    """Synchronous email sending function (called from async wrapper)"""
    return send_welcome_email(email, password)

async def send_test_email_with_timeout(email: str, password: str):
    """Async wrapper with timeout - HARD STOP so Cloudflare never 524s again"""
    logger = logging.getLogger(__name__)
    try:
        success = await asyncio.wait_for(
            asyncio.to_thread(_send_test_email_sync, email, password),
            timeout=12.0
        )
        if success:
            print(f"✅ Test email sent to {email}")
        else:
            print(f"⚠️ Test email failed for {email}")
    except anyio.get_cancelled_exc_class():
        logger.exception("EMAIL_SEND_FAILED: Timeout after 12s")
    except Exception as e:
        logger.exception("EMAIL_SEND_FAILED: %s", e)

@app.post("/api/v1/test-email")
async def test_email(request: Request, data: dict, background_tasks: BackgroundTasks):
    """Test email configuration - REMOVE AFTER TESTING"""
    test_email = data.get('email', 'test@example.com')
    test_password = 'TEST_PASSWORD_123'
    
    # Queue email in background (returns immediately)
    background_tasks.add_task(
        send_test_email_with_timeout,
        email=test_email,
        password=test_password
    )
    
    return {"queued": True, "message": f"Test email queued for {test_email}"}

# ==========================================
# PASSWORD RESET ENDPOINTS
# ==========================================
@app.post("/api/v1/request-password-reset")
async def request_password_reset(request: Request, data: dict):
    """Generate and send password reset token"""
    try:
        email = data.get('email', '').strip().lower()
        
        # Validate email
        if not email or '@' not in email:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Invalid email address"}
            )
        
        # Check if user exists
        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()
            
            if not user:
                # Don't reveal if user exists - security best practice
                return {"status": "success", "message": "If account exists, reset link sent"}
            
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=24)
            
            # Store token
            cursor.execute("""
                INSERT INTO password_reset_tokens (email, token, expires_at)
                VALUES (?, ?, ?)
            """, (email, reset_token, expires_at))
            db.commit()
        finally:
            db.close()
        
        # Send reset email
        reset_link = f"https://liendeadline.com/reset-password.html?token={reset_token}"
        send_password_reset_email(email, reset_link)
        
        print(f"✅ Password reset token generated for {email}")
        return {"status": "success", "message": "If account exists, reset link sent"}
        
    except Exception as e:
        print(f"❌ Password reset error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to process request"}
        )

@app.post("/api/v1/reset-password")
async def reset_password(request: Request, data: dict):
    """Reset password using token"""
    try:
        token = data.get('token', '').strip()
        new_password = data.get('password', '').strip()
        
        # Validate inputs
        if not token or not new_password:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Missing token or password"}
            )
        
        if len(new_password) < 8:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Password must be at least 8 characters"}
            )
        
        # Verify token
        db = get_db()
        try:
            cursor = db.cursor()
            
            cursor.execute("""
                SELECT email, expires_at, used 
                FROM password_reset_tokens 
                WHERE token = ?
            """, (token,))
            
            token_data = cursor.fetchone()
            
            if not token_data:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Invalid or expired token"}
                )
            
            email = token_data[0]
            expires_at = datetime.fromisoformat(token_data[1]) if isinstance(token_data[1], str) else token_data[1]
            used = token_data[2]
            
            # Check if token is expired or used
            if used or datetime.now() > expires_at:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Invalid or expired token"}
                )
            
            # Hash new password
            password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt())
            
            # Update password
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?
                WHERE email = ?
            """, (password_hash.decode(), email))
            
            # Mark token as used
            cursor.execute("""
                UPDATE password_reset_tokens 
                SET used = 1 
                WHERE token = ?
            """, (token,))
            
            db.commit()
        finally:
            db.close()
        
        print(f"✅ Password reset successful for {email}")
        return {"status": "success", "message": "Password reset successful"}
        
    except Exception as e:
        print(f"❌ Password reset error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to reset password"}
        )

def send_password_reset_email(email: str, reset_link: str):
    """Send password reset email"""
    try:
        sendgrid_key = os.getenv('SENDGRID_API_KEY')
        if sendgrid_key:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: #1e293b; color: white; padding: 20px; border-radius: 10px; text-align: center;">
                    <h1 style="margin: 0;">Password Reset Request</h1>
                </div>
                
                <div style="padding: 30px 0;">
                    <p>You requested a password reset for your LienDeadline account.</p>
                    
                    <p>Click the button below to reset your password:</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_link}" style="display: inline-block; background: #c1554e; color: white; padding: 15px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                            Reset Password
                        </a>
                    </div>
                    
                    <p style="color: #64748b; font-size: 14px;">
                        This link expires in 24 hours. If you didn't request this, ignore this email.
                    </p>
                    
                    <p style="color: #64748b; font-size: 14px;">
                        Or copy and paste this link:<br>
                        {reset_link}
                    </p>
                </div>
            </body>
            </html>
            """
            
            sg = SendGridAPIClient(api_key=sendgrid_key)
            message = Mail(
                from_email=Email("support@liendeadline.com"),
                to_emails=To(email),
                subject="Reset Your LienDeadline Password",
                html_content=html_content
            )
            
            sg.send(message)
            print(f"✅ Password reset email sent to {email}")
            return True
        else:
            print(f"⚠️ SendGrid not configured - Reset link: {reset_link}")
            return False
            
    except Exception as e:
        print(f"❌ Password reset email error: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==========================================
# ADMIN ENDPOINTS (in main.py for convenience)
# ==========================================
@app.get("/api/admin/calculations-today")
async def get_calculations_today():
    """Get today's calculations - Fixed counting with UTC timezone"""
    try:
        # Use UTC date for consistency
        from datetime import datetime, timezone
        today_utc = datetime.now(timezone.utc).date()
        
        print(f"🔍 Counting calculations for today (UTC): {today_utc}")
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Count ALL calculations from today (UTC)
            if DB_TYPE == 'postgresql':
                # PostgreSQL: calculation_date is DATE type, created_at is TIMESTAMP
                # Compare calculation_date directly (it's already a date)
                # Convert created_at TIMESTAMP to UTC date
                cursor.execute('''
                    SELECT COUNT(*) as count 
                    FROM calculations 
                    WHERE calculation_date = %s
                       OR DATE(created_at AT TIME ZONE 'UTC') = %s
                ''', (today_utc, today_utc))
            else:
                # SQLite: Use DATE() function
                cursor.execute('''
                    SELECT COUNT(*) as count 
                    FROM calculations 
                    WHERE DATE(calculation_date) = DATE('now')
                       OR DATE(created_at) = DATE('now')
                ''')
            
            result = cursor.fetchone()
            
            # Handle different row formats
            if isinstance(result, dict):
                count = result.get('count', 0)
            elif hasattr(result, 'keys'):
                count = result['count'] if 'count' in result.keys() else (result[0] if len(result) > 0 else 0)
            else:
                count = result[0] if result and len(result) > 0 else 0
            
            count = int(count) if count else 0
            print(f"✅ Found {count} calculations for today (UTC: {today_utc})")
            
            return {"calculations_today": count, "date": str(today_utc), "timezone": "UTC"}
            
    except Exception as e:
        print(f"❌ Error getting calculations today: {e}")
        import traceback
        traceback.print_exc()
        return {"calculations_today": 0, "error": str(e)}

# ==========================================
# DEBUG ENDPOINTS
# ==========================================
@app.get("/api/debug/tables")
async def debug_tables():
    """Debug endpoint - PROPERLY handle sqlite3.Row objects"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Get all tables
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                table_results = cursor.fetchall()
                # Extract table names from PostgreSQL results
                table_names = []
                for row in table_results:
                    if isinstance(row, dict):
                        table_names.append(row.get('table_name'))
                    elif isinstance(row, tuple) and len(row) > 0:
                        table_names.append(row[0])
                    else:
                        table_names.append(str(row))
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
                table_results = cursor.fetchall()
                
                # Extract table names from sqlite3.Row objects
                table_names = []
                for row in table_results:
                    if hasattr(row, '_fields') and 'name' in row._fields:
                        table_names.append(row['name'])
                    elif isinstance(row, tuple) and len(row) > 0:
                        table_names.append(row[0])
                    else:
                        table_names.append(str(row))
            
            result = {"db_type": DB_TYPE, "tables": []}
            
            for table_name in table_names:
                if not table_name:
                    continue
                    
                try:
                    # Count rows (use quoted table name for safety)
                    if DB_TYPE == 'postgresql':
                        cursor.execute(f'SELECT COUNT(*) as count FROM "{table_name}"')
                    else:
                        cursor.execute(f'SELECT COUNT(*) as count FROM "{table_name}"')
                    
                    count_row = cursor.fetchone()
                    
                    count = 0
                    if count_row:
                        if hasattr(count_row, '_fields'):
                            count = count_row['count']
                        elif isinstance(count_row, tuple):
                            count = count_row[0]
                        elif isinstance(count_row, dict):
                            count = count_row.get('count', 0)
                    
                    # Get sample data
                    if DB_TYPE == 'postgresql':
                        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
                    else:
                        cursor.execute(f'SELECT * FROM "{table_name}" LIMIT 3')
                    
                    sample_rows = cursor.fetchall()
                    
                    # Convert sample data
                    sample_data = []
                    for sample_row in sample_rows:
                        if hasattr(sample_row, '_fields'):
                            # sqlite3.Row to dict
                            row_dict = {}
                            for field in sample_row._fields:
                                value = sample_row[field]
                                # Convert to JSON-serializable
                                if value is None:
                                    row_dict[field] = None
                                elif isinstance(value, (int, float, bool, str)):
                                    row_dict[field] = value
                                else:
                                    row_dict[field] = str(value)
                            sample_data.append(row_dict)
                        elif isinstance(sample_row, dict):
                            # PostgreSQL dict
                            row_dict = {}
                            for key, value in sample_row.items():
                                if value is None:
                                    row_dict[key] = None
                                elif isinstance(value, (int, float, bool, str)):
                                    row_dict[key] = value
                                else:
                                    row_dict[key] = str(value)
                            sample_data.append(row_dict)
                        elif isinstance(sample_row, tuple):
                            # Tuple to list
                            sample_data.append([str(item) if item is not None else None for item in sample_row])
                        else:
                            sample_data.append(str(sample_row))
                    
                    result["tables"].append({
                        "name": table_name,
                        "row_count": count,
                        "sample": sample_data
                    })
                    
                except Exception as table_error:
                    result["tables"].append({
                        "name": table_name,
                        "error": str(table_error)
                    })
            
            return result
            
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

# ==========================================
# BROKER ENDPOINTS
# ==========================================
@app.get("/api/v1/broker/pending")
async def get_pending_brokers():
    """Get pending broker applications - PostgreSQL compatible"""
    print("🎯 GET /api/v1/broker/pending called")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # PostgreSQL compatible query with COALESCE for applied_at
            if DB_TYPE == 'postgresql':
                query = '''
                    SELECT id, name, email, company, commission_model, 
                           status, COALESCE(applied_at, created_at) as applied_at
                    FROM partner_applications 
                    WHERE status = 'pending'
                    ORDER BY COALESCE(applied_at, created_at) DESC
                '''
            else:
                # SQLite version
                query = '''
                    SELECT id, name, email, company, commission_model, 
                           status, COALESCE(applied_at, created_at, timestamp) as applied_at
                    FROM partner_applications 
                    WHERE status = 'pending'
                    ORDER BY COALESCE(applied_at, created_at, timestamp) DESC
                '''
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            pending = []
            for row in rows:
                # Handle PostgreSQL RealDictCursor (dict-like)
                if isinstance(row, dict):
                    pending.append(row)
                # Handle sqlite3.Row
                elif hasattr(row, 'keys'):
                    pending.append({key: row[key] for key in row.keys()})
                # Handle tuple (fallback)
                else:
                    pending.append({
                        'id': row[0],
                        'name': row[1],
                        'email': row[2],
                        'company': row[3],
                        'commission_model': row[4],
                        'status': row[5],
                        'applied_at': row[6]
                    })
            
            print(f"✅ Found {len(pending)} pending brokers")
            return {"pending": pending, "count": len(pending)}
    
    except Exception as e:
        print(f"❌ PostgreSQL error in get_pending_brokers: {e}")
        import traceback
        traceback.print_exc()
        return {"pending": [], "count": 0}

@app.get("/api/v1/broker/dashboard")
async def broker_dashboard(request: Request, email: str):
    """Get broker dashboard data"""
    try:
        db = get_db()
        try:
            cursor = db.cursor()
            
            # Verify broker exists
            cursor.execute("""
                SELECT id, name, referral_code, commission_model
                FROM brokers
                WHERE email = ?
            """, (email,))
            
            broker = cursor.fetchone()
            
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            broker_id = broker[0]
            broker_name = broker[1]
            referral_code = broker[2]
            commission_model = broker[3]
            
            # Get referrals
            cursor.execute("""
                SELECT 
                    customer_email,
                    amount,
                    payout,
                    payout_type,
                    status,
                    created_at
                FROM referrals
                WHERE broker_id = ?
                ORDER BY created_at DESC
            """, (referral_code,))
            
            referrals = []
            total_pending = 0
            total_paid = 0
            
            for row in cursor.fetchall():
                referral = {
                    "customer_email": row[0],
                    "amount": row[1],
                    "payout": row[2],
                    "payout_type": row[3],
                    "status": row[4],
                    "created_at": row[5]
                }
                referrals.append(referral)
                
                if row[4] == 'pending':
                    total_pending += row[2]
                elif row[4] == 'paid':
                    total_paid += row[2]
            
            return {
                "broker_name": broker_name,
                "referral_code": referral_code,
                "referral_link": f"https://liendeadline.com?ref={referral_code}",
                "commission_model": commission_model,
                "total_referrals": len(referrals),
                "total_pending": total_pending,
                "total_paid": total_paid,
                "referrals": referrals
            }
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ Broker dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to load dashboard"}
        )

# ==========================================
# ERROR MONITORING
# ==========================================
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('errors.log'),
        logging.StreamHandler()
    ]
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions"""
    logging.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    
    # Store in database for monitoring
    try:
        db = get_db()
        try:
            cursor = db.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT,
                    method TEXT,
                    error_message TEXT,
                    stack_trace TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                INSERT INTO error_logs (url, method, error_message, stack_trace)
                VALUES (?, ?, ?, ?)
            """, (str(request.url), request.method, str(exc), traceback.format_exc()))
            db.commit()
        finally:
            db.close()
    except:
        pass  # Don't fail on logging failure
    
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal server error. Our team has been notified."
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
