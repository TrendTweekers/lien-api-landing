from fastapi import FastAPI, HTTPException, Request, Depends, status, Response, Header, BackgroundTasks
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
import json
import secrets
import os
import bcrypt
import stripe
import traceback
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import resend
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from api.rate_limiter import limiter
from io import BytesIO
from api.calculators import (
    calculate_texas, calculate_washington, calculate_california,
    calculate_ohio, calculate_oregon, calculate_hawaii, calculate_default
)

# Optional ReportLab imports (for PDF generation)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("⚠️ Warning: ReportLab not installed. PDF generation will not work.")
    print("   Install with: pip install reportlab==4.0.7")

# Import database functions FIRST (before other local imports to avoid circular dependencies)
from api.database import get_db, get_db_cursor, DB_TYPE, execute_query, BASE_DIR

# Define project root (parent of api/ directory)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# THEN import routers (after database is defined)
from api.analytics import router as analytics_router
from api.admin import router as admin_router

# Import short link generator
from api.short_link_system import ShortLinkGenerator

# Import payout ledger service
try:
    from api.services.payout_ledger import (
        compute_broker_ledger,
        compute_all_brokers_ledgers,
        BrokerPayoutLedger,
        STATUS_ACTIVE,
        STATUS_CANCELED,
        STATUS_REFUNDED,
        STATUS_CHARGEBACK,
        MODEL_BOUNTY,
        MODEL_RECURRING
    )
    PAYOUT_LEDGER_AVAILABLE = True
except ImportError as e:
    PAYOUT_LEDGER_AVAILABLE = False
    print(f"⚠️ Warning: Payout ledger service not available: {e}")

# Import email anti-abuse system
from api.email_abuse import (
    is_disposable_email,
    generate_verification_token,
    hash_email,
    check_duplicate_email,
    validate_email_format
)

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
print("============================================================")
print("📧 EMAIL CONFIGURATION CHECK")
print("============================================================")

resend_key = os.environ.get("RESEND_API_KEY")
smtp_from = os.environ.get("SMTP_FROM_EMAIL", "onboarding@resend.dev")

if resend_key:
    print("✅ Resend: CONFIGURED")
    print(f"   From: {smtp_from}")
    print(f"   API Key: {'*' * min(len(resend_key), 20)}")
else:
    print("⚠️ Resend: NOT CONFIGURED")
    print("   Set RESEND_API_KEY environment variable")
    print("   Emails will be logged to console only")
    print("   Users won't receive welcome emails or password resets")

print("============================================================")

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
            
            # Contact messages table
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS contact_messages (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        email VARCHAR NOT NULL,
                        company VARCHAR,
                        topic VARCHAR NOT NULL,
                        message TEXT NOT NULL,
                        ip_address VARCHAR,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_email ON contact_messages(email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_created ON contact_messages(created_at)")
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS contact_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT NOT NULL,
                        company TEXT,
                        topic TEXT NOT NULL,
                        message TEXT NOT NULL,
                        ip_address TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_email ON contact_messages(email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_contact_created ON contact_messages(created_at)")
            
            # Create lien_deadlines table if it doesn't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'lien_deadlines'
                    )
                """)
                table_exists = cursor.fetchone()[0]
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lien_deadlines'")
                table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                print("📋 Creating lien_deadlines table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        CREATE TABLE lien_deadlines (
                            id SERIAL PRIMARY KEY,
                            state_code VARCHAR(2) UNIQUE NOT NULL,
                            state_name VARCHAR(50) NOT NULL,
                            preliminary_notice_required BOOLEAN DEFAULT FALSE,
                            preliminary_notice_days INTEGER,
                            preliminary_notice_formula TEXT,
                            preliminary_notice_deadline_description TEXT,
                            preliminary_notice_statute TEXT,
                            lien_filing_days INTEGER,
                            lien_filing_formula TEXT,
                            lien_filing_deadline_description TEXT,
                            lien_filing_statute TEXT,
                            weekend_extension BOOLEAN DEFAULT FALSE,
                            holiday_extension BOOLEAN DEFAULT FALSE,
                            residential_vs_commercial BOOLEAN DEFAULT FALSE,
                            notice_of_completion_trigger BOOLEAN DEFAULT FALSE,
                            notes TEXT,
                            last_updated TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lien_deadlines_state_code ON lien_deadlines(state_code)")
                else:
                    cursor.execute("""
                        CREATE TABLE lien_deadlines (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            state_code TEXT UNIQUE NOT NULL,
                            state_name TEXT NOT NULL,
                            preliminary_notice_required INTEGER DEFAULT 0,
                            preliminary_notice_days INTEGER,
                            preliminary_notice_formula TEXT,
                            preliminary_notice_deadline_description TEXT,
                            preliminary_notice_statute TEXT,
                            lien_filing_days INTEGER,
                            lien_filing_formula TEXT,
                            lien_filing_deadline_description TEXT,
                            lien_filing_statute TEXT,
                            weekend_extension INTEGER DEFAULT 0,
                            holiday_extension INTEGER DEFAULT 0,
                            residential_vs_commercial INTEGER DEFAULT 0,
                            notice_of_completion_trigger INTEGER DEFAULT 0,
                            notes TEXT,
                            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_lien_deadlines_state_code ON lien_deadlines(state_code)")
                conn.commit()
                print("✅ lien_deadlines table created")
            
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
    
    # Ensure users table exists
    try:
        from api.admin import ensure_users_table
        created = ensure_users_table()
        if created:
            print("✅ Users table created on startup")
        else:
            print("✅ Users table check: OK")
    except Exception as e:
        error_repr = repr(e)
        print(f"⚠️ Users table check failed: {error_repr}")
        # Don't fail startup if migration fails - it can be run manually via /api/admin/migrate-users-table
    
    # Verify critical HTML files exist
    critical_files = ["contact.html", "index.html", "terms.html", "admin-dashboard.html"]
    print("\n=== CRITICAL FILES CHECK ===")
    for filename in critical_files:
        file_path = BASE_DIR / filename
        if file_path.exists():
            print(f"✅ {filename} found at: {file_path.absolute()}")
        else:
            print(f"❌ {filename} NOT FOUND at: {file_path.absolute()}")
    print("============================\n")
    
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

# Serve images from public/images directory
images_dir = PROJECT_ROOT / "public" / "images"
print(f"🖼️ images_dir={images_dir} exists={images_dir.exists()}")
if images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(images_dir), html=False), name="images")

# Redirect www to non-www
@app.middleware("http")
async def redirect_www(request: Request, call_next):
    host = request.headers.get("host", "")
    if host.startswith("www."):
        url = request.url.replace(netloc=host[4:])
        return RedirectResponse(url=str(url), status_code=301)
    return await call_next(request)

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

# Valid state codes (all 50 US states + DC)
VALID_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL",
    "GA", "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "ME",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
    "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
]

# Load state rules (fallback to JSON if database not available)
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

@app.get("/r/{short_code}")
async def referral_redirect(short_code: str, request: Request):
    """
    Handle short referral links like /r/mA63
    1. Look up broker by short code
    2. Track the click
    3. Set referral cookies
    4. Redirect to homepage
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Validate code format
    if not ShortLinkGenerator.is_valid_code(short_code):
        logger.warning(f"Invalid short code format: {short_code}")
        raise HTTPException(status_code=404, detail="Invalid referral link")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Look up broker by short_code
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email, referral_code 
                    FROM brokers 
                    WHERE short_code = %s AND status = 'approved'
                """, (short_code,))
            else:
                cursor.execute("""
                    SELECT id, name, email, referral_code 
                    FROM brokers 
                    WHERE short_code = ? AND status = 'approved'
                """, (short_code,))
            
            broker = cursor.fetchone()
            
            if not broker:
                logger.warning(f"Short code not found or broker not approved: {short_code}")
                raise HTTPException(status_code=404, detail="Referral link not found")
            
            # Handle different row formats
            if isinstance(broker, dict):
                broker_id = broker.get('id')
                broker_name = broker.get('name', '')
                broker_email = broker.get('email', '')
                referral_code = broker.get('referral_code', '')
            else:
                broker_id = broker[0]
                broker_name = broker[1] if len(broker) > 1 else ''
                broker_email = broker[2] if len(broker) > 2 else ''
                referral_code = broker[3] if len(broker) > 3 else ''
            
            # Track the click for analytics
            try:
                client_ip = request.client.host if request.client else "unknown"
                user_agent = request.headers.get("user-agent", "unknown")
                referrer = request.headers.get("referer", "")
                
                # Create referral_clicks table if it doesn't exist
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS referral_clicks (
                            id SERIAL PRIMARY KEY,
                            short_code VARCHAR(10) NOT NULL,
                            broker_id INTEGER,
                            ip_address VARCHAR(45),
                            user_agent TEXT,
                            referrer_url TEXT,
                            clicked_at TIMESTAMP DEFAULT NOW(),
                            converted BOOLEAN DEFAULT FALSE,
                            conversion_date TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON referral_clicks(short_code)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_broker ON referral_clicks(broker_id)")
                    
                    cursor.execute("""
                        INSERT INTO referral_clicks 
                        (short_code, broker_id, ip_address, user_agent, referrer_url)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (short_code, broker_id, client_ip, user_agent, referrer))
                else:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS referral_clicks (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            short_code TEXT NOT NULL,
                            broker_id INTEGER,
                            ip_address TEXT,
                            user_agent TEXT,
                            referrer_url TEXT,
                            clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            converted INTEGER DEFAULT 0,
                            conversion_date TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON referral_clicks(short_code)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_clicks_broker ON referral_clicks(broker_id)")
                    
                    cursor.execute("""
                        INSERT INTO referral_clicks 
                        (short_code, broker_id, ip_address, user_agent, referrer_url)
                        VALUES (?, ?, ?, ?, ?)
                    """, (short_code, broker_id, client_ip, user_agent, referrer))
                
                conn.commit()
                logger.info(f"📊 Click tracked: {short_code} -> {broker_email}")
            except Exception as e:
                logger.error(f"Failed to track click: {e}")
                # Don't fail the redirect if tracking fails
            
            # Create redirect response
            redirect_response = RedirectResponse(url="/", status_code=302)
            
            # Set referral tracking cookies (30-day expiry)
            cookie_age = 30 * 24 * 60 * 60  # 30 days
            
            redirect_response.set_cookie(
                key="ref_code",
                value=referral_code,
                max_age=cookie_age,
                httponly=True,
                samesite="lax"
            )
            
            redirect_response.set_cookie(
                key="ref_short",
                value=short_code,
                max_age=cookie_age,
                httponly=True,
                samesite="lax"
            )
            
            redirect_response.set_cookie(
                key="ref_broker",
                value=str(broker_id),
                max_age=cookie_age,
                httponly=True,
                samesite="lax"
            )
            
            logger.info(f"🔗 Referral redirect: {short_code} -> {broker_email}")
            
            return redirect_response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in referral redirect: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/v1/states")
def get_states():
    """Get list of supported states - returns all 51 states with code and name"""
    try:
        # Try to get states from database with names
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT state_code, state_name 
                    FROM lien_deadlines 
                    ORDER BY state_code
                """)
            else:
                cursor.execute("""
                    SELECT state_code, state_name 
                    FROM lien_deadlines 
                    ORDER BY state_code
                """)
            states = cursor.fetchall()
            
            if states:
                result = []
                for row in states:
                    if isinstance(row, dict):
                        result.append({
                            "code": row.get("state_code"),
                            "name": row.get("state_name")
                        })
                    else:
                        result.append({
                            "code": row[0],
                            "name": row[1]
                        })
                return {
                    "states": result,
                    "count": len(result)
                }
    except Exception as e:
        print(f"⚠️ Error querying database for states: {e}")
    
    # Fallback: return state codes only if database query fails
    return {
        "states": [{"code": code, "name": code} for code in VALID_STATES],
        "count": len(VALID_STATES)
    }

@app.get("/api/v1/guide/{state_code}/pdf")
async def generate_state_guide_pdf(state_code: str):
    """Generate PDF guide for a specific state"""
    # Check if ReportLab is available
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation is temporarily unavailable. ReportLab library is not installed. Please contact support."
        )
    
    state_code = state_code.upper()
    
    # Validate state code
    if state_code not in STATE_RULES:
        raise HTTPException(
            status_code=404,
            detail=f"State '{state_code}' not found. Available states: {', '.join(STATE_RULES.keys())}"
        )
    
    state_data = STATE_RULES[state_code]
    state_name = state_data.get('state_name', state_code)
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    # Container for PDF content
    story = []
    
    # Define colors
    navy = HexColor('#1e3a8a')
    coral = HexColor('#f97316')
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=navy,
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=navy,
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubheading',
        parent=styles['Heading3'],
        fontSize=14,
        textColor=HexColor('#374151'),
        spaceAfter=6,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        textColor=HexColor('#1f2937'),
        spaceAfter=6,
        leading=14,
        alignment=TA_JUSTIFY
    )
    
    # Header
    header_text = f"<b>LienDeadline.com</b>"
    story.append(Paragraph(header_text, ParagraphStyle('Header', parent=styles['Normal'], fontSize=12, textColor=navy, alignment=TA_CENTER)))
    story.append(Spacer(1, 0.2*inch))
    
    # Title
    title_text = f"{state_name} Mechanics Lien Guide<br/>for Material Suppliers"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Deadline Summary Box
    prelim_notice = state_data.get('preliminary_notice', {})
    lien_filing = state_data.get('lien_filing', {})
    
    prelim_days = prelim_notice.get('days', prelim_notice.get('commercial_days', prelim_notice.get('standard_days', 'N/A')))
    lien_days = lien_filing.get('days', lien_filing.get('commercial_days', lien_filing.get('standard_days', 'N/A')))
    
    # Create summary table
    summary_data = [
        ['<b>Deadline Summary</b>', ''],
        ['Preliminary Notice Deadline:', f'{prelim_days} days' if prelim_days != 'N/A' else 'Not required'],
        ['Lien Filing Deadline:', f'{lien_days} days' if lien_days != 'N/A' else 'N/A'],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f3f4f6')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Step-by-Step Instructions
    story.append(Paragraph("Step-by-Step Instructions", heading_style))
    
    # When to send preliminary notice
    story.append(Paragraph("When to Send Preliminary Notice", subheading_style))
    prelim_desc = prelim_notice.get('description', 'See state-specific requirements')
    story.append(Paragraph(f"• {prelim_desc}", body_style))
    if prelim_notice.get('trigger'):
        trigger = prelim_notice['trigger'].replace('_', ' ').title()
        story.append(Paragraph(f"• Trigger: {trigger}", body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # Who to serve it to
    story.append(Paragraph("Who to Serve It To", subheading_style))
    serving_reqs = state_data.get('serving_requirements', [])
    if serving_reqs:
        for req in serving_reqs:
            req_formatted = req.replace('_', ' ').title()
            story.append(Paragraph(f"• {req_formatted}", body_style))
    else:
        story.append(Paragraph("• See state-specific requirements", body_style))
    story.append(Spacer(1, 0.15*inch))
    
    # What information to include
    story.append(Paragraph("What Information to Include", subheading_style))
    story.append(Paragraph("• Your company name and address", body_style))
    story.append(Paragraph("• Property owner's name and address", body_style))
    story.append(Paragraph("• General contractor's name (if applicable)", body_style))
    story.append(Paragraph("• Description of materials/services provided", body_style))
    story.append(Paragraph("• Project address or legal description", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Common Mistakes
    story.append(Paragraph("Common Mistakes to Avoid", heading_style))
    warnings = state_data.get('critical_warnings', [])
    if warnings:
        for warning in warnings[:3]:  # Limit to 3
            warning_clean = warning.replace('⚠️', '').strip()
            story.append(Paragraph(f"• {warning_clean}", body_style))
    else:
        story.append(Paragraph("• Missing the preliminary notice deadline", body_style))
        story.append(Paragraph("• Serving notice to wrong parties", body_style))
        story.append(Paragraph("• Missing required information in notice", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Quick Checklist
    story.append(Paragraph("Quick Checklist", heading_style))
    checklist_items = [
        f"Send preliminary notice within {prelim_days} days" if prelim_days != 'N/A' else "Check if preliminary notice is required",
        f"File lien within {lien_days} days of last work" if lien_days != 'N/A' else "File lien within required timeframe",
        "Serve notice on all required parties",
        "Include all required information",
        "Keep proof of service/delivery"
    ]
    
    for item in checklist_items[:5]:  # Limit to 5 items
        story.append(Paragraph(f"☐ {item}", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Statute Citations
    citations = state_data.get('statute_citations', [])
    if citations:
        story.append(Paragraph("Statute Citations", heading_style))
        for citation in citations:
            story.append(Paragraph(f"• {citation}", body_style))
        story.append(Spacer(1, 0.2*inch))
    
    # Footer with social proof
    story.append(Spacer(1, 0.3*inch))
    footer_text = "Generated by LienDeadline.com | Free Calculator: https://liendeadline.com"
    story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=HexColor('#6b7280'), alignment=TA_CENTER)))
    story.append(Spacer(1, 0.1*inch))
    social_proof = "Trusted by 500+ material suppliers | ⭐⭐⭐⭐⭐ 4.9/5 rating"
    story.append(Paragraph(social_proof, ParagraphStyle('SocialProof', parent=styles['Normal'], fontSize=8, textColor=HexColor('#6b7280'), alignment=TA_CENTER)))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Track PDF download (analytics)
    print(f"📥 PDF downloaded: {state_code} - {datetime.now().isoformat()}")
    # TODO: Send to analytics endpoint if needed
    # import requests
    # requests.post("https://api.liendeadline.com/analytics", json={"event": "pdf_download", "state": state_code})
    
    # Return PDF file
    filename = f"{state_code}-lien-guide.pdf"
    return Response(
        content=buffer.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf"
        }
    )

# Calculate deadline request model
class ContactRequest(BaseModel):
    name: str
    email: EmailStr
    company: str | None = None
    topic: str
    message: str

class TrackCalculationRequest(BaseModel):
    """Request model for tracking calculation attempts"""
    state: str = None
    notice_date: str = None
    last_work_date: str = None
    email: str = None  # Allow email to be sent from frontend for admin check

class CalculateDeadlineRequest(BaseModel):
    invoice_date: str
    state: str
    role: str = "supplier"
    project_type: str = "commercial"
    notice_of_completion_date: Optional[str] = None
    notice_of_commencement_filed: Optional[bool] = False

def get_client_ip(request: Request) -> str:
    """Get real client IP from headers (works with Railway/Cloudflare)"""
    return (
        request.headers.get("cf-connecting-ip") or 
        request.headers.get("x-forwarded-for", "").split(",")[0].strip() or
        request.headers.get("x-real-ip") or
        (request.client.host if request.client else "unknown")
    )

def get_user_agent_hash(request: Request) -> str:
    """Get a hash of user agent for better tracking (handles shared IPs)"""
    import hashlib
    user_agent = request.headers.get('user-agent', 'unknown')
    return hashlib.md5(user_agent.encode()).hexdigest()[:8]

def is_broker_email(email: str) -> bool:
    """
    Check if an email belongs to a broker.
    Returns True if email exists in brokers table with approved/active status.
    """
    if not email:
        return False
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id FROM brokers 
                    WHERE LOWER(email) = LOWER(%s) 
                    AND status IN ('approved', 'active')
                    LIMIT 1
                """, (email.lower().strip(),))
            else:
                cursor.execute("""
                    SELECT id FROM brokers 
                    WHERE LOWER(email) = LOWER(?) 
                    AND status IN ('approved', 'active')
                    LIMIT 1
                """, (email.lower().strip(),))
            
            result = cursor.fetchone()
            return result is not None
            
    except Exception as e:
        print(f"⚠️ Error checking broker email: {e}")
        return False  # Fail closed - assume not a broker if check fails

@app.post("/api/v1/track-calculation")
@limiter.limit("20/minute")
async def track_calculation(request: Request, request_data: TrackCalculationRequest = None):
    """
    Track calculation attempt and enforce server-side limits.
    Returns whether calculation is allowed and current count.
    """
    from fastapi.responses import JSONResponse
    
    try:
        client_ip = get_client_ip(request)
        user_agent = request.headers.get('user-agent', 'unknown')
        user_agent_hash = get_user_agent_hash(request)
        
        # Create composite key: IP + user agent hash (handles shared IPs better)
        tracking_key = f"{client_ip}:{user_agent_hash}"
        
        # Get email from request first (for admin check before DB lookup)
        request_email = None
        if request_data and request_data.email:
            request_email = request_data.email.strip().lower()
        
        # Admin/dev user bypass (check BEFORE database lookup)
        DEV_EMAIL = "kartaginy1@gmail.com"
        if request_email and request_email == DEV_EMAIL.lower():
            print(f"✅ Admin/dev user detected from request: {request_email} - allowing unlimited calculations")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "allowed",
                    "calculation_count": 0,
                    "remaining_calculations": 999999,
                    "email_provided": True,
                    "quota": {"unlimited": True}
                }
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Ensure email_gate_tracking table exists with tracking_key column
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_gate_tracking (
                        id SERIAL PRIMARY KEY,
                        ip_address VARCHAR NOT NULL,
                        tracking_key VARCHAR NOT NULL,
                        email VARCHAR,
                        calculation_count INTEGER DEFAULT 0,
                        first_calculation_at TIMESTAMP DEFAULT NOW(),
                        last_calculation_at TIMESTAMP DEFAULT NOW(),
                        email_captured_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                # Add tracking_key column if it doesn't exist (migration)
                try:
                    cursor.execute("ALTER TABLE email_gate_tracking ADD COLUMN IF NOT EXISTS tracking_key VARCHAR")
                except:
                    pass  # Column might already exist
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_tracking_key ON email_gate_tracking(tracking_key)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_ip ON email_gate_tracking(ip_address)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_email ON email_gate_tracking(email)")
                
                # Get current tracking record
                cursor.execute("""
                    SELECT calculation_count, email, email_captured_at 
                    FROM email_gate_tracking 
                    WHERE tracking_key = %s 
                    ORDER BY last_calculation_at DESC 
                    LIMIT 1
                """, (tracking_key,))
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_gate_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip_address TEXT NOT NULL,
                        tracking_key TEXT NOT NULL,
                        email TEXT,
                        calculation_count INTEGER DEFAULT 0,
                        first_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        email_captured_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Add tracking_key column if it doesn't exist (migration)
                try:
                    cursor.execute("ALTER TABLE email_gate_tracking ADD COLUMN tracking_key TEXT")
                except:
                    pass  # Column might already exist
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_tracking_key ON email_gate_tracking(tracking_key)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_ip ON email_gate_tracking(ip_address)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_gate_email ON email_gate_tracking(email)")
                
                cursor.execute("""
                    SELECT calculation_count, email, email_captured_at 
                    FROM email_gate_tracking 
                    WHERE tracking_key = ? 
                    ORDER BY last_calculation_at DESC 
                    LIMIT 1
                """, (tracking_key,))
            
            tracking = cursor.fetchone()
            
            # Parse tracking data
            if tracking:
                if isinstance(tracking, dict):
                    count = tracking.get('calculation_count', 0)
                    db_email = tracking.get('email')
                    email_captured_at = tracking.get('email_captured_at')
                elif hasattr(tracking, 'keys'):
                    count = tracking['calculation_count'] if 'calculation_count' in tracking.keys() else tracking[0]
                    db_email = tracking['email'] if 'email' in tracking.keys() else (tracking[1] if len(tracking) > 1 else None)
                    email_captured_at = tracking['email_captured_at'] if 'email_captured_at' in tracking.keys() else (tracking[2] if len(tracking) > 2 else None)
                else:
                    count = tracking[0] if tracking else 0
                    db_email = tracking[1] if tracking and len(tracking) > 1 else None
                    email_captured_at = tracking[2] if tracking and len(tracking) > 2 else None
            else:
                count = 0
                db_email = None
                email_captured_at = None
            
            # Use email from request if provided, otherwise use DB email
            email = request_email or (db_email.lower() if db_email else None)
            
            # Determine limits
            CALCULATIONS_BEFORE_EMAIL = 3
            TOTAL_FREE_CALCULATIONS = 6
            
            # Check if user is a broker - brokers get same limits as customers (no unlimited access)
            is_broker = email and is_broker_email(email)
            if is_broker:
                print(f"⚠️ Broker attempting calculation: {email} - applying same limits as customers")
            
            # Admin/dev user bypass (unlimited calculations)
            DEV_EMAIL = "kartaginy1@gmail.com"
            is_dev_user = email and email.lower() == DEV_EMAIL.lower()
            
            if is_dev_user:
                print(f"✅ Admin/dev user detected: {email} - allowing unlimited calculations")
                remaining = 999999  # Effectively unlimited
            # Check if limit exceeded (same for brokers and customers)
            elif not email:
                # No email provided yet
                if count >= CALCULATIONS_BEFORE_EMAIL:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "status": "limit_reached",
                            "message": "Free trial limit reached. Please provide your email for 3 more calculations.",
                            "calculation_count": count,
                            "remaining_calculations": 0,
                            "email_required": True,
                            "limit_type": "before_email"
                        }
                    )
                remaining = CALCULATIONS_BEFORE_EMAIL - count
            else:
                # Email provided - brokers get same limits as customers
                if count >= TOTAL_FREE_CALCULATIONS:
                    error_msg = "Free trial limit reached (6 calculations). Upgrade to unlimited for $299/month."
                    if is_broker:
                        error_msg += " Note: Brokers have the same calculation limits as customers."
                    return JSONResponse(
                        status_code=403,
                        content={
                            "status": "limit_reached",
                            "message": error_msg,
                            "calculation_count": count,
                            "remaining_calculations": 0,
                            "email_required": False,
                            "limit_type": "upgrade_required"
                        }
                    )
                remaining = TOTAL_FREE_CALCULATIONS - count
            
            # Increment count BEFORE allowing calculation
            new_count = count + 1
            
            if tracking:
                # Update existing record
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE email_gate_tracking 
                        SET calculation_count = %s,
                            last_calculation_at = NOW()
                        WHERE tracking_key = %s
                    """, (new_count, tracking_key))
                else:
                    cursor.execute("""
                        UPDATE email_gate_tracking 
                        SET calculation_count = ?,
                            last_calculation_at = CURRENT_TIMESTAMP
                        WHERE tracking_key = ?
                    """, (new_count, tracking_key))
            else:
                # Create new record
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        INSERT INTO email_gate_tracking (ip_address, tracking_key, calculation_count)
                        VALUES (%s, %s, 1)
                    """, (client_ip, tracking_key))
                else:
                    cursor.execute("""
                        INSERT INTO email_gate_tracking (ip_address, tracking_key, calculation_count)
                        VALUES (?, ?, 1)
                    """, (client_ip, tracking_key))
            
            conn.commit()
            
            # Return success with updated count
            return {
                "status": "allowed",
                "calculation_count": new_count,
                "remaining_calculations": remaining - 1,  # Subtract 1 since we just incremented
                "email_required": not email and new_count >= CALCULATIONS_BEFORE_EMAIL,
                "email_provided": bool(email)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in track_calculation: {e}")
        import traceback
        traceback.print_exc()
        # On error, allow calculation (fail open for better UX)
        return {
            "status": "allowed",
            "calculation_count": 0,
            "remaining_calculations": 3,
            "email_required": False,
            "email_provided": False,
            "error": str(e)
        }

@app.post("/v1/calculate")
def get_user_from_session(request: Request):
    """Helper to get logged-in user from session token"""
    authorization = request.headers.get('authorization', '')
    if not authorization or not authorization.startswith('Bearer '):
        return None
    
    token = authorization.replace('Bearer ', '')
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT email, subscription_status FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT email, subscription_status FROM users WHERE session_token = ?", (token,))
            
            user = cursor.fetchone()
            
            if user:
                if isinstance(user, dict):
                    email = user.get('email')
                    subscription_status = user.get('subscription_status')
                elif hasattr(user, 'keys'):
                    email = user['email'] if 'email' in user.keys() else (user[0] if len(user) > 0 else None)
                    subscription_status = user['subscription_status'] if 'subscription_status' in user.keys() else (user[1] if len(user) > 1 else None)
                else:
                    email = user[0] if user and len(user) > 0 else None
                    subscription_status = user[1] if user and len(user) > 1 else None
                
                if subscription_status in ['active', 'trialing']:
                    return {'email': email, 'subscription_status': subscription_status, 'unlimited': True}
    except Exception as e:
        print(f"⚠️ Error checking session: {e}")
    
    return None

@app.post("/api/v1/calculate-deadline")
@limiter.limit("10/minute")
async def calculate_deadline(
    request: Request,
    request_data: CalculateDeadlineRequest
):
    """
    Calculate deadline - now enforces server-side limits.
    Frontend should call /api/v1/track-calculation first to check limits.
    """
    invoice_date = request_data.invoice_date
    state = request_data.state
    role = request_data.role
    project_type = request_data.project_type
    state_code = state.upper()
    
    # Check if user is logged in with active/trialing subscription
    logged_in_user = get_user_from_session(request)
    quota = {'unlimited': False, 'remaining': 0, 'limit': 3}
    
    if logged_in_user and logged_in_user.get('unlimited'):
        # Skip limit checks for logged-in active/trialing users
        quota = {'unlimited': True}
    else:
        # Get client IP and tracking key
        client_ip = get_client_ip(request)
        user_agent_hash = get_user_agent_hash(request)
        tracking_key = f"{client_ip}:{user_agent_hash}"
        
        # Check limits BEFORE processing calculation (server-side enforcement)
        try:
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                # Get current tracking
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT calculation_count, email 
                        FROM email_gate_tracking 
                        WHERE tracking_key = %s 
                        ORDER BY last_calculation_at DESC 
                        LIMIT 1
                    """, (tracking_key,))
                else:
                    cursor.execute("""
                        SELECT calculation_count, email 
                        FROM email_gate_tracking 
                        WHERE tracking_key = ? 
                        ORDER BY last_calculation_at DESC 
                        LIMIT 1
                    """, (tracking_key,))
                
                tracking = cursor.fetchone()
                
                if tracking:
                    if isinstance(tracking, dict):
                        count = tracking.get('calculation_count', 0)
                        email = tracking.get('email')
                    elif hasattr(tracking, 'keys'):
                        count = tracking['calculation_count'] if 'calculation_count' in tracking.keys() else tracking[0]
                        email = tracking['email'] if 'email' in tracking.keys() else (tracking[1] if len(tracking) > 1 else None)
                    else:
                        count = tracking[0] if tracking else 0
                        email = tracking[1] if tracking and len(tracking) > 1 else None
                    
                    # Admin/dev user bypass (check BEFORE broker check)
                    DEV_EMAIL = "kartaginy1@gmail.com"
                    is_dev_user = email and email.lower() == DEV_EMAIL.lower()
                    
                    if is_dev_user:
                        print(f"✅ Admin/dev user detected in calculate_deadline: {email} - allowing unlimited calculations")
                        quota = {'unlimited': True}
                    else:
                        # Check if user is a broker - brokers get same limits as customers
                        is_broker = email and is_broker_email(email)
                        if is_broker:
                            print(f"⚠️ Broker attempting calculation: {email} - applying same limits as customers")
                        
                        limit = 6 if email else 3
                        remaining = max(0, limit - count)
                        quota = {'unlimited': False, 'remaining': remaining, 'limit': limit}
                        
                        # Enforce limits server-side (same for brokers and customers)
                        if not email and count >= 3:
                            raise HTTPException(
                                status_code=403,
                                detail="Free trial limit reached. Please provide your email for 3 more calculations."
                            )
                        
                        if email and count >= 6:
                            # Brokers get same limits - no unlimited access
                            error_msg = "Free trial limit reached (6 calculations). Upgrade to unlimited for $299/month."
                            if is_broker:
                                error_msg += " Note: Brokers have the same calculation limits as customers."
                            raise HTTPException(
                                status_code=403,
                                detail=error_msg
                            )
        except HTTPException:
            raise
        except Exception as e:
            print(f"⚠️ Error checking limits in calculate_deadline: {e}")
            # Continue with calculation if limit check fails (fail open for UX)
    
    # Validate state (check against VALID_STATES list)
    if state_code not in VALID_STATES:
        return {
            "error": f"State {state_code} not supported",
            "available_states": VALID_STATES,
            "message": "Please select a valid US state or DC"
        }
    
    # Try to get rules from database first, fallback to JSON
    rules = None
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT * FROM lien_deadlines WHERE state_code = %s
                """, (state_code,))
            else:
                cursor.execute("""
                    SELECT * FROM lien_deadlines WHERE state_code = ?
                """, (state_code,))
            db_state = cursor.fetchone()
            
            if db_state:
                # Convert database row to rules format
                if isinstance(db_state, dict):
                    rules = {
                        "state_name": db_state.get("state_name"),
                        "preliminary_notice": {
                            "required": db_state.get("preliminary_notice_required", False),
                            "days": db_state.get("preliminary_notice_days"),
                            "formula": db_state.get("preliminary_notice_formula"),
                            "description": db_state.get("preliminary_notice_deadline_description"),
                            "statute": db_state.get("preliminary_notice_statute")
                        },
                        "lien_filing": {
                            "days": db_state.get("lien_filing_days"),
                            "formula": db_state.get("lien_filing_formula"),
                            "description": db_state.get("lien_filing_deadline_description"),
                            "statute": db_state.get("lien_filing_statute")
                        },
                        "special_rules": {
                            "weekend_extension": db_state.get("weekend_extension", False),
                            "holiday_extension": db_state.get("holiday_extension", False),
                            "residential_vs_commercial": db_state.get("residential_vs_commercial", False),
                            "notice_of_completion_trigger": db_state.get("notice_of_completion_trigger", False),
                            "notes": db_state.get("notes", "")
                        }
                    }
    except Exception as e:
        print(f"⚠️ Error querying database for state {state_code}: {e}")
    
    # Fallback to JSON if database query failed
    if not rules and state_code in STATE_RULES:
        rules = STATE_RULES[state_code]
    
    if not rules:
        return {
            "error": f"State {state_code} data not available",
            "available_states": VALID_STATES,
            "message": "State is supported but data is not loaded. Please contact support."
        }
    
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
    
    # State-specific calculation logic
    result = None
    state_name = rules.get("state_name", state_code)
    special_rules = rules.get("special_rules", {})
    
    if state_code == "TX":
        result = calculate_texas(delivery_date, project_type=project_type)
    elif state_code == "WA":
        result = calculate_washington(delivery_date, role=role)
    elif state_code == "CA":
        result = calculate_california(
            delivery_date,
            notice_of_completion_date=request_data.notice_of_completion_date,
            role=role
        )
    elif state_code == "OH":
        result = calculate_ohio(
            delivery_date,
            project_type=project_type,
            notice_of_commencement_filed=request_data.notice_of_commencement_filed or False
        )
    elif state_code == "OR":
        result = calculate_oregon(delivery_date)
    elif state_code == "HI":
        result = calculate_hawaii(delivery_date)
    else:
        # Default calculation for simple states
        result = calculate_default(
            delivery_date,
            {
                "preliminary_notice_required": rules.get("preliminary_notice", {}).get("required", False),
                "preliminary_notice_days": rules.get("preliminary_notice", {}).get("days"),
                "lien_filing_days": rules.get("lien_filing", {}).get("days"),
                "notes": special_rules.get("notes", "")
            },
            weekend_extension=special_rules.get("weekend_extension", False),
            holiday_extension=special_rules.get("holiday_extension", False)
        )
    
    # Extract deadlines from result
    prelim_deadline = result.get("preliminary_deadline")
    lien_deadline = result.get("lien_deadline")
    warnings = result.get("warnings", [])
    prelim_required = result.get("preliminary_required", rules.get("preliminary_notice", {}).get("required", False))
    
    # Calculate days from now
    today = datetime.now()
    days_to_prelim = (prelim_deadline - today).days if prelim_deadline else None
    days_to_lien = (lien_deadline - today).days if lien_deadline else None
    
    # Track page view and calculation (non-blocking, PostgreSQL compatible)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Format dates for database
            today_str = date.today().isoformat()
            prelim_date_str = prelim_deadline.date().isoformat() if prelim_deadline else None
            lien_date_str = lien_deadline.date().isoformat() if lien_deadline else None
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
                    prelim_date_str if prelim_date_str else None,
                    lien_date_str if lien_date_str else None
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
                    prelim_date_str if prelim_date_str else None,
                    lien_date_str if lien_date_str else None
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
    
    # Get statute citations from rules
    prelim_notice = rules.get("preliminary_notice", {})
    lien_filing = rules.get("lien_filing", {})
    statute_citations = []
    if prelim_notice.get("statute"):
        statute_citations.append(prelim_notice["statute"])
    if lien_filing.get("statute"):
        statute_citations.append(lien_filing["statute"])
    
    # Build response
    response = {
        "state": state_name,
        "state_code": state_code,
        "invoice_date": invoice_date,
        "role": role,
        "project_type": project_type,
        "preliminary_notice": {
            "required": prelim_required,
            "deadline": prelim_deadline.strftime('%Y-%m-%d') if prelim_deadline else None,
            "days_from_now": days_to_prelim,
            "urgency": get_urgency(days_to_prelim) if days_to_prelim else None,
            "description": prelim_notice.get("description", prelim_notice.get("deadline_description", ""))
        },
        "lien_filing": {
            "deadline": lien_deadline.strftime('%Y-%m-%d') if lien_deadline else None,
            "days_from_now": days_to_lien,
            "urgency": get_urgency(days_to_lien) if days_to_lien else None,
            "description": lien_filing.get("description", lien_filing.get("deadline_description", ""))
        },
        "serving_requirements": rules.get("serving_requirements", []),
        "statute_citations": statute_citations,
        "warnings": warnings,
        "critical_warnings": warnings,  # Keep for backward compatibility
        "notes": special_rules.get("notes", ""),
        "disclaimer": "⚠️ This is general information only, NOT legal advice.",
        "response_time_ms": 45,
        "quota": quota
    }
    
    return response

@app.post("/api/contact")
@limiter.limit("5/minute")
async def submit_contact_form(request: Request, contact_data: ContactRequest):
    """
    Handle contact form submissions.
    Validates input, stores in database, and sends email via Resend.
    """
    from api.admin import send_email_sync
    
    try:
        # Get client IP
        client_ip = get_client_ip(request)
        
        # Server-side validation
        if not contact_data.name or len(contact_data.name.strip()) < 2:
            raise HTTPException(status_code=400, detail="Name must be at least 2 characters")
        
        if not contact_data.message or len(contact_data.message.strip()) < 20:
            raise HTTPException(status_code=400, detail="Message must be at least 20 characters")
        
        valid_topics = ["Support", "Sales", "Partner Program", "Legal", "Other"]
        if contact_data.topic not in valid_topics:
            raise HTTPException(status_code=400, detail=f"Topic must be one of: {', '.join(valid_topics)}")
        
        # Store in database
        try:
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        INSERT INTO contact_messages (name, email, company, topic, message, ip_address)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        contact_data.name.strip(),
                        contact_data.email.strip(),
                        contact_data.company.strip() if contact_data.company else None,
                        contact_data.topic,
                        contact_data.message.strip(),
                        client_ip
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO contact_messages (name, email, company, topic, message, ip_address)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        contact_data.name.strip(),
                        contact_data.email.strip(),
                        contact_data.company.strip() if contact_data.company else None,
                        contact_data.topic,
                        contact_data.message.strip(),
                        client_ip
                    ))
                
                conn.commit()
                print(f"✅ Contact message saved: {contact_data.email} - {contact_data.topic}")
        except Exception as db_error:
            print(f"⚠️ Failed to save contact message to database: {db_error}")
            # Continue even if DB save fails - still send email
        
        # Determine recipient email based on topic
        recipient_email = "partners@liendeadline.com" if contact_data.topic == "Partner Program" else "support@liendeadline.com"
        
        # Create email subject
        subject = f"[Contact] {contact_data.topic} – {contact_data.email}"
        
        # Create email body (HTML) - escape HTML to prevent XSS
        import html
        
        name_escaped = html.escape(contact_data.name)
        email_escaped = html.escape(contact_data.email)
        company_escaped = html.escape(contact_data.company) if contact_data.company else ""
        topic_escaped = html.escape(contact_data.topic)
        message_escaped = html.escape(contact_data.message).replace('\n', '<br>')
        ip_escaped = html.escape(client_ip)
        
        company_line = f"<p><strong>Company:</strong> {company_escaped}</p>" if contact_data.company else ""
        
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f9fafb; border-radius: 8px; padding: 24px; border: 1px solid #e5e7eb;">
        <h2 style="color: #1f2937; margin-top: 0; font-size: 24px;">New Contact Form Submission</h2>
        
        <div style="background-color: white; border-radius: 6px; padding: 20px; margin-top: 16px;">
            <p><strong>Name:</strong> {name_escaped}</p>
            <p><strong>Email:</strong> <a href="mailto:{email_escaped}">{email_escaped}</a></p>
            {company_line}
            <p><strong>Topic:</strong> {topic_escaped}</p>
            <p><strong>IP Address:</strong> {ip_escaped}</p>
        </div>
        
        <div style="background-color: white; border-radius: 6px; padding: 20px; margin-top: 16px;">
            <h3 style="color: #1f2937; margin-top: 0;">Message:</h3>
            <div style="white-space: pre-wrap; color: #4b5563; line-height: 1.8;">{message_escaped}</div>
        </div>
        
        <p style="color: #6b7280; font-size: 14px; margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
            This message was submitted via the LienDeadline contact form at {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
        </p>
    </div>
</body>
</html>"""
        
        # Send email via Resend
        try:
            send_email_sync(recipient_email, subject, body_html)
            print(f"✅ Contact email sent to {recipient_email}")
        except Exception as email_error:
            print(f"❌ Failed to send contact email: {email_error}")
            import traceback
            traceback.print_exc()
            # Still return success if DB save worked, but log the email failure
            return {
                "status": "success",
                "message": "Your message has been received. We'll get back to you soon.",
                "note": "Email notification may be delayed"
            }
        
        return {
            "status": "success",
            "message": "Thank you for your message! We'll get back to you within 24 hours."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Contact form error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to process contact form. Please try again or email us directly.")

# Serve HTML files
# Serve HTML files (with .html extension)
@app.get("/calculator.html")
async def serve_calculator():
    file_path = BASE_DIR / "calculator.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path)

@app.get("/calculator-embed.html")
async def serve_calculator_embed():
    file_path = BASE_DIR / "calculator-embed.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(file_path)

@app.get("/dashboard.html")
async def serve_dashboard():
    """Redirect old dashboard to new customer dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/customer-dashboard.html", status_code=301)

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
async def serve_customer_dashboard_html(request: Request):
    """
    Customer dashboard HTML - block brokers from accessing.
    """
    # Check if user is a broker (via email in query params)
    email = request.query_params.get('email', '').strip()
    
    # Block brokers from accessing customer dashboard
    if email and is_broker_email(email):
        raise HTTPException(
            status_code=403,
            detail="Brokers cannot access customer dashboard. Please use /broker-dashboard"
        )
    
    file_path = BASE_DIR / "customer-dashboard.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="customer-dashboard.html not found in project root")
    return FileResponse(file_path)

@app.get("/comparison.html")
async def serve_comparison_html():
    """Serve comparison page"""
    file_path = BASE_DIR / "comparison.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="comparison.html not found in project root")
    return FileResponse(file_path, media_type="text/html")

@app.get("/vs-levelset.html")
async def serve_vs_levelset_html():
    """Redirect old vs-levelset.html to comparison.html"""
    return RedirectResponse(url="/comparison.html", status_code=301)

@app.get("/contact.html")
async def serve_contact_html():
    """
    Serve contact page
    
    Smoke test:
    - curl -I http://localhost:8080/contact.html should return 200 and Content-Type: text/html
    """
    file_path = BASE_DIR / "contact.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="contact.html not found in project root")
    return FileResponse(file_path, media_type="text/html")

@app.get("/contact")
async def serve_contact_clean():
    """
    Clean URL: /contact → contact.html
    
    Smoke test:
    - curl -I http://localhost:8080/contact should return 200 and Content-Type: text/html
    """
    file_path = BASE_DIR / "contact.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Contact page not found")
    return FileResponse(file_path, media_type="text/html")

# Clean URLs (without .html extension)
@app.get("/calculator")
async def serve_calculator_clean():
    """Clean URL: /calculator → calculator.html"""
    file_path = BASE_DIR / "calculator.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Calculator not found")
    return FileResponse(file_path)

@app.get("/dashboard")
async def serve_dashboard_clean(request: Request):
    """
    Clean URL: /dashboard → redirects to /customer-dashboard
    """
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/customer-dashboard", status_code=301)

@app.get("/admin-dashboard-v2")
async def serve_admin_dashboard_v2(username: str = Depends(verify_admin)):
    """Serve admin dashboard V2 with HTTP Basic Auth"""
    file_path = BASE_DIR / "admin-dashboard-v2.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Admin dashboard V2 not found")
    
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

@app.get("/admin-dashboard-v2.js")
async def serve_admin_dashboard_v2_js(username: str = Depends(verify_admin)):
    """Serve admin dashboard V2 JavaScript"""
    file_path = BASE_DIR / "admin-dashboard-v2.js"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Admin dashboard V2 JS not found")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    return Response(
        content=js_content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/admin-dashboard")
async def serve_admin_dashboard_clean(request: Request, username: str = Depends(verify_admin)):
    """
    Clean URL: /admin-dashboard → serves V2 by default
    Query params:
    - ?ui=v1 → serves V1 (admin-dashboard.html)
    - ?ui=v2 or no param → serves V2 (admin-dashboard-v2.html)
    """
    ui_version = request.query_params.get('ui', 'v2').lower()
    
    if ui_version == 'v1':
        # Serve V1 dashboard
        file_path = BASE_DIR / "admin-dashboard.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Admin dashboard V1 not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    else:
        # Serve V2 dashboard (default)
        file_path = BASE_DIR / "admin-dashboard-v2.html"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Admin dashboard V2 not found")
        
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

@app.get("/comparison")
async def serve_comparison_clean():
    """Clean URL: /comparison → comparison.html"""
    file_path = BASE_DIR / "comparison.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Comparison page not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/vs-levelset")
async def serve_vs_levelset_clean():
    """Redirect old /vs-levelset to /comparison"""
    return RedirectResponse(url="/comparison", status_code=301)
    return FileResponse(file_path, media_type="text/html")

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
async def serve_customer_dashboard_clean(request: Request):
    """
    Customer dashboard - block brokers from accessing.
    Clean URL: /customer-dashboard → customer-dashboard.html
    """
    # Check if user is a broker (via email in query params or session)
    email = request.query_params.get('email', '').strip()
    
    # Block brokers from accessing customer dashboard
    if email and is_broker_email(email):
        raise HTTPException(
            status_code=403,
            detail="Brokers cannot access customer dashboard. Please use /broker-dashboard"
        )
    
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
    print(f"🔐 Login attempt for {req.email}")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get user by email
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM users WHERE email = %s", (req.email.lower(),))
            else:
                cursor.execute("SELECT * FROM users WHERE email = ?", (req.email.lower(),))
            
            user = cursor.fetchone()
            
            if not user:
                print(f"❌ User not found: {req.email}")
                raise HTTPException(status_code=401, detail="Invalid email or password")
            
            print(f"✅ User found: {req.email}")
            
            # Extract password_hash - handle both dict-like and tuple results
            # RealDictCursor (PostgreSQL) and sqlite3.Row both support dict-like access
            try:
                password_hash = user['password_hash'] if 'password_hash' in user else user.get('password_hash', '')
                subscription_status = user['subscription_status'] if 'subscription_status' in user else user.get('subscription_status', '')
            except (TypeError, KeyError):
                # Fallback for tuple/list results
                if isinstance(user, (tuple, list)):
                    password_hash = user[1] if len(user) > 1 else ''
                    subscription_status = user[4] if len(user) > 4 else ''
                else:
                    password_hash = getattr(user, 'password_hash', '')
                    subscription_status = getattr(user, 'subscription_status', '')
            
            # Check password with bcrypt
            try:
                password_match = bcrypt.checkpw(req.password.encode('utf-8'), password_hash.encode('utf-8'))
                print(f"🔑 Password match: {password_match}")
            except Exception as pw_error:
                print(f"❌ Password check error: {repr(pw_error)}")
                password_match = False
            
            if not password_match:
                raise HTTPException(status_code=401, detail="Invalid email or password")
            
            # Check subscription status
            if subscription_status not in ['active', 'trialing']:
                print(f"⚠️ Subscription status: {subscription_status} (not active)")
                raise HTTPException(status_code=403, detail="Subscription expired or cancelled")
            
            # Generate session token
            token = secrets.token_urlsafe(32)
            
            # Update user session token and last login
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users 
                    SET session_token = %s, last_login_at = NOW()
                    WHERE email = %s
                """, (token, req.email.lower()))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET session_token = ?, last_login_at = CURRENT_TIMESTAMP
                    WHERE email = ?
                """, (token, req.email.lower()))
            
            conn.commit()
            
            print(f"✅ Login successful for {req.email}")
            
            return {
                "success": True,
                "token": token,
                "email": req.email.lower()
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {repr(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Login failed. Please try again.")

@app.get("/api/verify-session")
async def verify_session(authorization: str = Header(None)):
    """Verify session token"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="No token provided")
    
    token = authorization.replace('Bearer ', '')
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT * FROM users WHERE session_token = ?", (token,))
            
            user = cursor.fetchone()
            
            if not user:
                raise HTTPException(status_code=401, detail="Invalid session")
            
            # Extract fields - handle both dict-like and tuple results
            try:
                subscription_status = user['subscription_status'] if 'subscription_status' in user else user.get('subscription_status', '')
                email = user['email'] if 'email' in user else user.get('email', '')
            except (TypeError, KeyError):
                # Fallback for tuple/list results
                if isinstance(user, (tuple, list)):
                    subscription_status = user[4] if len(user) > 4 else ''
                    email = user[1] if len(user) > 1 else ''
                else:
                    subscription_status = getattr(user, 'subscription_status', '')
                    email = getattr(user, 'email', '')
            
            if subscription_status not in ['active', 'trialing']:
                raise HTTPException(status_code=403, detail="Subscription expired")
            
            return {
                "valid": True,
                "email": email,
                "subscription_status": subscription_status
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Session verification error: {repr(e)}")
        raise HTTPException(status_code=500, detail="Session verification failed")

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

async def auto_approve_broker(name: str, email: str, company: str, commission_model: str, message: str):
    """Auto-approve broker and create account immediately"""
    import string
    from api.admin import send_welcome_email_background
    
    try:
        print("=" * 60)
        print("🚀 AUTO-APPROVING BROKER")
        print("=" * 60)
        
        # Generate referral code: broker_[random6]
        random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        referral_code = f"broker_{random_suffix}"
        
        # Generate short code for clean referral link
        short_code = ShortLinkGenerator.generate_short_code(email, length=4)
        referral_link = f"https://liendeadline.com/r/{short_code}"
        
        # Generate temporary password
        temp_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
        
        # Hash password
        password_hash = bcrypt.hashpw(temp_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check for short code collision
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT short_code FROM brokers WHERE short_code = %s", (short_code,))
            else:
                cursor.execute("SELECT short_code FROM brokers WHERE short_code = ?", (short_code,))
            
            if cursor.fetchone():
                # Collision - generate longer random code
                short_code = ShortLinkGenerator.generate_random_code(length=6)
                referral_link = f"https://liendeadline.com/r/{short_code}"
                print(f"⚠️ Short code collision, using random code: {short_code}")
            
            # Create broker record with status='approved'
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO brokers 
                    (name, email, company, referral_code, referral_link, short_code, commission_model, status, password_hash, approved_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved', %s, NOW())
                    ON CONFLICT (email) DO UPDATE SET
                        name = EXCLUDED.name,
                        company = EXCLUDED.company,
                        referral_code = EXCLUDED.referral_code,
                        referral_link = EXCLUDED.referral_link,
                        short_code = EXCLUDED.short_code,
                        commission_model = EXCLUDED.commission_model,
                        status = 'approved',
                        password_hash = EXCLUDED.password_hash,
                        approved_at = NOW()
                    RETURNING id
                """, (name, email.lower(), company, referral_code, referral_link, short_code, commission_model, password_hash))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO brokers 
                    (name, email, company, referral_code, referral_link, short_code, commission_model, status, password_hash, approved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'approved', ?, CURRENT_TIMESTAMP)
                """, (name, email.lower(), company, referral_code, referral_link, short_code, commission_model, password_hash))
            
            conn.commit()
        
        print(f"✅ Broker created: {email}")
        print(f"   Referral code: {referral_code}")
        print(f"   Short code: {short_code}")
        print(f"   Referral link: {referral_link}")
        
        # Send welcome email in background
        try:
            send_welcome_email_background(
                email=email,
                referral_link=referral_link,
                name=name,
                referral_code=referral_code,
                commission_model=commission_model,
                temp_password=temp_password
            )
            print("✅ Welcome email queued")
        except Exception as email_error:
            print(f"⚠️ Email send error: {email_error}")
            # Don't fail the request if email fails
        
        return {
            "status": "approved",
            "referral_link": referral_link,
            "message": "Broker account created successfully. Check your email for login details."
        }
        
    except Exception as e:
        print(f"❌ Auto-approval error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Auto-approval failed: {str(e)}"}
        )

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
        works_with_suppliers = data.get('works_with_suppliers', False)
        
        print(f"👤 Name: {name}")
        print(f"📧 Email: {email}")
        print(f"🏢 Company: {company}")
        print(f"📞 Phone: {phone}")
        print(f"💰 Commission: {commission_model}")
        print(f"✅ Works with suppliers: {works_with_suppliers}")
        
        # Validate required fields
        if not name or not email or not company or not client_count or not commission_model:
            print("❌ VALIDATION FAILED: Missing required fields")
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Missing required fields"}
            )
        
        # Auto-approval logic
        if works_with_suppliers:
            print("🚀 AUTO-APPROVAL: Creating broker immediately...")
            return await auto_approve_broker(name, email, company, commission_model, message)
        
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
            "status": "pending",
            "message": "Manual review in 24 hours",
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
    """
    Enhanced email capture with comprehensive anti-abuse protection:
    - Disposable email blocking (1000+ domains)
    - Email format validation
    - Duplicate email detection across IPs
    - Email verification (optional - can be enabled later)
    """
    from fastapi.responses import JSONResponse
    
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()
        recaptcha_token = data.get('recaptcha_token')  # Optional reCAPTCHA token
        
        # Get client IP
        client_ip = get_client_ip(request)
        user_agent = request.headers.get('user-agent', '')
        
        # ========== LAYER 1: Format Validation ==========
        is_valid, format_error = validate_email_format(email)
        if not is_valid:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": format_error or "Invalid email format",
                    "error_code": "INVALID_FORMAT",
                    "help_text": "Please enter a valid email address (e.g., name@example.com)"
                }
            )
        
        # ========== LAYER 2: Disposable Email Blocking ==========
        is_disposable, disposable_reason = is_disposable_email(email)
        if is_disposable:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Temporary or disposable email addresses are not allowed",
                    "error_code": "DISPOSABLE_EMAIL",
                    "help_text": "Please use a permanent email address. If you believe this is an error, contact support.",
                    "reason": disposable_reason
                }
            )
        
        # ========== LAYER 3: Duplicate Email Detection ==========
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Ensure email_captures table exists with verification columns
            if DB_TYPE == 'postgresql':
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS email_captures (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR NOT NULL UNIQUE,
                        ip_address VARCHAR,
                        user_agent TEXT,
                        calculation_count INTEGER DEFAULT 0,
                        verification_token VARCHAR,
                        verified_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT NOW(),
                        last_used_at TIMESTAMP DEFAULT NOW()
                    )
                ''')
                # Add verification columns if they don't exist
                try:
                    cursor.execute("ALTER TABLE email_captures ADD COLUMN IF NOT EXISTS verification_token VARCHAR")
                    cursor.execute("ALTER TABLE email_captures ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP")
                    cursor.execute("ALTER TABLE email_captures ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP DEFAULT NOW()")
                except:
                    pass  # Columns may already exist
            else:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS email_captures (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL UNIQUE,
                        ip_address TEXT,
                        user_agent TEXT,
                        calculation_count INTEGER DEFAULT 0,
                        verification_token TEXT,
                        verified_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                # Add verification columns if they don't exist
                try:
                    cursor.execute("ALTER TABLE email_captures ADD COLUMN verification_token TEXT")
                    cursor.execute("ALTER TABLE email_captures ADD COLUMN verified_at TIMESTAMP")
                    cursor.execute("ALTER TABLE email_captures ADD COLUMN last_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                except:
                    pass  # Columns may already exist
            
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_captures_email ON email_captures(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_captures_ip ON email_captures(ip_address)")
            
            # Check for duplicate email from different IP
            is_duplicate, duplicate_reason = check_duplicate_email(email, client_ip, cursor)
            if is_duplicate:
                # Allow if same IP (legitimate user), block if different IP
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT ip_address FROM email_captures WHERE email = %s LIMIT 1
                    """, (email,))
                else:
                    cursor.execute("""
                        SELECT ip_address FROM email_captures WHERE email = ? LIMIT 1
                    """, (email,))
                
                existing_record = cursor.fetchone()
                existing_ip = None
                if existing_record:
                    if isinstance(existing_record, dict):
                        existing_ip = existing_record.get('ip_address')
                    else:
                        existing_ip = existing_record[0] if len(existing_record) > 0 else None
                
                # Block if different IP
                if existing_ip and existing_ip != client_ip:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "status": "error",
                            "message": "This email address has already been registered from a different location",
                            "error_code": "DUPLICATE_EMAIL",
                            "help_text": "Each email address can only be used from one location. If this is your email, please contact support.",
                            "appeal_url": "/contact.html"
                        }
                    )
            
            # ========== LAYER 4: Rate Limiting by Email ==========
            # Check if email was used too frequently
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT COUNT(*), MAX(last_used_at) 
                    FROM email_captures 
                    WHERE email = %s 
                    AND last_used_at > NOW() - INTERVAL '1 hour'
                """, (email,))
            else:
                cursor.execute("""
                    SELECT COUNT(*), MAX(last_used_at) 
                    FROM email_captures 
                    WHERE email = ? 
                    AND last_used_at > datetime('now', '-1 hour')
                """, (email,))
            
            rate_check = cursor.fetchone()
            if rate_check:
                count = rate_check[0] if isinstance(rate_check, tuple) else rate_check.get('count', 0)
                if count > 10:  # More than 10 uses in 1 hour
                    return JSONResponse(
                        status_code=429,
                        content={
                            "status": "error",
                            "message": "Too many requests from this email address",
                            "error_code": "RATE_LIMIT",
                            "help_text": "Please wait before trying again. If you need more calculations, consider upgrading to Pro."
                        }
                    )
            
            # ========== SAVE EMAIL (with verification token) ==========
            verification_token = generate_verification_token()
            
            if DB_TYPE == 'postgresql':
                cursor.execute('''
                    INSERT INTO email_captures 
                    (email, ip_address, user_agent, calculation_count, verification_token, last_used_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (email) DO UPDATE SET
                        calculation_count = GREATEST(email_captures.calculation_count, 3),
                        ip_address = EXCLUDED.ip_address,
                        user_agent = EXCLUDED.user_agent,
                        last_used_at = NOW(),
                        verification_token = COALESCE(email_captures.verification_token, EXCLUDED.verification_token)
                ''', (
                    email,
                    client_ip,
                    user_agent,
                    3,  # Give them 3 more calculations
                    verification_token
                ))
            else:
                # SQLite: Check if email exists first
                cursor.execute("SELECT id, verification_token FROM email_captures WHERE email = ?", (email,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing record
                    existing_token = existing[1] if isinstance(existing, tuple) and len(existing) > 1 else None
                    cursor.execute('''
                        UPDATE email_captures 
                        SET calculation_count = MAX(calculation_count, 3),
                            ip_address = ?,
                            user_agent = ?,
                            last_used_at = CURRENT_TIMESTAMP,
                            verification_token = COALESCE(verification_token, ?)
                        WHERE email = ?
                    ''', (client_ip, user_agent, verification_token, email))
                else:
                    # Insert new record
                    cursor.execute('''
                        INSERT INTO email_captures 
                        (email, ip_address, user_agent, calculation_count, verification_token, last_used_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (
                        email,
                        client_ip,
                        user_agent,
                        3,  # Give them 3 more calculations
                        verification_token
                    ))
            
            # Link email to tracking record (update email_gate_tracking)
            user_agent_hash = get_user_agent_hash(request)
            tracking_key = f"{client_ip}:{user_agent_hash}"
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE email_gate_tracking 
                    SET email = %s,
                        email_captured_at = NOW(),
                        calculation_count = GREATEST(calculation_count, 3)
                    WHERE tracking_key = %s
                """, (email, tracking_key))
            else:
                cursor.execute("""
                    UPDATE email_gate_tracking 
                    SET email = ?,
                        email_captured_at = CURRENT_TIMESTAMP,
                        calculation_count = MAX(calculation_count, 3)
                    WHERE tracking_key = ?
                """, (email, tracking_key))
            
            conn.commit()
        
        print(f"✅ Email captured (anti-abuse passed): {email} from {client_ip}")
        
        # TODO: Send verification email (optional - can be enabled later)
        # For now, we'll allow immediate access but can add verification later
        
        return {
            "status": "success",
            "message": "Email saved! You have 3 more calculations.",
            "calculations_remaining": 3,
            "verification_required": False,  # Set to True when verification is enabled
            "verification_token": None  # Don't expose token to frontend
        }
        
    except Exception as e:
        print(f"❌ Error capturing email: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Internal server error. Please try again later.",
                "error_code": "INTERNAL_ERROR"
            }
        )

@app.get("/api/v1/verify-email/{token}")
async def verify_email(token: str):
    """
    Verify email address using verification token.
    This endpoint can be called when email verification is enabled.
    """
    from fastapi.responses import JSONResponse
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE email_captures 
                    SET verified_at = NOW()
                    WHERE verification_token = %s 
                    AND verified_at IS NULL
                    RETURNING email
                """, (token,))
            else:
                cursor.execute("""
                    UPDATE email_captures 
                    SET verified_at = CURRENT_TIMESTAMP
                    WHERE verification_token = ? 
                    AND verified_at IS NULL
                """, (token,))
                cursor.execute("SELECT email FROM email_captures WHERE verification_token = ?", (token,))
            
            result = cursor.fetchone()
            conn.commit()
            
            if result:
                email = result[0] if isinstance(result, tuple) else result.get('email')
                return {
                    "status": "success",
                    "message": "Email verified successfully!",
                    "email": email
                }
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Invalid or expired verification token",
                        "error_code": "INVALID_TOKEN"
                    }
                )
                
    except Exception as e:
        print(f"❌ Error verifying email: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": "Internal server error",
                "error_code": "INTERNAL_ERROR"
            }
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
    Returns: (fraud_flags: list, risk_score: int, should_flag: bool, auto_reject: bool)
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
            same_payment_method = False
            if broker_stripe_id and customer_stripe_id:
                # Check if same Stripe customer (catches shared payment methods)
                if broker_stripe_id == customer_stripe_id:
                    same_payment_method = True
                    flags.append('SAME_STRIPE_CUSTOMER')
                    risk_score += 50  # Critical flag - automatic flag regardless of score
            
            # LAYER 2: Email Similarity Check ⭐⭐
            broker_base = broker_email.split('@')[0].lower()
            customer_base = customer_email.split('@')[0].lower()
            broker_domain = broker_email.split('@')[1].lower()
            customer_domain = customer_email.split('@')[1].lower()
            
            # Check for similar usernames (reduced penalty - could be family business)
            from difflib import SequenceMatcher
            similarity = SequenceMatcher(None, broker_base, customer_base).ratio()
            
            if similarity > 0.8:  # 80% similar
                flags.append('SIMILAR_EMAIL')
                risk_score += 15  # Reduced from 30 - could be legitimate family business
            
            # Check for sequential numbers (john1@, john2@)
            import re
            broker_no_nums = re.sub(r'\d+', '', broker_base)
            customer_no_nums = re.sub(r'\d+', '', customer_base)
            if broker_no_nums == customer_no_nums:
                flags.append('SEQUENTIAL_EMAIL')
                risk_score += 15  # Reduced from 25
            
            # Same domain check - DON'T penalize alone (brokers referring colleagues is GOOD)
            # Only penalize if combined with same payment method (real fraud indicator)
            same_domain = False
            if broker_domain == customer_domain and broker_domain not in ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']:
                same_domain = True
                flags.append('SAME_COMPANY_DOMAIN')
                # Don't add points here - brokers referring colleagues is legitimate
                # Will check combination with payment method below
            
            # NEW: Check combination of same domain + same payment method (real fraud)
            # This catches brokers using their own payment method for "customer" signups
            if same_domain and same_payment_method:
                flags.append('SAME_DOMAIN_AND_PAYMENT')
                risk_score += 40  # Strong fraud indicator
            
            # LAYER 3: Timing Analysis ⭐⭐
            if broker_created:
                from datetime import datetime
                try:
                    broker_created_dt = datetime.fromisoformat(broker_created.replace('Z', '+00:00'))
                    signup_time = datetime.now()
                    time_diff = (signup_time - broker_created_dt.replace(tzinfo=None)).total_seconds() / 3600  # hours
                    
                    if time_diff < 1:  # Signup within 1 hour
                        flags.append('IMMEDIATE_SIGNUP')
                        risk_score += 20  # Reduced from 35 - excited customers sign up fast
                    elif time_diff < 24:  # Within 24 hours
                        flags.append('FAST_SIGNUP')
                        risk_score += 10  # Reduced from 15
                except:
                    pass
            
            # LAYER 4: IP Address Check (if available)
            # Reduced penalty - could be office meeting or shared network
            customer_ip = session_data.get('customer_details', {}).get('ip_address')
            if broker_ip and customer_ip and broker_ip == customer_ip:
                flags.append('SAME_IP')
                risk_score += 20  # Reduced from 40 - could be legitimate office/VPN
            
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
            
            # REMOVED: First referral penalty - penalizes all new brokers unfairly
            # First referral is often their best/most legitimate one
            # Only flag if combined with other high-risk indicators
            if referral_count == 0:
                flags.append('FIRST_REFERRAL')  # Keep flag for admin visibility, but no penalty
                # risk_score += 0  # No penalty for first referral
            
            # NEW: Check for suspicious velocity (batch fraud)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM referrals 
                WHERE broker_id = ? AND created_at > datetime('now', '-24 hours')
            """, (broker_id,))
            referrals_last_24h = cursor.fetchone()[0]
            
            if referrals_last_24h >= 5:  # 5+ referrals in 24 hours = suspicious
                flags.append('HIGH_VELOCITY')
                risk_score += 25  # Suspicious batch fraud pattern
            
            # LAYER 7: Email Age Check (new Gmail accounts are suspicious)
            # Note: This requires external API, skip for now or add later
            
            # LAYER 8: Device Fingerprint (if available)
            # Note: Requires frontend implementation, skip for now
            
            # Determine if should flag for manual review
            # Updated thresholds:
            # - 60+ points = flagged for review (allows for 1-2 legitimate coincidences)
            # - 80+ points = auto-reject (clear fraud, but still reviewable)
            # - SAME_STRIPE_CUSTOMER = automatic flag regardless of score
            
            should_flag = False
            auto_reject = False
            
            if 'SAME_STRIPE_CUSTOMER' in flags:
                # Same payment method = automatic flag (strongest indicator)
                should_flag = True
            elif risk_score >= 80:
                # Clear fraud pattern
                should_flag = True
                auto_reject = True
                flags.append('AUTO_REJECT_THRESHOLD')
            elif risk_score >= 60:
                # Suspicious pattern - needs review
                should_flag = True
            
            return flags, risk_score, should_flag, auto_reject
            
    except Exception as e:
        print(f"❌ Fraud check error: {e}")
        import traceback
        traceback.print_exc()
        return ['ERROR_DURING_CHECK'], 0, False, False


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
            print(f"✅ Received checkout.session.completed webhook - Event ID: {event['id']}, Session ID: {session.get('id')}")
            
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
                
                # Track revenue in Umami
                try:
                    amount_total = session.get('amount_total')  # Amount in cents
                    currency = session.get('currency', 'usd').upper()
                    
                    if amount_total:
                        # Convert cents to dollars for Umami
                        value = amount_total / 100.0
                        
                        # Send revenue event to Umami API (server-side)
                        import urllib.request
                        
                        umami_payload = {
                            'website': '02250d35-ee17-41be-845d-2fe0f7f15e63',
                            'hostname': 'liendeadline.com',
                            'name': 'revenue',
                            'data': {
                                'value': value,
                                'currency': currency,
                                'plan': 'professional'
                            }
                        }
                        
                        json_data = json.dumps(umami_payload).encode('utf-8')
                        req = urllib.request.Request(
                            'https://cloud.umami.is/api/send',
                            data=json_data,
                            headers={'Content-Type': 'application/json'}
                        )
                        
                        try:
                            with urllib.request.urlopen(req, timeout=5) as response:
                                print(f"✅ Umami revenue tracked: ${value} {currency}")
                        except Exception as umami_error:
                            print(f"⚠️ Umami revenue tracking failed: {umami_error}")
                except Exception as e:
                    print(f"⚠️ Error tracking revenue in Umami: {e}")
                    # Don't fail webhook if Umami tracking fails
                
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
                        fraud_flags, risk_score, should_flag, auto_reject = check_fraud_signals(
                            referral_code, 
                            email, 
                            customer_id,
                            session
                        )
                        
                        # Calculate hold dates
                        from datetime import datetime, timedelta
                        hold_until = datetime.now() + timedelta(days=60)  # 60-day hold period (catches fraud, chargebacks, disputes)
                        clawback_until = datetime.now() + timedelta(days=90)
                        
                        # Determine status based on fraud detection results
                        if should_flag:
                            if auto_reject:
                                status = 'flagged_for_review'  # Auto-reject but still reviewable
                            else:
                                status = 'flagged_for_review'
                        else:
                            status = 'on_hold'  # Normal referral, 60-day hold
                        
                        # For one-time bounty: only create if this is the first payment for this customer
                        if payout_type == 'bounty':
                            existing_ref = db.execute("""
                                SELECT id FROM referrals 
                                WHERE broker_id = ? AND customer_email = ? AND payout_type = 'bounty'
                            """, (broker['referral_code'], email)).fetchone()
                            
                            if existing_ref:
                                print(f"⚠️ One-time bounty already exists for {email}, skipping duplicate")
                                db.commit()
                                return {"status": "skipped", "reason": "One-time bounty already paid for this customer"}
                        
                        # Store referral with fraud data and payment_date (when payment succeeded)
                        db.execute("""
                            INSERT INTO referrals 
                            (broker_id, broker_email, customer_email, customer_stripe_id,
                             amount, payout, payout_type, status, fraud_flags, 
                             hold_until, clawback_until, created_at, payment_date)
                            VALUES (?, ?, ?, ?, 299.00, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
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
        
        # Recurring payment succeeded (for recurring commission model)
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            customer_id = invoice.get('customer')
            subscription_id = invoice.get('subscription')
            amount_paid = invoice.get('amount_paid', 0) / 100.0  # Convert from cents
            
            if not customer_id:
                return {"status": "skipped", "reason": "No customer ID"}
            
            # Find customer email
            customer_row = db.execute("""
                SELECT email FROM customers WHERE stripe_customer_id = ?
            """, (customer_id,)).fetchone()
            
            if not customer_row:
                print(f"⚠️ Customer {customer_id} not found for invoice payment")
                return {"status": "skipped", "reason": "Customer not found"}
            
            customer_email = customer_row[0] if isinstance(customer_row, (list, tuple)) else customer_row.get('email')
            
            # Find referral that created this customer (to get broker info)
            referral_row = db.execute("""
                SELECT broker_id, broker_email, payout_type, commission_model
                FROM referrals
                WHERE customer_stripe_id = ? OR customer_email = ?
                ORDER BY created_at ASC
                LIMIT 1
            """, (customer_id, customer_email)).fetchone()
            
            if not referral_row:
                print(f"⚠️ No referral found for customer {customer_email}")
                return {"status": "skipped", "reason": "No referral found"}
            
            if isinstance(referral_row, dict):
                broker_ref_code = referral_row.get('broker_id')
                broker_email = referral_row.get('broker_email', '')
                payout_type = referral_row.get('payout_type', 'bounty')
                commission_model = referral_row.get('commission_model', 'bounty')
            else:
                broker_ref_code = referral_row[0] if len(referral_row) > 0 else None
                broker_email = referral_row[1] if len(referral_row) > 1 else ''
                payout_type = referral_row[2] if len(referral_row) > 2 else 'bounty'
                commission_model = referral_row[3] if len(referral_row) > 3 else 'bounty'
            
            # Only create earning event if broker has recurring commission model
            if commission_model == 'recurring' or payout_type == 'recurring':
                # Get broker info
                broker = db.execute("""
                    SELECT * FROM brokers WHERE referral_code = ?
                """, (broker_ref_code,)).fetchone()
                
                if broker:
                    # Create new earning event for this monthly payment
                    payout_amount = 50.00  # $50/month recurring
                    hold_until = datetime.now() + timedelta(days=60)
                    clawback_until = datetime.now() + timedelta(days=90)
                    
                    db.execute("""
                        INSERT INTO referrals 
                        (broker_id, broker_email, customer_email, customer_stripe_id,
                         amount, payout, payout_type, status, 
                         hold_until, clawback_until, created_at, payment_date)
                        VALUES (?, ?, ?, ?, ?, ?, 'recurring', 'on_hold', ?, ?, datetime('now'), datetime('now'))
                    """, (
                        broker_ref_code,
                        broker_email,
                        customer_email,
                        customer_id,
                        amount_paid,
                        payout_amount,
                        hold_until,
                        clawback_until
                    ))
                    
                    db.commit()
                    print(f"✓ Recurring payment earning event created: {customer_email} → {broker_email} (${payout_amount})")
            
            return {"status": "processed", "event_type": "invoice.payment_succeeded"}
        
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
            
            # Update all referrals for this customer to CANCELED status
            cursor.execute("""
                UPDATE referrals
                SET status = 'CANCELED'
                WHERE customer_stripe_id = ? OR customer_email = (
                    SELECT email FROM customers WHERE stripe_customer_id = ?
                )
            """, (customer_id, customer_id))
            
            updated_count = cursor.rowcount
            if updated_count > 0:
                print(f"✓ Updated {updated_count} referral(s) to CANCELED for customer {customer_id}")
            
            # Check for clawback eligibility (if paid within 90 days)
            cursor.execute("""
                SELECT id, payout, status, paid_at, created_at
                FROM referrals
                WHERE (customer_stripe_id = ? OR customer_email = (
                    SELECT email FROM customers WHERE stripe_customer_id = ?
                ))
                AND status = 'paid'
                AND paid_at IS NOT NULL
            """, (customer_id, customer_id))
            
            paid_referrals = cursor.fetchall()
            for ref in paid_referrals:
                ref_id = ref[0] if isinstance(ref, (list, tuple)) else ref.get('id')
                paid_at = ref[3] if isinstance(ref, (list, tuple)) else ref.get('paid_at')
                
                if paid_at:
                    try:
                        if isinstance(paid_at, str):
                            paid_date = datetime.fromisoformat(paid_at.replace('Z', '+00:00'))
                        else:
                            paid_date = paid_at
                        days_since_paid = (datetime.now() - paid_date).days
                        
                        # If cancelled within 90 days of payment, mark for clawback
                        if days_since_paid < 90:
                            cursor.execute("""
                                UPDATE referrals
                                SET status = 'clawed_back',
                                    notes = 'Customer cancelled within 90 days of payment'
                                WHERE id = ?
                            """, (ref_id,))
                            print(f"🚨 CLAWBACK: Referral {ref_id} cancelled {days_since_paid} days after payment")
                    except Exception as e:
                        print(f"⚠️ Error processing clawback for referral {ref_id}: {e}")
            
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
            
            # Update referrals to PAST_DUE status
            db.execute("""
                UPDATE referrals
                SET status = 'PAST_DUE'
                WHERE customer_stripe_id = ? AND status = 'on_hold'
            """, (customer_id,))
            
            db.commit()
        
        # Chargeback/dispute
        elif event['type'] in ['charge.dispute.created', 'charge.refunded']:
            charge = event['data']['object']
            customer_id = charge.get('customer')
            
            if customer_id:
                # Update referrals to REFUNDED or CHARGEBACK status
                status_to_set = 'REFUNDED' if event['type'] == 'charge.refunded' else 'CHARGEBACK'
                
                db.execute("""
                    UPDATE referrals
                    SET status = ?
                    WHERE customer_stripe_id = ? AND status IN ('on_hold', 'ready_to_pay', 'paid')
                """, (status_to_set, customer_id))
                
                db.commit()
                print(f"✓ Updated referrals to {status_to_set} for customer {customer_id}")
        
        return {"status": "success"}
    finally:
        db.close()

def send_welcome_email(email: str, temp_password: str):
    """Send welcome email with login credentials"""
    try:
        # Try Resend first (if configured)
        resend_key = os.environ.get("RESEND_API_KEY")
        if resend_key:
            resend.api_key = resend_key
            from_email = os.environ.get("SMTP_FROM_EMAIL", "onboarding@resend.dev")
            
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
            
            params = {
                "from": from_email,
                "to": [email],
                "subject": "🎉 Welcome to LienDeadline - Your Account is Ready",
                "html": html
            }
            
            response = resend.Emails.send(params)
            print(f"✅ Welcome email sent via Resend to {email}: {response.get('id', 'N/A')}")
            return True
        else:
            # Fallback: Try SMTP if Resend not configured
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
        resend_key = os.environ.get("RESEND_API_KEY")
        if resend_key:
            resend.api_key = resend_key
            from_email = os.environ.get("SMTP_FROM_EMAIL", "onboarding@resend.dev")
            
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
                        <li>Commissions paid after 60-day customer retention period</li>
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
            
            params = {
                "from": from_email,
                "to": [email],
                "subject": "🎉 Welcome to LienDeadline Partner Program!",
                "html": html
            }
            
            response = resend.Emails.send(params)
            print(f"✅ Broker welcome email sent via Resend to {email}: {response.get('id', 'N/A')}")
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
            You earn $500 per signup (after 60 days).
            
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
        resend_key = os.environ.get("RESEND_API_KEY")
        if resend_key:
            resend.api_key = resend_key
            from_email = os.environ.get("SMTP_FROM_EMAIL", "onboarding@resend.dev")
            
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
                    <p style="margin: 10px 0;"><strong>Commission Status:</strong> <span style="color: #f59e0b; font-weight: bold;">Pending (60-day retention period)</span></p>
                    <p style="margin: 10px 0;"><strong>Commission Amount:</strong> <span style="color: #059669; font-size: 20px; font-weight: bold;">$500</span> (one-time bounty)</p>
                </div>
                
                <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px; margin: 20px 0;">
                    <p style="margin: 0; color: #92400e;">
                        <strong>⏰ Payment Timeline:</strong> Your commission will be paid after the customer completes their 60-day retention period. You'll receive an email when payment is processed.
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
            
            params = {
                "from": from_email,
                "to": [broker_email],
                "subject": "💰 New Referral - $500 Commission Earned!",
                "html": html
            }
            
            response = resend.Emails.send(params)
            print(f"✅ Broker notification sent via Resend to {broker_email}: {response.get('id', 'N/A')}")
            return True
        else:
            print(f"⚠️ RESEND_API_KEY not set - skipping broker notification to {broker_email}")
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
    """Send calculation results via email using Resend"""
    try:
        # Get Resend API key from environment variable
        resend_api_key = os.environ.get("RESEND_API_KEY")
        if not resend_api_key:
            raise HTTPException(status_code=500, detail="Resend API key not configured. Please set RESEND_API_KEY environment variable.")
        
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
        
        resend.api_key = resend_api_key
        from_email = os.environ.get("SMTP_FROM_EMAIL", "onboarding@resend.dev")
        
        params = {
            "from": from_email,
            "to": [to_email],
            "subject": "Your Lien Deadline Calculation - LienDeadline.com",
            "html": html_content
        }
        
        response = resend.Emails.send(params)
        
        return {"status": "success", "message": "Email sent successfully!", "resend_id": response.get('id', 'N/A')}
        
    except Exception as e:
        print(f"Resend error: {str(e)}")
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

@app.get("/api/admin/setup-referrals-table")
async def setup_referrals_table(username: str = Depends(verify_admin)):
    """One-time setup to create referrals table - works with PostgreSQL and SQLite"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create referrals table (PostgreSQL compatible)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS referrals (
                        id SERIAL PRIMARY KEY,
                        broker_id VARCHAR(255) NOT NULL,
                        broker_email VARCHAR(255) NOT NULL,
                        customer_email VARCHAR(255) NOT NULL,
                        customer_stripe_id VARCHAR(255),
                        amount DECIMAL(10,2) NOT NULL DEFAULT 299.00,
                        payout DECIMAL(10,2) NOT NULL,
                        payout_type VARCHAR(50) NOT NULL,
                        status VARCHAR(50) DEFAULT 'on_hold',
                        fraud_flags TEXT,
                        hold_until DATE,
                        clawback_until DATE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP,
                        FOREIGN KEY (broker_id) REFERENCES brokers(referral_code)
                    )
                """)
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_broker_id ON referrals(broker_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_customer_email ON referrals(customer_email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_created_at ON referrals(created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_hold_until ON referrals(hold_until)")
            else:
                # SQLite version
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS referrals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_id TEXT NOT NULL,
                        broker_email TEXT NOT NULL,
                        customer_email TEXT NOT NULL,
                        customer_stripe_id TEXT,
                        amount REAL NOT NULL DEFAULT 299.00,
                        payout REAL NOT NULL,
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
                
                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_broker_id ON referrals(broker_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_customer_email ON referrals(customer_email)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_created_at ON referrals(created_at)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrals_hold_until ON referrals(hold_until)")
            
            conn.commit()
            
            return {
                "success": True,
                "message": "Referrals table created successfully",
                "db_type": DB_TYPE
            }
            
    except Exception as e:
        print(f"❌ Error creating referrals table: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/api/admin/brokers")
async def get_brokers_api(username: str = Depends(verify_admin)):
    """Return list of brokers with payment info"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get brokers with payment method and payment tracking (PostgreSQL compatible)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email, referrals, earned, status, payment_method, 
                           commission_model, referral_code,
                           COALESCE(payment_status, 'pending_first_payment') as payment_status,
                           last_payment_date, total_paid
                    FROM brokers
                    WHERE status IN ('approved', 'active')
                    ORDER BY created_at DESC NULLS LAST, id DESC
                """)
            else:
                cursor.execute("""
                    SELECT id, name, email, referrals, earned, status, payment_method, 
                           commission_model, referral_code,
                           COALESCE(payment_status, 'pending_first_payment') as payment_status,
                           last_payment_date, total_paid
                    FROM brokers
                    WHERE status IN ('approved', 'active') OR status IS NULL
                    ORDER BY created_at DESC, id DESC
                """)
            
            rows = cursor.fetchall()
            
            brokers_list = []
            for row in rows:
                if isinstance(row, dict):
                    broker_dict = {
                        "id": row.get('id'),
                "name": row.get('name') or row.get('email') or 'N/A',
                "email": row.get('email') or 'N/A',
                "referrals": row.get('referrals') or 0,
                "earned": float(row.get('earned') or 0),
                        "status": row.get('status') or 'pending',
                        "payment_method": row.get('payment_method'),
                        "commission_model": row.get('commission_model') or row.get('model'),
                        "referral_code": row.get('referral_code') or row.get('id'),
                        "payment_status": row.get('payment_status') or 'pending_first_payment',
                        "last_payment_date": row.get('last_payment_date'),
                        "total_paid": float(row.get('total_paid') or 0)
                    }
                else:
                    broker_dict = {
                        "id": row[0] if len(row) > 0 else None,
                        "name": row[1] if len(row) > 1 and row[1] else (row[2] if len(row) > 2 else 'N/A'),
                        "email": row[2] if len(row) > 2 else 'N/A',
                        "referrals": row[3] if len(row) > 3 else 0,
                        "earned": float(row[4] if len(row) > 4 else 0),
                        "status": row[5] if len(row) > 5 else 'pending',
                        "payment_method": row[6] if len(row) > 6 else None,
                        "commission_model": row[7] if len(row) > 7 else None,
                        "referral_code": row[8] if len(row) > 8 else (row[0] if len(row) > 0 else None),
                        "payment_status": row[9] if len(row) > 9 else 'pending_first_payment',
                        "last_payment_date": row[10] if len(row) > 10 else None,
                        "total_paid": float(row[11] if len(row) > 11 else 0)
                    }
                brokers_list.append(broker_dict)
            
            return {"brokers": brokers_list}
            
    except Exception as e:
        print(f"Error in get_brokers_api: {e}")
        import traceback
        traceback.print_exc()
        return {"brokers": []}

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
        # (You'll implement this later with EmailJS or Resend)
        
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
def send_email_sync(to_email: str, subject: str, body: str):
    """Synchronous email sending function with timeout=10 on SMTP connection"""
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER") or os.getenv("SMTP_EMAIL") or "trendtweakers00@gmail.com"
    smtp_password = (os.getenv("SMTP_PASSWORD") or "").replace(" ", "")  # Remove spaces from Gmail app password

    if not smtp_password:
        raise RuntimeError("SMTP_PASSWORD missing")

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    # ✅ timeout=10 is the key: prevents indefinite hang → Cloudflare 524
    with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)

class TestEmailIn(BaseModel):
    to: str

@app.post("/api/v1/test-email")
async def test_email(payload: TestEmailIn, background_tasks: BackgroundTasks):
    """Test email configuration - REMOVE AFTER TESTING"""
    logger = logging.getLogger(__name__)
    
    def _job():
        try:
            send_email_sync(
                to_email=payload.to,
                subject="LienDeadline test email",
                body="If you received this, SMTP works.",
            )
            logger.info("TEST_EMAIL_SENT to=%s", payload.to)
        except Exception as e:
            logger.error("TEST_EMAIL_FAILED to=%s err=%s", payload.to, e)
            traceback.print_exc()

    background_tasks.add_task(_job)
    return {"queued": True}

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
        resend_key = os.environ.get("RESEND_API_KEY")
        if resend_key:
            resend.api_key = resend_key
            from_email = os.environ.get("SMTP_FROM_EMAIL", "onboarding@resend.dev")
            
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
            
            params = {
                "from": from_email,
                "to": [email],
                "subject": "Reset Your LienDeadline Password",
                "html": html_content
            }
            
            response = resend.Emails.send(params)
            print(f"✅ Password reset email sent via Resend to {email}: {response.get('id', 'N/A')}")
            return True
        else:
            print(f"⚠️ Resend not configured - Reset link: {reset_link}")
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
    """Get broker dashboard data - requires approved status"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Normalize email (lowercase)
            email = email.lower().strip()
            
            # Verify broker exists AND is approved (accept both 'approved' and 'active' for backward compatibility)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, referral_code, commission_model, referral_link, short_code, status
                    FROM brokers
                    WHERE LOWER(email) = LOWER(%s)
                    AND status IN ('approved', 'active')
                """, (email,))
            else:
                cursor.execute("""
                    SELECT id, name, referral_code, commission_model, referral_link, short_code, status
                    FROM brokers
                    WHERE LOWER(email) = LOWER(?)
                    AND status IN ('approved', 'active')
            """, (email,))
            
            broker = cursor.fetchone()
            
            if not broker:
                print(f"❌ Broker not found: {email}")
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found. Please check your email address."}
                )
            
            # Handle different row formats
            if isinstance(broker, dict):
                broker_id = broker.get('id')
                broker_name = broker.get('name', '')
                referral_code = broker.get('referral_code', '')
                commission_model = broker.get('commission_model', 'bounty')
                referral_link = broker.get('referral_link', '')
                short_code = broker.get('short_code', '')
                status = broker.get('status', 'pending')
            else:
                    broker_id = broker[0]
                    broker_name = broker[1] if len(broker) > 1 else ''
                    referral_code = broker[2] if len(broker) > 2 else ''
                    commission_model = broker[3] if len(broker) > 3 else 'bounty'
                    referral_link = broker[4] if len(broker) > 4 else ''
                    short_code = broker[5] if len(broker) > 5 else ''
                    status = broker[6] if len(broker) > 6 else 'pending'
            
            # Check if broker is approved
            if status != 'approved':
                print(f"⚠️ Broker not approved: {email} (status: {status})")
                return JSONResponse(
                    status_code=403,
                    content={
                        "status": "error", 
                        "message": f"Your application is still {status}. Please wait for approval or contact support."
                    }
                )
            
            # Use short link if available, otherwise fallback to old format
            if referral_link:
                final_referral_link = referral_link
            elif short_code:
                final_referral_link = f"https://liendeadline.com/r/{short_code}"
            else:
                final_referral_link = f"https://liendeadline.com?ref={referral_code}"
            
            # Get referrals
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT 
                        customer_email,
                        amount,
                        payout,
                        payout_type,
                        status,
                        created_at
                    FROM referrals
                    WHERE broker_id = %s
                    ORDER BY created_at DESC
                """, (referral_code,))
            else:
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
                # Handle different row formats
                if isinstance(row, dict):
                    customer_email = row.get('customer_email', '')
                    amount = row.get('amount', 0) or 0
                    payout = row.get('payout', 0) or 0
                    payout_type = row.get('payout_type', '')
                    ref_status = row.get('status', 'pending')
                    created_at = row.get('created_at', '')
                else:
                    customer_email = row[0] if len(row) > 0 else ''
                    amount = row[1] if len(row) > 1 else 0
                    payout = row[2] if len(row) > 2 else 0
                    payout_type = row[3] if len(row) > 3 else ''
                    ref_status = row[4] if len(row) > 4 else 'pending'
                    created_at = row[5] if len(row) > 5 else ''
                
                referral = {
                    "customer_email": customer_email,
                    "amount": float(amount) if amount else 0,
                    "payout": float(payout) if payout else 0,
                    "payout_type": payout_type,
                    "status": ref_status,
                    "created_at": str(created_at) if created_at else ''
                }
                referrals.append(referral)
                
                if ref_status == 'pending' or ref_status == 'on_hold':
                    total_pending += float(payout) if payout else 0
                elif ref_status == 'paid':
                    total_paid += float(payout) if payout else 0
            
            print(f"✅ Broker dashboard loaded: {email} ({broker_name})")
            
            return {
                "broker_name": broker_name,
                "referral_code": referral_code,
                "referral_link": final_referral_link,
                "commission_model": commission_model or 'bounty',
                "total_referrals": len(referrals),
                "total_pending": float(total_pending),
                "total_paid": float(total_paid),
                "referrals": referrals
            }
            
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

# ==========================================
# BROKER AUTHENTICATION ENDPOINTS
# ==========================================

@app.post("/api/v1/broker/login")
async def broker_login(request: Request, data: dict):
    """Broker login with email and password"""
    try:
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email or not password:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Email and password are required"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get broker with password hash
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email, password_hash, status
                    FROM brokers
                    WHERE LOWER(email) = LOWER(%s)
                    AND status IN ('approved', 'active')
                """, (email,))
            else:
                cursor.execute("""
                    SELECT id, name, email, password_hash, status
                    FROM brokers
                    WHERE LOWER(email) = LOWER(?)
                    AND status IN ('approved', 'active')
                """, (email,))
            
            broker = cursor.fetchone()
            
            if not broker:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Invalid email or password"}
                )
            
            # Handle different row formats
            if isinstance(broker, dict):
                broker_id = broker.get('id')
                broker_name = broker.get('name', '')
                password_hash = broker.get('password_hash', '')
                status = broker.get('status', '')
            else:
                broker_id = broker[0]
                broker_name = broker[1] if len(broker) > 1 else ''
                broker_email = broker[2] if len(broker) > 2 else ''
                password_hash = broker[3] if len(broker) > 3 else ''
                status = broker[4] if len(broker) > 4 else ''
            
            # Check if password hash exists (for backward compatibility)
            if not password_hash:
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Password not set. Please contact support."}
                )
            
            # Verify password
            if not bcrypt.checkpw(password.encode(), password_hash.encode()):
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Invalid email or password"}
                )
            
            # Generate session token
            session_token = secrets.token_urlsafe(32)
            
            # Store session token (optional - can use cookies instead)
            # For now, return token in response
            
            print(f"✅ Broker login successful: {email} ({broker_name})")
            
            return {
                "status": "success",
                "message": "Login successful",
                "broker": {
                    "id": broker_id,
                    "name": broker_name,
                    "email": email
                },
                "token": session_token
            }
            
    except Exception as e:
        print(f"❌ Broker login error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Login failed. Please try again."}
        )

@app.post("/api/v1/broker/change-password")
async def broker_change_password(request: Request, data: dict):
    """Change broker password"""
    try:
        email = data.get('email', '').lower().strip()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not email or not old_password or not new_password:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Email, old password, and new password are required"}
            )
        
        if len(new_password) < 8:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "New password must be at least 8 characters"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get broker
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, password_hash
                    FROM brokers
                    WHERE LOWER(email) = LOWER(%s)
                """, (email,))
            else:
                cursor.execute("""
                    SELECT id, password_hash
                    FROM brokers
                    WHERE LOWER(email) = LOWER(?)
                """, (email,))
            
            broker = cursor.fetchone()
            
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            # Handle different row formats
            if isinstance(broker, dict):
                broker_id = broker.get('id')
                password_hash = broker.get('password_hash', '')
            else:
                broker_id = broker[0]
                password_hash = broker[1] if len(broker) > 1 else ''
            
            # Verify old password
            if not password_hash or not bcrypt.checkpw(old_password.encode(), password_hash.encode()):
                return JSONResponse(
                    status_code=401,
                    content={"status": "error", "message": "Invalid old password"}
                )
            
            # Hash new password
            new_password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            
            # Update password
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE brokers
                    SET password_hash = %s
                    WHERE id = %s
                """, (new_password_hash, broker_id))
            else:
                cursor.execute("""
                    UPDATE brokers
                    SET password_hash = ?
                    WHERE id = ?
                """, (new_password_hash, broker_id))
            
            conn.commit()
            
            print(f"✅ Password changed for broker: {email}")
            
            return {
                "status": "success",
                "message": "Password changed successfully"
            }
            
    except Exception as e:
        print(f"❌ Password change error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Password change failed. Please try again."}
        )

@app.post("/api/v1/broker/request-password-reset")
async def broker_request_password_reset(request: Request, data: dict):
    """Request password reset for broker"""
    try:
        email = data.get('email', '').lower().strip()
        
        if not email:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Email is required"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Check if broker exists
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email
                    FROM brokers
                    WHERE LOWER(email) = LOWER(%s)
                    AND status IN ('approved', 'active')
                """, (email,))
            else:
                cursor.execute("""
                    SELECT id, name, email
                    FROM brokers
                    WHERE LOWER(email) = LOWER(?)
                    AND status IN ('approved', 'active')
                """, (email,))
            
            broker = cursor.fetchone()
            
            # Always return success (don't reveal if email exists)
            if not broker:
                print(f"⚠️ Password reset requested for non-existent broker: {email}")
                return {
                    "status": "success",
                    "message": "If the email exists, a password reset link has been sent."
                }
            
            # Handle different row formats
            if isinstance(broker, dict):
                broker_id = broker.get('id')
                broker_name = broker.get('name', '')
            else:
                broker_id = broker[0]
                broker_name = broker[1] if len(broker) > 1 else ''
            
            # Generate reset token
            reset_token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=24)  # 24 hour expiry
            
            # Create password_reset_tokens table if it doesn't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_password_reset_tokens (
                        id SERIAL PRIMARY KEY,
                        email VARCHAR(255) NOT NULL,
                        token VARCHAR(255) UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        used BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broker_reset_token ON broker_password_reset_tokens(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broker_reset_email ON broker_password_reset_tokens(email)")
                
                cursor.execute("""
                    INSERT INTO broker_password_reset_tokens (email, token, expires_at)
                    VALUES (%s, %s, %s)
                """, (email, reset_token, expires_at))
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_password_reset_tokens (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL,
                        token TEXT UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        used INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broker_reset_token ON broker_password_reset_tokens(token)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_broker_reset_email ON broker_password_reset_tokens(email)")
                
                cursor.execute("""
                    INSERT INTO broker_password_reset_tokens (email, token, expires_at)
                    VALUES (?, ?, ?)
                """, (email, reset_token, expires_at))
            
            conn.commit()
            
            # Send reset email
            reset_link = f"https://liendeadline.com/broker-reset-password.html?token={reset_token}"
            send_broker_password_reset_email(email, broker_name, reset_link)
            
            print(f"✅ Password reset token generated for broker: {email}")
            
            return {
                "status": "success",
                "message": "If the email exists, a password reset link has been sent."
            }
            
    except Exception as e:
        print(f"❌ Password reset request error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "success",
            "message": "If the email exists, a password reset link has been sent."
        }

@app.post("/api/v1/broker/reset-password")
async def broker_reset_password(request: Request, data: dict):
    """Reset broker password using token"""
    try:
        token = data.get('token', '')
        new_password = data.get('new_password', '')
        
        if not token or not new_password:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Token and new password are required"}
            )
        
        if len(new_password) < 8:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Password must be at least 8 characters"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get token
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT email, expires_at, used
                    FROM broker_password_reset_tokens
                    WHERE token = %s
                """, (token,))
            else:
                cursor.execute("""
                    SELECT email, expires_at, used
                    FROM broker_password_reset_tokens
                    WHERE token = ?
                """, (token,))
            
            token_data = cursor.fetchone()
            
            if not token_data:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Invalid or expired token"}
                )
            
            # Handle different row formats
            if isinstance(token_data, dict):
                email = token_data.get('email', '')
                expires_at = token_data.get('expires_at')
                used = token_data.get('used', False)
            else:
                email = token_data[0] if len(token_data) > 0 else ''
                expires_at = token_data[1] if len(token_data) > 1 else None
                used = token_data[2] if len(token_data) > 2 else False
            
            # Check if token is expired or used
            if used or (expires_at and datetime.now() > expires_at):
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Invalid or expired token"}
                )
            
            # Hash new password
            password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            
            # Update password
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE brokers
                    SET password_hash = %s
                    WHERE LOWER(email) = LOWER(%s)
                """, (password_hash, email))
                
                # Mark token as used
                cursor.execute("""
                    UPDATE broker_password_reset_tokens
                    SET used = TRUE
                    WHERE token = %s
                """, (token,))
            else:
                cursor.execute("""
                    UPDATE brokers
                    SET password_hash = ?
                    WHERE LOWER(email) = LOWER(?)
                """, (password_hash, email))
                
                # Mark token as used
                cursor.execute("""
                    UPDATE broker_password_reset_tokens
                    SET used = 1
                    WHERE token = ?
                """, (token,))
            
            conn.commit()
            
            print(f"✅ Password reset successful for broker: {email}")
            
            return {
                "status": "success",
                "message": "Password reset successful"
            }
            
    except Exception as e:
        print(f"❌ Password reset error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Password reset failed. Please try again."}
        )

# ==========================================
# BROKER PAYMENT INFORMATION ENDPOINTS
# ==========================================

@app.post("/api/v1/broker/payment-info")
async def save_broker_payment_info(request: Request, data: dict):
    """Save or update broker payment information (international support)"""
    try:
        email = data.get('email', '').lower().strip()
        payment_method = data.get('payment_method', '')
        payment_email = data.get('payment_email', '')
        
        # International payment fields
        iban = data.get('iban', '')
        swift_code = data.get('swift_code', '')
        bank_name = data.get('bank_name', '')
        bank_address = data.get('bank_address', '')
        account_holder_name = data.get('account_holder_name', '')
        crypto_wallet = data.get('crypto_wallet', '')
        crypto_currency = data.get('crypto_currency', '')
        tax_id = data.get('tax_id', '')
        
        if not email:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Email is required"}
            )
        
        # Import encryption utilities
        from api.encryption import encrypt_data
        
        # Encrypt sensitive data
        encrypted_iban = encrypt_data(iban) if iban else None
        encrypted_swift = encrypt_data(swift_code) if swift_code else None
        encrypted_crypto = encrypt_data(crypto_wallet) if crypto_wallet else None
        encrypted_tax_id = encrypt_data(tax_id) if tax_id else None
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Verify broker exists
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id FROM brokers
                    WHERE LOWER(email) = LOWER(%s)
                """, (email,))
            else:
                cursor.execute("""
                    SELECT id FROM brokers
                    WHERE LOWER(email) = LOWER(?)
                """, (email,))
            
            broker = cursor.fetchone()
            
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            # Update payment information (international fields)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE brokers
                    SET payment_method = %s,
                        payment_email = %s,
                        iban = %s,
                        swift_code = %s,
                        bank_name = %s,
                        bank_address = %s,
                        account_holder_name = %s,
                        crypto_wallet = %s,
                        crypto_currency = %s,
                        tax_id = %s
                    WHERE LOWER(email) = LOWER(%s)
                """, (payment_method, payment_email, encrypted_iban, encrypted_swift, 
                      bank_name, bank_address, account_holder_name, encrypted_crypto, 
                      crypto_currency, encrypted_tax_id, email))
            else:
                cursor.execute("""
                    UPDATE brokers
                    SET payment_method = ?,
                        payment_email = ?,
                        iban = ?,
                        swift_code = ?,
                        bank_name = ?,
                        bank_address = ?,
                        account_holder_name = ?,
                        crypto_wallet = ?,
                        crypto_currency = ?,
                        tax_id = ?
                    WHERE LOWER(email) = LOWER(?)
                """, (payment_method, payment_email, encrypted_iban, encrypted_swift,
                      bank_name, bank_address, account_holder_name, encrypted_crypto,
                      crypto_currency, encrypted_tax_id, email))
            
            conn.commit()
            
            print(f"✅ Payment info updated for broker: {email} (method: {payment_method})")
            
            return {
                "status": "success",
                "message": "Payment information saved successfully"
            }
            
    except Exception as e:
        print(f"❌ Payment info save error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to save payment information"}
        )

@app.get("/api/v1/broker/payment-info")
async def get_broker_payment_info(request: Request, email: str):
    """Get broker payment information (masked for security)"""
    try:
        email = email.lower().strip()
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get payment info (international fields)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT payment_method, payment_email, iban, swift_code, bank_name, 
                           bank_address, account_holder_name, crypto_wallet, crypto_currency, tax_id
                    FROM brokers
                    WHERE LOWER(email) = LOWER(%s)
                """, (email,))
            else:
                cursor.execute("""
                    SELECT payment_method, payment_email, iban, swift_code, bank_name, 
                           bank_address, account_holder_name, crypto_wallet, crypto_currency, tax_id
                    FROM brokers
                    WHERE LOWER(email) = LOWER(?)
                """, (email,))
            
            broker = cursor.fetchone()
            
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            # Handle different row formats
            if isinstance(broker, dict):
                payment_method = broker.get('payment_method', '')
                payment_email = broker.get('payment_email', '')
                iban = broker.get('iban', '')
                swift_code = broker.get('swift_code', '')
                bank_name = broker.get('bank_name', '')
                bank_address = broker.get('bank_address', '')
                account_holder_name = broker.get('account_holder_name', '')
                crypto_wallet = broker.get('crypto_wallet', '')
                crypto_currency = broker.get('crypto_currency', '')
                tax_id = broker.get('tax_id', '')
            else:
                payment_method = broker[0] if len(broker) > 0 else ''
                payment_email = broker[1] if len(broker) > 1 else ''
                iban = broker[2] if len(broker) > 2 else ''
                swift_code = broker[3] if len(broker) > 3 else ''
                bank_name = broker[4] if len(broker) > 4 else ''
                bank_address = broker[5] if len(broker) > 5 else ''
                account_holder_name = broker[6] if len(broker) > 6 else ''
                crypto_wallet = broker[7] if len(broker) > 7 else ''
                crypto_currency = broker[8] if len(broker) > 8 else ''
                tax_id = broker[9] if len(broker) > 9 else ''
            
            # Import encryption utilities
            from api.encryption import decrypt_data, mask_sensitive_data
            
            # Decrypt and mask sensitive data
            masked_iban = mask_sensitive_data(decrypt_data(iban), show_last=4) if iban else ''
            masked_swift = mask_sensitive_data(decrypt_data(swift_code), show_last=4) if swift_code else ''
            masked_crypto = mask_sensitive_data(decrypt_data(crypto_wallet), show_last=8) if crypto_wallet else ''
            masked_tax_id = mask_sensitive_data(decrypt_data(tax_id), show_last=4) if tax_id else ''
            
            return {
                "status": "success",
                "payment_info": {
                    "payment_method": payment_method,
                    "payment_email": payment_email,
                    "iban": masked_iban,
                    "swift_code": masked_swift,
                    "bank_name": bank_name,
                    "bank_address": bank_address,
                    "account_holder_name": account_holder_name,
                    "crypto_wallet": masked_crypto,
                    "crypto_currency": crypto_currency,
                    "tax_id": masked_tax_id
                }
            }
            
    except Exception as e:
        print(f"❌ Payment info get error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to retrieve payment information"}
        )

@app.get("/api/admin/migrate-payout-batches")
async def migrate_payout_batches(username: str = Depends(verify_admin)):
    """
    Migration endpoint to create broker_payout_batches table.
    Safe and idempotent - can be run multiple times.
    """
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payout_batches (
                        id SERIAL PRIMARY KEY,
                        broker_id INTEGER NOT NULL,
                        broker_name VARCHAR(255) NOT NULL,
                        broker_email VARCHAR(255) NOT NULL,
                        total_amount DECIMAL(10,2) NOT NULL,
                        currency VARCHAR(10) DEFAULT 'USD',
                        payment_method VARCHAR(50) NOT NULL,
                        transaction_id VARCHAR(255),
                        notes TEXT,
                        status VARCHAR(50) DEFAULT 'pending',
                        referral_ids TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP,
                        created_by_admin VARCHAR(255)
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_broker ON broker_payout_batches(broker_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_status ON broker_payout_batches(status)
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payout_batches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_id INTEGER NOT NULL,
                        broker_name TEXT NOT NULL,
                        broker_email TEXT NOT NULL,
                        total_amount REAL NOT NULL,
                        currency TEXT DEFAULT 'USD',
                        payment_method TEXT NOT NULL,
                        transaction_id TEXT,
                        notes TEXT,
                        status TEXT DEFAULT 'pending',
                        referral_ids TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP,
                        created_by_admin TEXT
                    )
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_broker ON broker_payout_batches(broker_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_batch_status ON broker_payout_batches(status)
                """)
            
            conn.commit()
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Payout batches migration completed successfully",
                    "database_type": DB_TYPE
                }
            )
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {str(e)}",
                "database_type": DB_TYPE,
                "traceback": traceback.format_exc()
            }
        )

@app.get("/api/admin/migrate-payout-ledger")
async def migrate_payout_ledger(username: str = Depends(verify_admin)):
    """
    Migration endpoint to add payout ledger columns to referrals table.
    Safe and idempotent - can be run multiple times.
    """
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                # Add payment_date column if it doesn't exist
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'referrals' 
                            AND column_name = 'payment_date'
                        ) THEN
                            ALTER TABLE referrals ADD COLUMN payment_date TIMESTAMP;
                            RAISE NOTICE 'Added payment_date column';
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'referrals' 
                            AND column_name = 'paid_batch_id'
                        ) THEN
                            ALTER TABLE referrals ADD COLUMN paid_batch_id VARCHAR(255);
                            RAISE NOTICE 'Added paid_batch_id column';
                        END IF;
                    END $$;
                """)
                
                # Update existing referrals: set payment_date = created_at if null
                cursor.execute("""
                    UPDATE referrals 
                    SET payment_date = created_at 
                    WHERE payment_date IS NULL
                """)
                
                # Add paid_batch_id column to broker_payments if it doesn't exist
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'broker_payments' 
                            AND column_name = 'paid_referral_ids'
                        ) THEN
                            ALTER TABLE broker_payments ADD COLUMN paid_referral_ids TEXT;
                            RAISE NOTICE 'Added paid_referral_ids column';
                        END IF;
                    END $$;
                """)
            else:
                # SQLite: Add columns if they don't exist
                try:
                    cursor.execute("ALTER TABLE referrals ADD COLUMN payment_date TIMESTAMP")
                except Exception:
                    pass  # Column already exists
                
                try:
                    cursor.execute("ALTER TABLE referrals ADD COLUMN paid_batch_id TEXT")
                except Exception:
                    pass  # Column already exists
                
                try:
                    cursor.execute("ALTER TABLE broker_payments ADD COLUMN paid_referral_ids TEXT")
                except Exception:
                    pass  # Column already exists
                
                # Update existing referrals: set payment_date = created_at if null
                cursor.execute("""
                    UPDATE referrals 
                    SET payment_date = created_at 
                    WHERE payment_date IS NULL
                """)
            
            conn.commit()
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Payout ledger migration completed successfully",
                    "database_type": DB_TYPE
                }
            )
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {str(e)}",
                "database_type": DB_TYPE,
                "traceback": traceback.format_exc()
            }
        )

@app.get("/api/admin/migrate-payment-tracking")
async def migrate_payment_tracking(username: str = Depends(verify_admin)):
    """Migration endpoint to add payment tracking columns to brokers table"""
    migrations = []
    db_type = None
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            db_type = DB_TYPE

            # Add payment tracking columns
            column_definitions = [
                ("first_payment_date", "TIMESTAMP"),
                ("last_payment_date", "TIMESTAMP"),
                ("next_payment_due", "TIMESTAMP"),
                ("total_paid", "DECIMAL(10,2) DEFAULT 0"),
                ("payment_status", "VARCHAR(50) DEFAULT 'pending_first_payment'")
            ]

            for col_name, col_type in column_definitions:
                if db_type == 'postgresql':
                    cursor.execute(f"""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name = 'brokers' AND column_name = '{col_name}'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN {col_name} {col_type};
                            END IF;
                        END $$;
                    """)
                    migrations.append(f'✅ Added column: {col_name}')
                else: # SQLite
                    try:
                        cursor.execute(f"ALTER TABLE brokers ADD COLUMN {col_name} {col_type}")
                        migrations.append(f'✅ Added column: {col_name}')
                    except Exception as e:
                        if "duplicate column name" in str(e).lower():
                            migrations.append(f'ℹ️ Column already exists: {col_name}')
                        else:
                            migrations.append(f'❌ Failed to add column {col_name}: {e}')

            conn.commit()
            return {
                "status": "success",
                "message": "Payment tracking migration completed",
                "migrations": migrations,
                "database_type": db_type
            }

    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {e}",
                "traceback": traceback.format_exc(),
                "database_type": db_type
            }
        )

@app.get("/api/admin/migrate-users-table")
async def migrate_users_table(username: str = Depends(verify_admin)):
    """
    Migration endpoint to create users table.
    Safe and idempotent - can be run multiple times.
    """
    from api.admin import ensure_users_table
    import traceback
    
    try:
        created = ensure_users_table()
        return {
            "status": "ok",
            "created": bool(created)  # Ensure boolean, not int
        }
    except Exception as e:
        error_repr = repr(e)
        error_msg = str(e)
        # Try to get SQLSTATE if available (PostgreSQL)
        sqlstate = getattr(e, 'pgcode', None) or getattr(e, 'sqlstate', None)
        
        # Build detailed error message
        if sqlstate:
            detail_msg = f"{error_repr} (SQLSTATE: {sqlstate})"
        else:
            detail_msg = error_repr
        
        # Log full exception
        print(f"❌ Migration error: {detail_msg}")
        print(f"   Error message: {error_msg}")
        traceback.print_exc()
        
        # Return JSON error response
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "detail": detail_msg
            }
        )

@app.get("/api/admin/migrate-payment-columns")
async def migrate_payment_columns(username: str = Depends(verify_admin)):
    """Migration endpoint to add international payment columns to brokers table"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                # PostgreSQL migration
                migrations = []
                
                # Add new international payment columns
                new_columns = [
                    ('payment_method', 'VARCHAR(50)'),
                    ('payment_email', 'VARCHAR(255)'),
                    ('iban', 'VARCHAR(255)'),
                    ('swift_code', 'VARCHAR(100)'),
                    ('bank_name', 'VARCHAR(255)'),
                    ('bank_address', 'TEXT'),
                    ('account_holder_name', 'VARCHAR(255)'),
                    ('crypto_wallet', 'VARCHAR(255)'),
                    ('crypto_currency', 'VARCHAR(50)'),
                    ('tax_id', 'VARCHAR(100)')
                ]
                
                for column_name, column_type in new_columns:
                    try:
                        cursor.execute(f"""
                            DO $$ 
                            BEGIN
                                IF NOT EXISTS (
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name = 'brokers' AND column_name = '{column_name}'
                                ) THEN
                                    ALTER TABLE brokers ADD COLUMN {column_name} {column_type};
                                END IF;
                            END $$;
                        """)
                        migrations.append(f"✅ Added column: {column_name}")
                        print(f"✅ Added column: {column_name}")
                    except Exception as e:
                        migrations.append(f"⚠️ Column {column_name}: {str(e)}")
                        print(f"⚠️ Column {column_name} error: {e}")
                
                # Remove old US-only columns (if they exist)
                old_columns = ['bank_account_number', 'bank_routing_number']
                for column_name in old_columns:
                    try:
                        cursor.execute(f"""
                            DO $$ 
                            BEGIN
                                IF EXISTS (
                                    SELECT 1 FROM information_schema.columns 
                                    WHERE table_name = 'brokers' AND column_name = '{column_name}'
                                ) THEN
                                    ALTER TABLE brokers DROP COLUMN {column_name};
                                END IF;
                            END $$;
                        """)
                        migrations.append(f"✅ Removed column: {column_name}")
                        print(f"✅ Removed column: {column_name}")
                    except Exception as e:
                        migrations.append(f"⚠️ Could not remove {column_name}: {str(e)}")
                        print(f"⚠️ Could not remove {column_name}: {e}")
                
                conn.commit()
                
                return {
                    "status": "success",
                    "message": "Migration completed",
                    "migrations": migrations,
                    "database_type": "postgresql"
                }
            else:
                # SQLite migration
                migrations = []
                
                # Add new columns
                new_columns = [
                    ('payment_method', 'TEXT'),
                    ('payment_email', 'TEXT'),
                    ('iban', 'TEXT'),
                    ('swift_code', 'TEXT'),
                    ('bank_name', 'TEXT'),
                    ('bank_address', 'TEXT'),
                    ('account_holder_name', 'TEXT'),
                    ('crypto_wallet', 'TEXT'),
                    ('crypto_currency', 'TEXT'),
                    ('tax_id', 'TEXT')
                ]
                
                for column_name, column_type in new_columns:
                    try:
                        cursor.execute(f"ALTER TABLE brokers ADD COLUMN {column_name} {column_type}")
                        migrations.append(f"✅ Added column: {column_name}")
                        print(f"✅ Added column: {column_name}")
                    except Exception as e:
                        if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                            migrations.append(f"ℹ️ Column {column_name} already exists")
                        else:
                            migrations.append(f"⚠️ Column {column_name}: {str(e)}")
                            print(f"⚠️ Column {column_name} error: {e}")
                
                # Note: SQLite doesn't support DROP COLUMN easily, so we'll keep old columns
                # They can be ignored in queries
                migrations.append("ℹ️ Old columns (bank_account_number, bank_routing_number) kept for compatibility")
                
                conn.commit()
                
                return {
                    "status": "success",
                    "message": "Migration completed",
                    "migrations": migrations,
                    "database_type": "sqlite",
                    "note": "Old columns kept for SQLite compatibility"
                }
            
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Migration failed: {str(e)}",
                "traceback": traceback.format_exc()
            }
        )

@app.get("/api/admin/broker-payment-info/{broker_id}")
async def get_broker_payment_info_admin(broker_id: int, username: str = Depends(verify_admin)):
    """Get broker payment information for admin (unmasked)"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get payment info (international fields)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email, payment_method, payment_email, iban, swift_code,
                           bank_name, bank_address, account_holder_name, crypto_wallet, 
                           crypto_currency, tax_id
                    FROM brokers
                    WHERE id = %s
                """, (broker_id,))
            else:
                cursor.execute("""
                    SELECT id, name, email, payment_method, payment_email, iban, swift_code,
                           bank_name, bank_address, account_holder_name, crypto_wallet, 
                           crypto_currency, tax_id
                    FROM brokers
                    WHERE id = ?
                """, (broker_id,))
            
            broker = cursor.fetchone()
            
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            # Handle different row formats
            if isinstance(broker, dict):
                broker_name = broker.get('name', '')
                broker_email = broker.get('email', '')
                payment_method = broker.get('payment_method', '')
                payment_email = broker.get('payment_email', '')
                iban = broker.get('iban', '')
                swift_code = broker.get('swift_code', '')
                bank_name = broker.get('bank_name', '')
                bank_address = broker.get('bank_address', '')
                account_holder_name = broker.get('account_holder_name', '')
                crypto_wallet = broker.get('crypto_wallet', '')
                crypto_currency = broker.get('crypto_currency', '')
                tax_id = broker.get('tax_id', '')
            else:
                broker_name = broker[1] if len(broker) > 1 else ''
                broker_email = broker[2] if len(broker) > 2 else ''
                payment_method = broker[3] if len(broker) > 3 else ''
                payment_email = broker[4] if len(broker) > 4 else ''
                iban = broker[5] if len(broker) > 5 else ''
                swift_code = broker[6] if len(broker) > 6 else ''
                bank_name = broker[7] if len(broker) > 7 else ''
                bank_address = broker[8] if len(broker) > 8 else ''
                account_holder_name = broker[9] if len(broker) > 9 else ''
                crypto_wallet = broker[10] if len(broker) > 10 else ''
                crypto_currency = broker[11] if len(broker) > 11 else ''
                tax_id = broker[12] if len(broker) > 12 else ''
            
            # Import encryption utilities
            from api.encryption import decrypt_data
            
            # Decrypt sensitive data for admin
            decrypted_iban = decrypt_data(iban) if iban else ''
            decrypted_swift = decrypt_data(swift_code) if swift_code else ''
            decrypted_crypto = decrypt_data(crypto_wallet) if crypto_wallet else ''
            decrypted_tax_id = decrypt_data(tax_id) if tax_id else ''
            
            return {
                "status": "success",
                "broker": {
                    "id": broker_id,
                    "name": broker_name,
                    "email": broker_email
                },
                "payment_info": {
                    "payment_method": payment_method,
                    "payment_email": payment_email,
                    "iban": decrypted_iban,
                    "swift_code": decrypted_swift,
                    "bank_name": bank_name,
                    "bank_address": bank_address,
                    "account_holder_name": account_holder_name,
                    "crypto_wallet": decrypted_crypto,
                    "crypto_currency": crypto_currency,
                    "tax_id": decrypted_tax_id
                }
            }
            
    except Exception as e:
        print(f"❌ Admin payment info get error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to retrieve payment information"}
        )

@app.get("/api/admin/payment-history")
async def get_payment_history(time_filter: str = "all", username: str = Depends(verify_admin)):
    """Get payment history for admin dashboard"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create broker_payments table if it doesn't exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payments (
                        id SERIAL PRIMARY KEY,
                        broker_id INTEGER NOT NULL,
                        broker_name VARCHAR(255) NOT NULL,
                        broker_email VARCHAR(255) NOT NULL,
                        amount DECIMAL(10,2) NOT NULL,
                        payment_method VARCHAR(50) NOT NULL,
                        transaction_id VARCHAR(255),
                        notes TEXT,
                        status VARCHAR(50) DEFAULT 'completed',
                        payment_date TIMESTAMP DEFAULT NOW(),
                        paid_at TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS broker_payments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        broker_id INTEGER NOT NULL,
                        broker_name TEXT NOT NULL,
                        broker_email TEXT NOT NULL,
                        amount REAL NOT NULL,
                        payment_method TEXT NOT NULL,
                        transaction_id TEXT,
                        notes TEXT,
                        status TEXT DEFAULT 'completed',
                        payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()
            
            # Build query based on time_filter
            if time_filter == "month":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= NOW() - INTERVAL '30 days'
                        ORDER BY bp.paid_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= datetime('now', '-30 days')
                        ORDER BY bp.paid_at DESC
                    """)
            elif time_filter == "week":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= NOW() - INTERVAL '7 days'
                        ORDER BY bp.paid_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= datetime('now', '-7 days')
                        ORDER BY bp.paid_at DESC
                    """)
            else:
                cursor.execute("""
                    SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                           bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                           bp.status, bp.paid_at, bp.created_at
                    FROM broker_payments bp
                    ORDER BY bp.paid_at DESC
                """)
            
            rows = cursor.fetchall()
            
            payments = []
            for row in rows:
                if isinstance(row, dict):
                    payments.append({
                        "id": row.get('id'),
                        "broker_id": row.get('broker_id'),
                        "broker_name": row.get('broker_name') or row.get('name'),
                        "broker_email": row.get('broker_email') or row.get('email'),
                        "amount": float(row.get('amount') or 0),
                        "payment_method": row.get('payment_method'),
                        "transaction_id": row.get('transaction_id'),
                        "notes": row.get('notes'),
                        "status": row.get('status') or 'completed',
                        "paid_at": row.get('paid_at') or row.get('created_at'),
                        "created_at": row.get('created_at')
                    })
                else:
                    payments.append({
                        "id": row[0] if len(row) > 0 else None,
                        "broker_id": row[1] if len(row) > 1 else None,
                        "broker_name": row[2] if len(row) > 2 else None,
                        "broker_email": row[3] if len(row) > 3 else None,
                        "amount": float(row[4] if len(row) > 4 else 0),
                        "payment_method": row[5] if len(row) > 5 else None,
                        "transaction_id": row[6] if len(row) > 6 else None,
                        "notes": row[7] if len(row) > 7 else None,
                        "status": row[8] if len(row) > 8 else 'completed',
                        "paid_at": row[9] if len(row) > 9 else None,
                        "created_at": row[10] if len(row) > 10 else None
                    })
            
            return {"payments": payments}
            
    except Exception as e:
        print(f"❌ Payment history error: {e}")
        import traceback
        traceback.print_exc()
        return {"payments": []}

@app.post("/api/admin/mark-paid")
async def mark_payment_paid(request: Request, username: str = Depends(verify_admin)):
    """Mark a broker payment as paid"""
    try:
        data = await request.json()
        broker_id = data.get('broker_id')
        amount = data.get('amount')
        payment_method = data.get('payment_method')
        transaction_id = data.get('transaction_id')
        notes = data.get('notes', '')
        
        if not broker_id or not amount or not payment_method or not transaction_id:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Missing required fields"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get broker info
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, name, email FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("SELECT id, name, email FROM brokers WHERE id = ?", (broker_id,))
            
            broker = cursor.fetchone()
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            if isinstance(broker, dict):
                broker_name = broker.get('name', 'Unknown')
                broker_email = broker.get('email', '')
            else:
                broker_name = broker[1] if len(broker) > 1 else 'Unknown'
                broker_email = broker[2] if len(broker) > 2 else ''
            
            # Get broker's current payment tracking info
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT first_payment_date, last_payment_date, total_paid, created_at, status
                    FROM brokers WHERE id = %s
                """, (broker_id,))
            else:
                cursor.execute("""
                    SELECT first_payment_date, last_payment_date, total_paid, created_at, status
                    FROM brokers WHERE id = ?
                """, (broker_id,))
            
            broker_info = cursor.fetchone()
            current_time = datetime.now()
            
            # Parse broker info
            if isinstance(broker_info, dict):
                first_payment_date = broker_info.get('first_payment_date')
                last_payment_date = broker_info.get('last_payment_date')
                total_paid = float(broker_info.get('total_paid') or 0)
                created_at = broker_info.get('created_at')
                broker_status = broker_info.get('status')
            else:
                first_payment_date = broker_info[0] if len(broker_info) > 0 else None
                last_payment_date = broker_info[1] if len(broker_info) > 1 else None
                total_paid = float(broker_info[2] if len(broker_info) > 2 else 0)
                created_at = broker_info[3] if len(broker_info) > 3 else None
                broker_status = broker_info[4] if len(broker_info) > 4 else None
            
            # Calculate next payment due (30 days after this payment)
            next_payment_due = current_time + timedelta(days=30)
            
            # Update broker payment tracking
            if DB_TYPE == 'postgresql':
                if first_payment_date is None:
                    # First payment
                    cursor.execute("""
                        UPDATE brokers 
                        SET first_payment_date = NOW(),
                            last_payment_date = NOW(),
                            next_payment_due = NOW() + INTERVAL '30 days',
                            total_paid = COALESCE(total_paid, 0) + %s,
                            payment_status = 'active'
                        WHERE id = %s
                    """, (amount, broker_id))
                else:
                    # Subsequent payment
                    cursor.execute("""
                        UPDATE brokers 
                        SET last_payment_date = NOW(),
                            next_payment_due = NOW() + INTERVAL '30 days',
                            total_paid = COALESCE(total_paid, 0) + %s
                        WHERE id = %s
                    """, (amount, broker_id))
            else:
                if first_payment_date is None:
                    # First payment
                    cursor.execute("""
                        UPDATE brokers 
                        SET first_payment_date = CURRENT_TIMESTAMP,
                            last_payment_date = CURRENT_TIMESTAMP,
                            next_payment_due = datetime('now', '+30 days'),
                            total_paid = COALESCE(total_paid, 0) + ?,
                            payment_status = 'active'
                        WHERE id = ?
                    """, (amount, broker_id))
                else:
                    # Subsequent payment
                    cursor.execute("""
                        UPDATE brokers 
                        SET last_payment_date = CURRENT_TIMESTAMP,
                            next_payment_due = datetime('now', '+30 days'),
                            total_paid = COALESCE(total_paid, 0) + ?
                        WHERE id = ?
                    """, (amount, broker_id))
            
            # Mark specific referral IDs as paid (using ledger if available)
            paid_referral_ids = []
            remaining_amount = float(amount)
            
            if PAYOUT_LEDGER_AVAILABLE:
                try:
                    # Get ledger to find eligible unpaid referrals
                    ledger = compute_broker_ledger(cursor, broker_id, DB_TYPE)
                    
                    # Find eligible unpaid earning events, sorted by eligible_at (oldest first)
                    eligible_events = [
                        event for event in ledger.earning_events
                        if event.amount_due_now > 0 and not event.is_paid
                    ]
                    eligible_events.sort(key=lambda e: e.eligible_at)
                    
                    # Mark referrals as paid up to the amount
                    for event in eligible_events:
                        if remaining_amount <= 0:
                            break
                        
                        amount_to_pay = min(float(event.amount_due_now), remaining_amount)
                        
                        # Update referral as paid
                        if DB_TYPE == 'postgresql':
                            cursor.execute("""
                                UPDATE referrals
                                SET paid_at = NOW(),
                                    status = 'paid',
                                    paid_batch_id = %s
                                WHERE id = %s
                            """, (transaction_id, event.referral_id))
                        else:
                            cursor.execute("""
                                UPDATE referrals
                                SET paid_at = CURRENT_TIMESTAMP,
                                    status = 'paid',
                                    paid_batch_id = ?
                                WHERE id = ?
                            """, (transaction_id, event.referral_id))
                        
                        paid_referral_ids.append(event.referral_id)
                        remaining_amount -= amount_to_pay
                        
                except Exception as ledger_error:
                    print(f"⚠️ Error using ledger for mark-paid, continuing without referral linking: {ledger_error}")
                    # Continue without linking referrals
            
            # Insert payment record
            paid_referral_ids_json = json.dumps(paid_referral_ids) if paid_referral_ids else None
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, broker_name, broker_email, amount, payment_method, transaction_id, notes, status, payment_date, paid_at, paid_referral_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', NOW(), NOW(), %s)
                """, (broker_id, broker_name, broker_email, amount, payment_method, transaction_id, notes, paid_referral_ids_json))
            else:
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, broker_name, broker_email, amount, payment_method, transaction_id, notes, status, payment_date, paid_at, paid_referral_ids)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
                """, (broker_id, broker_name, broker_email, amount, payment_method, transaction_id, notes, paid_referral_ids_json))
            
            conn.commit()
            
            return {
                "status": "success",
                "message": "Payment marked as paid",
                "payment_id": cursor.lastrowid if hasattr(cursor, 'lastrowid') else None,
                "is_first_payment": first_payment_date is None,
                "next_payment_due": next_payment_due.isoformat(),
                "paid_referral_ids": paid_referral_ids,
                "referrals_marked": len(paid_referral_ids)
            }
            
    except Exception as e:
        print(f"❌ Mark paid error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to mark payment as paid"}
        )

@app.get("/api/admin/payment-history/export")
async def export_payment_history_csv(time_filter: str = "all", username: str = Depends(verify_admin)):
    """Export payment history as CSV"""
    try:
        from fastapi.responses import Response
        from datetime import datetime
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Build query (same as payment history)
            if time_filter == "month":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= NOW() - INTERVAL '30 days'
                        ORDER BY bp.paid_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= datetime('now', '-30 days')
                        ORDER BY bp.paid_at DESC
                    """)
            elif time_filter == "week":
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= NOW() - INTERVAL '7 days'
                        ORDER BY bp.paid_at DESC
                    """)
                else:
                    cursor.execute("""
                        SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                               bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                               bp.status, bp.paid_at, bp.created_at
                        FROM broker_payments bp
                        WHERE bp.paid_at >= datetime('now', '-7 days')
                        ORDER BY bp.paid_at DESC
                    """)
            else:
                cursor.execute("""
                    SELECT bp.id, bp.broker_id, bp.broker_name, bp.broker_email, 
                           bp.amount, bp.payment_method, bp.transaction_id, bp.notes, 
                           bp.status, bp.paid_at, bp.created_at
                    FROM broker_payments bp
                    ORDER BY bp.paid_at DESC
                """)
            
            rows = cursor.fetchall()
            
            # Build CSV
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Date', 'Broker Name', 'Broker Email', 'Amount', 'Payment Method', 'Transaction ID', 'Status', 'Notes'])
            
            # Rows
            for row in rows:
                if isinstance(row, dict):
                    writer.writerow([
                        row.get('paid_at') or row.get('created_at') or '',
                        row.get('broker_name') or row.get('name') or '',
                        row.get('broker_email') or row.get('email') or '',
                        row.get('amount') or 0,
                        row.get('payment_method') or '',
                        row.get('transaction_id') or '',
                        row.get('status') or 'completed',
                        row.get('notes') or ''
                    ])
                else:
                    writer.writerow([
                        row[9] if len(row) > 9 else '',
                        row[2] if len(row) > 2 else '',
                        row[3] if len(row) > 3 else '',
                        row[4] if len(row) > 4 else 0,
                        row[5] if len(row) > 5 else '',
                        row[6] if len(row) > 6 else '',
                        row[8] if len(row) > 8 else 'completed',
                        row[7] if len(row) > 7 else ''
                    ])
            
            csv_content = output.getvalue()
            output.close()
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=payment-history-{time_filter}-{datetime.now().strftime('%Y-%m-%d')}.csv"
                }
            )
            
    except Exception as e:
        print(f"❌ Export CSV error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to export payment history"}
        )

@app.post("/api/admin/payout-batches/create")
async def create_payout_batch(request: Request, username: str = Depends(verify_admin)):
    """Create a payout batch and mark referrals as paid atomically"""
    try:
        data = await request.json()
        broker_id = data.get('broker_id')
        referral_ids = data.get('referral_ids', [])
        payment_method = data.get('payment_method')
        transaction_id = data.get('transaction_id', '')
        notes = data.get('notes', '')
        
        if not broker_id or not referral_ids or not payment_method:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "Missing required fields: broker_id, referral_ids, payment_method"}
            )
        
        if not isinstance(referral_ids, list) or len(referral_ids) == 0:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "referral_ids must be a non-empty array"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get broker info
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, name, email FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("SELECT id, name, email FROM brokers WHERE id = ?", (broker_id,))
            
            broker = cursor.fetchone()
            if not broker:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Broker not found"}
                )
            
            if isinstance(broker, dict):
                broker_name = broker.get('name', 'Unknown')
                broker_email = broker.get('email', '')
            else:
                broker_name = broker[1] if len(broker) > 1 else 'Unknown'
                broker_email = broker[2] if len(broker) > 2 else ''
            
            # Calculate total amount from selected referrals
            if DB_TYPE == 'postgresql':
                placeholders = ','.join(['%s'] * len(referral_ids))
                cursor.execute(f"""
                    SELECT COALESCE(SUM(payout), 0) as total
                    FROM referrals
                    WHERE id IN ({placeholders})
                    AND status != 'paid'
                """, referral_ids)
            else:
                placeholders = ','.join(['?'] * len(referral_ids))
                cursor.execute(f"""
                    SELECT COALESCE(SUM(payout), 0) as total
                    FROM referrals
                    WHERE id IN ({placeholders})
                    AND status != 'paid'
                """, referral_ids)
            
            total_result = cursor.fetchone()
            total_amount = 0.0
            if total_result:
                if isinstance(total_result, dict):
                    total_amount = float(total_result.get('total', 0))
                else:
                    total_amount = float(total_result[0] if len(total_result) > 0 else 0)
            
            if total_amount <= 0:
                return JSONResponse(
                    status_code=400,
                    content={"status": "error", "message": "Selected referrals have no unpaid amount or are already paid"}
                )
            
            # Generate batch ID if transaction_id not provided
            if not transaction_id:
                transaction_id = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
            
            # Create batch record
            referral_ids_json = json.dumps(referral_ids)
            current_time = datetime.now()
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO broker_payout_batches 
                    (broker_id, broker_name, broker_email, total_amount, currency, payment_method, 
                     transaction_id, notes, status, referral_ids, created_at, created_by_admin)
                    VALUES (%s, %s, %s, %s, 'USD', %s, %s, %s, 'pending', %s, NOW(), %s)
                    RETURNING id
                """, (broker_id, broker_name, broker_email, total_amount, payment_method, 
                      transaction_id, notes, referral_ids_json, username))
                
                batch_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    INSERT INTO broker_payout_batches 
                    (broker_id, broker_name, broker_email, total_amount, currency, payment_method, 
                     transaction_id, notes, status, referral_ids, created_at, created_by_admin)
                    VALUES (?, ?, ?, ?, 'USD', ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP, ?)
                """, (broker_id, broker_name, broker_email, total_amount, payment_method,
                      transaction_id, notes, referral_ids_json, username))
                
                batch_id = cursor.lastrowid
            
            # Mark referrals as paid atomically
            if DB_TYPE == 'postgresql':
                placeholders = ','.join(['%s'] * len(referral_ids))
                cursor.execute(f"""
                    UPDATE referrals
                    SET paid_at = NOW(),
                        status = 'paid',
                        paid_batch_id = %s
                    WHERE id IN ({placeholders})
                    AND status != 'paid'
                """, [transaction_id] + referral_ids)
            else:
                placeholders = ','.join(['?'] * len(referral_ids))
                cursor.execute(f"""
                    UPDATE referrals
                    SET paid_at = CURRENT_TIMESTAMP,
                        status = 'paid',
                        paid_batch_id = ?
                    WHERE id IN ({placeholders})
                    AND status != 'paid'
                """, [transaction_id] + referral_ids)
            
            # Create broker_payment record linking to batch
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, broker_name, broker_email, amount, payment_method, transaction_id, 
                     notes, status, payment_date, paid_at, paid_referral_ids)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed', NOW(), NOW(), %s)
                """, (broker_id, broker_name, broker_email, total_amount, payment_method,
                      transaction_id, notes, referral_ids_json))
            else:
                cursor.execute("""
                    INSERT INTO broker_payments 
                    (broker_id, broker_name, broker_email, amount, payment_method, transaction_id, 
                     notes, status, payment_date, paid_at, paid_referral_ids)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?)
                """, (broker_id, broker_name, broker_email, total_amount, payment_method,
                      transaction_id, notes, referral_ids_json))
            
            # Update batch status to completed
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE broker_payout_batches
                    SET status = 'completed',
                        paid_at = NOW()
                    WHERE id = %s
                """, (batch_id,))
            else:
                cursor.execute("""
                    UPDATE broker_payout_batches
                    SET status = 'completed',
                        paid_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (batch_id,))
            
            conn.commit()
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "message": "Payout batch created and referrals marked as paid",
                    "batch_id": batch_id,
                    "transaction_id": transaction_id,
                    "total_amount": float(total_amount),
                    "referrals_marked": len(referral_ids),
                    "referral_ids": referral_ids
                }
            )
            
    except Exception as e:
        print(f"❌ Create batch error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to create batch: {str(e)}"}
        )

@app.get("/api/admin/payout-batches/{broker_id}")
async def get_broker_batches(broker_id: int, username: str = Depends(verify_admin)):
    """Get all payout batches for a broker"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, total_amount, currency,
                           payment_method, transaction_id, notes, status, referral_ids,
                           created_at, paid_at, created_by_admin
                    FROM broker_payout_batches
                    WHERE broker_id = %s
                    ORDER BY created_at DESC
                """, (broker_id,))
            else:
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, total_amount, currency,
                           payment_method, transaction_id, notes, status, referral_ids,
                           created_at, paid_at, created_by_admin
                    FROM broker_payout_batches
                    WHERE broker_id = ?
                    ORDER BY created_at DESC
                """, (broker_id,))
            
            batches = cursor.fetchall()
            
            result = []
            for batch in batches:
                if isinstance(batch, dict):
                    referral_ids = json.loads(batch.get('referral_ids', '[]'))
                    result.append({
                        "id": batch.get('id'),
                        "broker_id": batch.get('broker_id'),
                        "broker_name": batch.get('broker_name'),
                        "broker_email": batch.get('broker_email'),
                        "total_amount": float(batch.get('total_amount', 0)),
                        "currency": batch.get('currency', 'USD'),
                        "payment_method": batch.get('payment_method'),
                        "transaction_id": batch.get('transaction_id'),
                        "notes": batch.get('notes'),
                        "status": batch.get('status'),
                        "referral_ids": referral_ids,
                        "referral_count": len(referral_ids),
                        "created_at": batch.get('created_at').isoformat() if batch.get('created_at') else None,
                        "paid_at": batch.get('paid_at').isoformat() if batch.get('paid_at') else None,
                        "created_by_admin": batch.get('created_by_admin')
                    })
                else:
                    referral_ids = json.loads(batch[10] if len(batch) > 10 else '[]')
                    result.append({
                        "id": batch[0] if len(batch) > 0 else None,
                        "broker_id": batch[1] if len(batch) > 1 else None,
                        "broker_name": batch[2] if len(batch) > 2 else None,
                        "broker_email": batch[3] if len(batch) > 3 else None,
                        "total_amount": float(batch[4] if len(batch) > 4 else 0),
                        "currency": batch[5] if len(batch) > 5 else 'USD',
                        "payment_method": batch[6] if len(batch) > 6 else None,
                        "transaction_id": batch[7] if len(batch) > 7 else None,
                        "notes": batch[8] if len(batch) > 8 else None,
                        "status": batch[9] if len(batch) > 9 else None,
                        "referral_ids": referral_ids,
                        "referral_count": len(referral_ids),
                        "created_at": batch[11].isoformat() if len(batch) > 11 and batch[11] else None,
                        "paid_at": batch[12].isoformat() if len(batch) > 12 and batch[12] else None,
                        "created_by_admin": batch[13] if len(batch) > 13 else None
                    })
            
            return JSONResponse(
                status_code=200,
                content={"batches": result}
            )
            
    except Exception as e:
        print(f"❌ Get batches error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to get batches: {str(e)}"}
        )

@app.get("/api/admin/payout-batches/export/{batch_id}")
async def export_batch_csv(batch_id: int, username: str = Depends(verify_admin)):
    """Export a payout batch as CSV"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get batch info
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, total_amount, currency,
                           payment_method, transaction_id, notes, status, referral_ids,
                           created_at, paid_at
                    FROM broker_payout_batches
                    WHERE id = %s
                """, (batch_id,))
            else:
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, total_amount, currency,
                           payment_method, transaction_id, notes, status, referral_ids,
                           created_at, paid_at
                    FROM broker_payout_batches
                    WHERE id = ?
                """, (batch_id,))
            
            batch = cursor.fetchone()
            if not batch:
                return JSONResponse(
                    status_code=404,
                    content={"status": "error", "message": "Batch not found"}
                )
            
            # Parse batch data
            if isinstance(batch, dict):
                referral_ids = json.loads(batch.get('referral_ids', '[]'))
                broker_name = batch.get('broker_name')
                broker_email = batch.get('broker_email')
                total_amount = batch.get('total_amount')
                transaction_id = batch.get('transaction_id')
                created_at = batch.get('created_at')
            else:
                referral_ids = json.loads(batch[10] if len(batch) > 10 else '[]')
                broker_name = batch[2] if len(batch) > 2 else None
                broker_email = batch[3] if len(batch) > 3 else None
                total_amount = batch[4] if len(batch) > 4 else 0
                transaction_id = batch[7] if len(batch) > 7 else None
                created_at = batch[11] if len(batch) > 11 else None
            
            # Get referral details
            if len(referral_ids) > 0:
                placeholders = ','.join(['%s'] * len(referral_ids)) if DB_TYPE == 'postgresql' else ','.join(['?'] * len(referral_ids))
                cursor.execute(f"""
                    SELECT id, customer_email, customer_stripe_id, payout, payout_type, payment_date
                    FROM referrals
                    WHERE id IN ({placeholders})
                    ORDER BY id
                """, referral_ids)
                
                referrals = cursor.fetchall()
            else:
                referrals = []
            
            # Build CSV
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Batch ID', 'Transaction ID', 'Broker Name', 'Broker Email', 
                           'Total Amount', 'Currency', 'Payment Method', 'Created At', 'Status'])
            writer.writerow([batch_id, transaction_id or '', broker_name or '', broker_email or '',
                           total_amount, 'USD', 'N/A', created_at.isoformat() if created_at else '', 'completed'])
            
            writer.writerow([])  # Empty row
            writer.writerow(['Referral Details'])
            writer.writerow(['Referral ID', 'Customer Email', 'Customer Stripe ID', 
                           'Amount', 'Type', 'Payment Date'])
            
            # Referral rows
            for ref in referrals:
                if isinstance(ref, dict):
                    writer.writerow([
                        ref.get('id'),
                        ref.get('customer_email', ''),
                        ref.get('customer_stripe_id', ''),
                        ref.get('payout', 0),
                        ref.get('payout_type', ''),
                        ref.get('payment_date', '').isoformat() if ref.get('payment_date') else ''
                    ])
                else:
                    writer.writerow([
                        ref[0] if len(ref) > 0 else '',
                        ref[1] if len(ref) > 1 else '',
                        ref[2] if len(ref) > 2 else '',
                        ref[3] if len(ref) > 3 else 0,
                        ref[4] if len(ref) > 4 else '',
                        ref[5].isoformat() if len(ref) > 5 and ref[5] else ''
                    ])
            
            csv_content = output.getvalue()
            output.close()
            
            return Response(
                content=csv_content,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=batch-{batch_id}-{datetime.now().strftime('%Y-%m-%d')}.csv"
                }
            )
            
    except Exception as e:
        print(f"❌ Export batch CSV error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to export batch CSV"}
        )

@app.get("/api/admin/debug/payout-data")
async def get_payout_debug_data(username: str = Depends(verify_admin)):
    """Get debug data for payout system (last 20 records of each type)"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get last 20 referrals
            # Check if subscription_id column exists
            has_subscription_id = False
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'referrals' AND column_name = 'subscription_id'
                    """)
                    has_subscription_id = cursor.fetchone() is not None
                else:
                    cursor.execute("PRAGMA table_info(referrals)")
                    columns = cursor.fetchall()
                    column_names = []
                    for col in columns:
                        if isinstance(col, (list, tuple)):
                            column_names.append(col[1] if len(col) > 1 else '')
                        elif isinstance(col, dict):
                            column_names.append(col.get('name', ''))
                    has_subscription_id = 'subscription_id' in column_names
            except Exception as e:
                print(f"⚠️ Could not check for subscription_id column: {e}")
                has_subscription_id = False
            
            if has_subscription_id:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                else:
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
            else:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, NULL as subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                else:
                    cursor.execute("""
                        SELECT id, broker_id, customer_email, customer_stripe_id, NULL as subscription_id,
                               status, payment_date, payout, payout_type, created_at, paid_at, paid_batch_id
                        FROM referrals
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
            
            referrals_rows = cursor.fetchall()
            referrals = []
            for row in referrals_rows:
                if isinstance(row, dict):
                    referrals.append({
                        "id": row.get('id'),
                        "broker_id": row.get('broker_id'),
                        "customer_email": row.get('customer_email') or '—',
                        "customer_stripe_id": row.get('customer_stripe_id') or '—',
                        "subscription_id": row.get('subscription_id') or '—',
                        "status": row.get('status') or '—',
                        "payment_date": row.get('payment_date').isoformat() if row.get('payment_date') else '—',
                        "payout": float(row.get('payout', 0)) if row.get('payout') else 0,
                        "payout_type": row.get('payout_type') or '—',
                        "created_at": row.get('created_at').isoformat() if row.get('created_at') else '—',
                        "paid_at": row.get('paid_at').isoformat() if row.get('paid_at') else '—',
                        "paid_batch_id": row.get('paid_batch_id') or '—'
                    })
                else:
                    referrals.append({
                        "id": row[0] if len(row) > 0 else None,
                        "broker_id": row[1] if len(row) > 1 else None,
                        "customer_email": row[2] if len(row) > 2 else '—',
                        "customer_stripe_id": row[3] if len(row) > 3 else '—',
                        "subscription_id": row[4] if len(row) > 4 else '—',
                        "status": row[5] if len(row) > 5 else '—',
                        "payment_date": row[6].isoformat() if len(row) > 6 and row[6] else '—',
                        "payout": float(row[7]) if len(row) > 7 and row[7] else 0,
                        "payout_type": row[8] if len(row) > 8 else '—',
                        "created_at": row[9].isoformat() if len(row) > 9 and row[9] else '—',
                        "paid_at": row[10].isoformat() if len(row) > 10 and row[10] else '—',
                        "paid_batch_id": row[11] if len(row) > 11 else '—'
                    })
            
            # Get last 20 broker_payments
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, amount, payment_method, 
                           transaction_id, status, created_at, paid_at
                    FROM broker_payments
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
            else:
                cursor.execute("""
                    SELECT id, broker_id, broker_name, broker_email, amount, payment_method, 
                           transaction_id, status, created_at, paid_at
                    FROM broker_payments
                    ORDER BY created_at DESC
                    LIMIT 20
                """)
            
            payments_rows = cursor.fetchall()
            payments = []
            for row in payments_rows:
                if isinstance(row, dict):
                    payments.append({
                        "id": row.get('id'),
                        "broker_id": row.get('broker_id'),
                        "broker_name": row.get('broker_name') or '—',
                        "broker_email": row.get('broker_email') or '—',
                        "amount": float(row.get('amount', 0)) if row.get('amount') else 0,
                        "payment_method": row.get('payment_method') or '—',
                        "transaction_id": row.get('transaction_id') or '—',
                        "status": row.get('status') or '—',
                        "created_at": row.get('created_at').isoformat() if row.get('created_at') else '—',
                        "paid_at": row.get('paid_at').isoformat() if row.get('paid_at') else '—'
                    })
                else:
                    payments.append({
                        "id": row[0] if len(row) > 0 else None,
                        "broker_id": row[1] if len(row) > 1 else None,
                        "broker_name": row[2] if len(row) > 2 else '—',
                        "broker_email": row[3] if len(row) > 3 else '—',
                        "amount": float(row[4]) if len(row) > 4 and row[4] else 0,
                        "payment_method": row[5] if len(row) > 5 else '—',
                        "transaction_id": row[6] if len(row) > 6 else '—',
                        "status": row[7] if len(row) > 7 else '—',
                        "created_at": row[8].isoformat() if len(row) > 8 and row[8] else '—',
                        "paid_at": row[9].isoformat() if len(row) > 9 and row[9] else '—'
                    })
            
            # Get last 20 payout batches
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id, broker_id, broker_name, broker_email, total_amount, 
                               payment_method, transaction_id, status, created_at, paid_at
                        FROM broker_payout_batches
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                else:
                    cursor.execute("""
                        SELECT id, broker_id, broker_name, broker_email, total_amount, 
                               payment_method, transaction_id, status, created_at, paid_at
                        FROM broker_payout_batches
                        ORDER BY created_at DESC
                        LIMIT 20
                    """)
                
                batches_rows = cursor.fetchall()
                batches = []
                for row in batches_rows:
                    if isinstance(row, dict):
                        batches.append({
                            "id": row.get('id'),
                            "broker_id": row.get('broker_id'),
                            "broker_name": row.get('broker_name') or '—',
                            "broker_email": row.get('broker_email') or '—',
                            "total_amount": float(row.get('total_amount', 0)) if row.get('total_amount') else 0,
                            "payment_method": row.get('payment_method') or '—',
                            "transaction_id": row.get('transaction_id') or '—',
                            "status": row.get('status') or '—',
                            "created_at": row.get('created_at').isoformat() if row.get('created_at') else '—',
                            "paid_at": row.get('paid_at').isoformat() if row.get('paid_at') else '—'
                        })
                    else:
                        batches.append({
                            "id": row[0] if len(row) > 0 else None,
                            "broker_id": row[1] if len(row) > 1 else None,
                            "broker_name": row[2] if len(row) > 2 else '—',
                            "broker_email": row[3] if len(row) > 3 else '—',
                            "total_amount": float(row[4]) if len(row) > 4 and row[4] else 0,
                            "payment_method": row[5] if len(row) > 5 else '—',
                            "transaction_id": row[6] if len(row) > 6 else '—',
                            "status": row[7] if len(row) > 7 else '—',
                            "created_at": row[8].isoformat() if len(row) > 8 and row[8] else '—',
                            "paid_at": row[9].isoformat() if len(row) > 9 and row[9] else '—'
                        })
            except Exception as e:
                # Table might not exist yet
                print(f"⚠️ broker_payout_batches table not found: {e}")
                batches = []
            
            return JSONResponse(
                status_code=200,
                content={
                    "referrals": referrals,
                    "payments": payments,
                    "batches": batches
                }
            )
            
    except Exception as e:
        print(f"❌ Debug data error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to get debug data: {str(e)}"}
        )

@app.get("/api/admin/broker-ledger/{broker_id}")
async def get_broker_ledger(broker_id: int, username: str = Depends(verify_admin)):
    """Get full payout ledger for a specific broker"""
    try:
        if not PAYOUT_LEDGER_AVAILABLE:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "message": "Payout ledger service not available"}
            )
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            ledger = compute_broker_ledger(cursor, broker_id, DB_TYPE)
            return JSONResponse(
                status_code=200,
                content=ledger.to_dict()
            )
    except Exception as e:
        print(f"❌ Broker ledger error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to compute ledger: {str(e)}"}
        )

@app.get("/api/admin/list-broker-ids")
async def list_broker_ids(username: str = Depends(verify_admin)):
    """List all broker IDs for testing"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Query brokers - check what columns exist
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, name, email, commission_model, approved_at
                    FROM brokers
                    ORDER BY id
                """)
            else:
                cursor.execute("""
                    SELECT id, name, email, commission_model, approved_at
                    FROM brokers
                    ORDER BY id
                """)
            
            brokers = []
            for row in cursor.fetchall():
                if isinstance(row, dict):
                    brokers.append({
                        "id": row.get('id'),
                        "name": row.get('name', ''),
                        "email": row.get('email', ''),
                        "commission_model": row.get('commission_model', 'bounty'),
                        "approved_at": row.get('approved_at').isoformat() if row.get('approved_at') else None
                    })
                else:
                    brokers.append({
                        "id": row[0] if len(row) > 0 else None,
                        "name": row[1] if len(row) > 1 else '',
                        "email": row[2] if len(row) > 2 else '',
                        "commission_model": row[3] if len(row) > 3 else 'bounty',
                        "approved_at": row[4].isoformat() if len(row) > 4 and row[4] else None
                    })
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "brokers": brokers,
                    "count": len(brokers)
                }
            )
    except Exception as e:
        print(f"❌ Error listing broker IDs: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/admin/test-set-broker-ready/{broker_id}")
async def test_set_broker_ready(broker_id: int, username: str = Depends(verify_admin)):
    """TEST ONLY: Simulate broker ready for payment"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get broker
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, name, email, referral_code, commission_model FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("SELECT id, name, email, referral_code, commission_model FROM brokers WHERE id = ?", (broker_id,))
            
            broker_row = cursor.fetchone()
            if not broker_row:
                raise HTTPException(status_code=404, detail=f"Broker {broker_id} not found")
            
            # Parse broker data
            if isinstance(broker_row, dict):
                broker_name = broker_row.get('name', '')
                broker_email = broker_row.get('email', '')
                referral_code = broker_row.get('referral_code', '')
                commission_model = broker_row.get('commission_model', 'bounty')
            else:
                broker_name = broker_row[1] if len(broker_row) > 1 else ''
                broker_email = broker_row[2] if len(broker_row) > 2 else ''
                referral_code = broker_row[3] if len(broker_row) > 3 else ''
                commission_model = broker_row[4] if len(broker_row) > 4 else 'bounty'
            
            # Calculate commission amount
            commission = 500.00 if commission_model == 'bounty' else 50.00
            payout_type = 'bounty' if commission_model == 'bounty' else 'recurring'
            
            # Set dates (61 days ago to pass 60-day hold)
            now = datetime.now()
            activated_date = now - timedelta(days=61)
            hold_until = activated_date + timedelta(days=60)  # Already passed
            clawback_until = activated_date + timedelta(days=90)
            
            # Create test customer
            test_customer_email = f'test_customer_{broker_id}@example.com'
            test_customer_stripe_id = f'cus_test_{broker_id}'
            test_subscription_id = f'sub_test_{broker_id}'
            
            # Insert test customer
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO customers (email, stripe_customer_id, subscription_id, status, plan, amount)
                    VALUES (%s, %s, %s, 'active', 'unlimited', 299.00)
                    ON CONFLICT (email) DO UPDATE SET
                        stripe_customer_id = EXCLUDED.stripe_customer_id,
                        subscription_id = EXCLUDED.subscription_id,
                        status = 'active'
                """, (test_customer_email, test_customer_stripe_id, test_subscription_id))
            else:
                cursor.execute("""
                    INSERT INTO customers (email, stripe_customer_id, subscription_id, status, plan, amount)
                    VALUES (?, ?, ?, 'active', 'unlimited', 299.00)
                    ON CONFLICT(email) DO UPDATE SET
                        stripe_customer_id = excluded.stripe_customer_id,
                        subscription_id = excluded.subscription_id,
                        status = 'active'
                """, (test_customer_email, test_customer_stripe_id, test_subscription_id))
            
            # Create test referral with ready_to_pay status
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO referrals (
                        broker_id, broker_email, customer_email, customer_stripe_id,
                        amount, payout, payout_type, status,
                        hold_until, clawback_until, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'ready_to_pay', %s, %s, %s)
                """, (
                    referral_code, broker_email, test_customer_email, test_customer_stripe_id,
                    commission, commission, payout_type,
                    hold_until.date(), clawback_until.date(), activated_date
                ))
            else:
                cursor.execute("""
                    INSERT INTO referrals (
                        broker_id, broker_email, customer_email, customer_stripe_id,
                        amount, payout, payout_type, status,
                        hold_until, clawback_until, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'ready_to_pay', ?, ?, ?)
                """, (
                    referral_code, broker_email, test_customer_email, test_customer_stripe_id,
                    commission, commission, payout_type,
                    hold_until.date(), clawback_until.date(), activated_date
                ))
            
            conn.commit()
            
            return JSONResponse(
                status_code=200,
                content={
                    'success': True,
                    'message': f'TEST DATA CREATED: Broker {broker_name} now ready for payment',
                    'broker_id': broker_id,
                    'broker_name': broker_name,
                    'commission_owed': commission,
                    'commission_model': commission_model,
                    'test_customer_email': test_customer_email,
                    'hold_until': hold_until.date().isoformat(),
                    'status': 'ready_to_pay'
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error creating test broker ready data: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create test data: {str(e)}")

@app.get("/api/admin/brokers-ready-to-pay")
async def get_brokers_ready_to_pay(username: str = Depends(verify_admin)):
    """Get list of brokers who are ready to be paid - Uses canonical payout ledger"""
    try:
        today = datetime.now()
        brokers_ready = []
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Use payout ledger if available
            if PAYOUT_LEDGER_AVAILABLE:
                try:
                    ledgers = compute_all_brokers_ledgers(cursor, DB_TYPE)
                    
                    for ledger in ledgers:
                        # Only include brokers with amount due now > 0
                        if ledger.total_due_now > 0:
                            # Get broker payment info
                            if DB_TYPE == 'postgresql':
                                cursor.execute("""
                                    SELECT payment_method, payment_email, iban, crypto_wallet
                                    FROM brokers WHERE id = %s
                                """, (ledger.broker_id,))
                            else:
                                cursor.execute("""
                                    SELECT payment_method, payment_email, iban, crypto_wallet
                                    FROM brokers WHERE id = ?
                                """, (ledger.broker_id,))
                            
                            payment_info = cursor.fetchone()
                            payment_method = ''
                            payment_email = ''
                            iban = ''
                            crypto_wallet = ''
                            
                            if payment_info:
                                if isinstance(payment_info, dict):
                                    payment_method = payment_info.get('payment_method', '')
                                    payment_email = payment_info.get('payment_email', '')
                                    iban = payment_info.get('iban', '')
                                    crypto_wallet = payment_info.get('crypto_wallet', '')
                                else:
                                    payment_method = payment_info[0] if len(payment_info) > 0 else ''
                                    payment_email = payment_info[1] if len(payment_info) > 1 else ''
                                    iban = payment_info[2] if len(payment_info) > 2 else ''
                                    crypto_wallet = payment_info[3] if len(payment_info) > 3 else ''
                            
                            # Get payment address
                            payment_address = ''
                            if payment_method in ['paypal', 'wise', 'revolut']:
                                payment_address = payment_email or ''
                            elif payment_method in ['sepa', 'swift']:
                                payment_address = iban or ''
                            elif payment_method == 'crypto':
                                payment_address = crypto_wallet or ''
                            
                            # Calculate days overdue
                            days_overdue = 0
                            if ledger.next_payout_date:
                                days_overdue = max(0, (today - ledger.next_payout_date).days)
                            
                            brokers_ready.append({
                                'id': ledger.broker_id,
                                'name': ledger.broker_name,
                                'email': ledger.broker_email,
                                'commission_owed': float(ledger.total_due_now),
                                'commission_model': ledger.commission_model,
                                'payment_method': payment_method or 'Not Set',
                                'payment_address': payment_address or 'N/A',
                                'next_payment_due': ledger.next_payout_date.isoformat() if ledger.next_payout_date else None,
                                'days_overdue': days_overdue,
                                'is_first_payment': ledger.total_paid == 0,
                                'total_earned': float(ledger.total_earned),
                                'total_paid': float(ledger.total_paid),
                                'total_on_hold': float(ledger.total_on_hold),
                                'payment_setup_complete': bool(payment_method),
                                'needs_setup': ledger.total_due_now > 0 and not payment_method
                            })
                    
                    # Sort by needs_setup first, then days_overdue, then commission_owed
                    brokers_ready.sort(key=lambda x: (
                        not x.get('needs_setup', False),  # needs_setup first
                        -x.get('days_overdue', 0),  # most overdue first
                        -x.get('commission_owed', 0)  # highest commission first
                    ))
                    
                    # Calculate summary statistics
                    total_commission_owed = sum(b['commission_owed'] for b in brokers_ready)
                    brokers_needing_setup = sum(1 for b in brokers_ready if b.get('needs_setup', False))
                    brokers_overdue = sum(1 for b in brokers_ready if b.get('days_overdue', 0) > 0)
                    
                    return JSONResponse(
                        status_code=200,
                        content={
                            "brokers": brokers_ready,
                            "summary": {
                                "total_commission_owed": total_commission_owed,
                                "brokers_needing_setup": brokers_needing_setup,
                                "brokers_overdue": brokers_overdue,
                                "brokers_ready_to_pay": len(brokers_ready)
                            }
                        }
                    )
                except Exception as ledger_error:
                    print(f"⚠️ Ledger computation error, falling back to legacy method: {ledger_error}")
                    import traceback
                    traceback.print_exc()
                    # Fall through to legacy method
            
            # Legacy method (fallback if ledger not available or fails)
            today = datetime.now()
            brokers_ready = []
            
            with get_db() as conn:
                cursor = get_db_cursor(conn)
            
            # Check what columns actually exist in brokers table
            has_payment_columns = False
            has_created_at = False
            has_approved_at = False
            
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'brokers'
                    """)
                    columns = cursor.fetchall()
                    column_names = [col[0] if isinstance(col, (list, tuple)) else col.get('column_name', '') for col in columns]
                    has_payment_columns = 'first_payment_date' in column_names
                    has_created_at = 'created_at' in column_names
                    has_approved_at = 'approved_at' in column_names
                else:
                    cursor.execute("PRAGMA table_info(brokers)")
                    columns = cursor.fetchall()
                    column_names = []
                    for col in columns:
                        if isinstance(col, (list, tuple)):
                            column_names.append(col[1] if len(col) > 1 else '')
                        elif isinstance(col, dict):
                            column_names.append(col.get('name', ''))
                    has_payment_columns = 'first_payment_date' in column_names
                    has_created_at = 'created_at' in column_names
                    has_approved_at = 'approved_at' in column_names
            except Exception as col_check_error:
                print(f"⚠️ Could not check for columns: {col_check_error}")
                has_payment_columns = False
                has_created_at = False
                has_approved_at = True  # Default to approved_at which should exist
            
            # Determine date column to use (created_at, approved_at, or fallback)
            date_column = 'approved_at'  # Default
            if has_created_at:
                date_column = 'created_at'
            elif has_approved_at:
                date_column = 'approved_at'
            else:
                date_column = 'NULL'  # Fallback if neither exists
            
            # Build SELECT query based on available columns
            if has_payment_columns:
                select_cols = f"""
                    id, name, email, payment_method, payment_email, iban, crypto_wallet,
                    first_payment_date, last_payment_date, next_payment_due, 
                    {date_column} as created_at, status, commission_model
                """
            else:
                # Fallback: use approved_at/created_at instead of payment tracking columns
                print(f"⚠️ Payment tracking columns not found, using {date_column} as fallback")
                select_cols = f"""
                    id, name, email, payment_method, payment_email, iban, crypto_wallet,
                    NULL as first_payment_date, NULL as last_payment_date, NULL as next_payment_due,
                    {date_column} as created_at, status, commission_model
                """
            
            # Get all active/approved brokers
            # Use the date_column we determined above for ordering
            order_by_col = date_column if date_column != 'NULL' else 'id'
            
            if DB_TYPE == 'postgresql':
                cursor.execute(f"""
                    SELECT {select_cols}
                    FROM brokers
                    WHERE status IN ('approved', 'active')
                    ORDER BY {order_by_col} ASC
                """)
            else:
                cursor.execute(f"""
                    SELECT {select_cols}
                    FROM brokers
                    WHERE status IN ('approved', 'active') OR status IS NULL
                    ORDER BY {order_by_col} ASC
                """)
            
            brokers = cursor.fetchall()
            
            for broker in brokers:
                # Parse broker data
                if isinstance(broker, dict):
                    broker_id = broker.get('id')
                    broker_name = broker.get('name', 'Unknown')
                    broker_email = broker.get('email', '')
                    payment_method = broker.get('payment_method', '')
                    payment_email = broker.get('payment_email', '')
                    iban = broker.get('iban', '')
                    crypto_wallet = broker.get('crypto_wallet', '')
                    first_payment_date = broker.get('first_payment_date')
                    last_payment_date = broker.get('last_payment_date')
                    next_payment_due = broker.get('next_payment_due')
                    created_at = broker.get('created_at')
                    broker_status = broker.get('status')
                    commission_model = broker.get('commission_model')
                else:
                    broker_id = broker[0] if len(broker) > 0 else None
                    broker_name = broker[1] if len(broker) > 1 else 'Unknown'
                    broker_email = broker[2] if len(broker) > 2 else ''
                    payment_method = broker[3] if len(broker) > 3 else ''
                    payment_email = broker[4] if len(broker) > 4 else ''
                    iban = broker[5] if len(broker) > 5 else ''
                    crypto_wallet = broker[6] if len(broker) > 6 else ''
                    first_payment_date = broker[7] if len(broker) > 7 else None
                    last_payment_date = broker[8] if len(broker) > 8 else None
                    next_payment_due = broker[9] if len(broker) > 9 else None
                    created_at = broker[10] if len(broker) > 10 else None
                    broker_status = broker[11] if len(broker) > 11 else None
                    commission_model = broker[12] if len(broker) > 12 else None
                
                # Calculate next payment due date
                if first_payment_date is None:
                    # First payment: 60 days after activation/approval
                    if created_at:
                        if isinstance(created_at, str):
                            try:
                                activation_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            except:
                                activation_date = datetime.now()
                        else:
                            activation_date = created_at
                    else:
                        activation_date = datetime.now()
                    
                    next_due = activation_date + timedelta(days=60)
                    is_first_payment = True
                else:
                    # Subsequent payments: 30 days after last payment
                    if isinstance(last_payment_date, str):
                        try:
                            last_payment = datetime.fromisoformat(last_payment_date.replace('Z', '+00:00'))
                        except:
                            last_payment = datetime.now()
                    else:
                        last_payment = last_payment_date or datetime.now()
                    
                    next_due = last_payment + timedelta(days=30)
                    is_first_payment = False
                
                # Use stored next_payment_due if available and valid
                if next_payment_due:
                    try:
                        if isinstance(next_payment_due, str):
                            stored_due = datetime.fromisoformat(next_payment_due.replace('Z', '+00:00'))
                        else:
                            stored_due = next_payment_due
                        if stored_due <= today:
                            next_due = stored_due
                    except:
                        pass
                
                # Check if payment is due
                if next_due <= today:
                    # Calculate commission owed from referrals
                    commission_owed = 0.0
                    
                    # Check if referrals table exists
                    referrals_exists = False
                    try:
                        if DB_TYPE == 'postgresql':
                            cursor.execute("""
                                SELECT EXISTS (
                                    SELECT FROM information_schema.tables 
                                    WHERE table_name = 'referrals'
                                )
                            """)
                            result = cursor.fetchone()
                            referrals_exists = result[0] if result else False
                        else:
                            cursor.execute("""
                                SELECT name FROM sqlite_master 
                                WHERE type='table' AND name='referrals'
                            """)
                            referrals_exists = cursor.fetchone() is not None
                    except Exception as table_check_error:
                        print(f"⚠️ Could not check for referrals table: {table_check_error}")
                        referrals_exists = False
                    
                    if referrals_exists:
                        # Get referrals that are ready to pay
                        # Try broker_id first, then fallback to referral_code
                        try:
                            # First, get the broker's referral_code if we need it
                            broker_referral_code = None
                            if DB_TYPE == 'postgresql':
                                cursor.execute("""
                                    SELECT referral_code FROM brokers WHERE id = %s
                                """, (broker_id,))
                            else:
                                cursor.execute("""
                                    SELECT referral_code FROM brokers WHERE id = ?
                                """, (broker_id,))
                            broker_ref_result = cursor.fetchone()
                            if broker_ref_result:
                                if isinstance(broker_ref_result, dict):
                                    broker_referral_code = broker_ref_result.get('referral_code')
                                else:
                                    broker_referral_code = broker_ref_result[0] if len(broker_ref_result) > 0 else None
                            
                            # Try querying by broker_id first
                            if DB_TYPE == 'postgresql':
                                cursor.execute("""
                                    SELECT COALESCE(SUM(payout), 0) as total_commission
                                    FROM referrals
                                    WHERE broker_id = %s 
                                    AND (status IN ('ready_to_pay', 'on_hold', 'active') OR status IS NULL)
                                    AND (hold_until IS NULL OR hold_until <= NOW())
                                """, (broker_id,))
                            else:
                                cursor.execute("""
                                    SELECT COALESCE(SUM(payout), 0) as total_commission
                                    FROM referrals
                                    WHERE broker_id = ? 
                                    AND (status IN ('ready_to_pay', 'on_hold', 'active') OR status IS NULL)
                                    AND (hold_until IS NULL OR hold_until <= date('now'))
                                """, (broker_id,))
                            
                            commission_result = cursor.fetchone()
                            
                            # If no results with broker_id, try referral_code
                            if not commission_result or (isinstance(commission_result, dict) and commission_result.get('total_commission', 0) == 0) or (not isinstance(commission_result, dict) and len(commission_result) > 0 and commission_result[0] == 0):
                                if broker_referral_code:
                                    if DB_TYPE == 'postgresql':
                                        cursor.execute("""
                                            SELECT COALESCE(SUM(payout), 0) as total_commission
                                            FROM referrals
                                            WHERE broker_code = %s 
                                            AND (status IN ('ready_to_pay', 'on_hold', 'active') OR status IS NULL)
                                            AND (hold_until IS NULL OR hold_until <= NOW())
                                        """, (broker_referral_code,))
                                    else:
                                        cursor.execute("""
                                            SELECT COALESCE(SUM(payout), 0) as total_commission
                                            FROM referrals
                                            WHERE broker_code = ? 
                                            AND (status IN ('ready_to_pay', 'on_hold', 'active') OR status IS NULL)
                                            AND (hold_until IS NULL OR hold_until <= date('now'))
                                        """, (broker_referral_code,))
                                    commission_result = cursor.fetchone()
                            
                            if commission_result:
                                if isinstance(commission_result, dict):
                                    commission_owed = float(commission_result.get('total_commission') or 0)
                                else:
                                    commission_owed = float(commission_result[0] if len(commission_result) > 0 and commission_result[0] else 0)
                            
                            print(f"✅ Broker {broker_id} ({broker_name}): commission_owed = ${commission_owed:.2f}")
                        except Exception as commission_error:
                            print(f"⚠️ Error calculating commission for broker {broker_id} ({broker_name}): {commission_error}")
                            import traceback
                            traceback.print_exc()
                            commission_owed = 0.0
                    else:
                        print(f"⚠️ Referrals table does not exist, skipping commission calculation")
                        commission_owed = 0.0
                    
                    # Include broker if commission > 0 OR payment is overdue (even with $0 commission)
                    # This helps identify brokers who need payment setup
                    if commission_owed > 0 or next_due < today:
                        # Get payment address based on payment method
                        payment_address = ''
                        payment_method_display = payment_method or 'Not Set'
                        
                        if payment_method in ['paypal', 'wise', 'revolut']:
                            payment_address = payment_email or ''
                            if not payment_address:
                                payment_method_display = f"{payment_method} (Email Missing)"
                        elif payment_method == 'sepa':
                            payment_address = iban or ''
                            if not payment_address:
                                payment_method_display = "SEPA (IBAN Missing)"
                        elif payment_method == 'swift':
                            payment_address = iban or ''
                            if not payment_address:
                                payment_method_display = "SWIFT (Account Missing)"
                        elif payment_method == 'crypto':
                            payment_address = crypto_wallet or ''
                            if not payment_address:
                                payment_method_display = "Crypto (Wallet Missing)"
                        
                        # Calculate days overdue
                        days_overdue = (today - next_due).days if next_due < today else 0
                        
                        # Determine payment setup status
                        payment_setup_complete = bool(
                            payment_method and (
                                (payment_method in ['paypal', 'wise', 'revolut'] and payment_email) or
                                (payment_method in ['sepa', 'swift'] and iban) or
                                (payment_method == 'crypto' and crypto_wallet)
                            )
                        )
                        
                        brokers_ready.append({
                            'id': broker_id,
                            'name': broker_name,
                            'email': broker_email,
                            'commission_owed': round(commission_owed, 2),
                            'payment_method': payment_method_display,
                            'payment_address': payment_address,
                            'payment_setup_complete': payment_setup_complete,
                            'next_payment_due': next_due.isoformat(),
                            'days_overdue': days_overdue,
                            'is_first_payment': is_first_payment,
                            'needs_setup': not payment_setup_complete and commission_owed > 0
                        })
        
        # Sort by: needs_setup first, then days overdue (most overdue first), then by commission amount
        brokers_ready.sort(key=lambda x: (
            not x.get('needs_setup', False),  # needs_setup=True comes first
            -x['days_overdue'],  # Most overdue first
            -x['commission_owed']  # Highest commission first
        ))
        
        # Add summary statistics
        total_commission = sum(b['commission_owed'] for b in brokers_ready)
        brokers_needing_setup = sum(1 for b in brokers_ready if b.get('needs_setup', False))
        brokers_overdue = sum(1 for b in brokers_ready if b['days_overdue'] > 0)
        
        return {
            "status": "success",
            "brokers": brokers_ready,
            "count": len(brokers_ready),
            "summary": {
                "total_commission_owed": round(total_commission, 2),
                "brokers_needing_setup": brokers_needing_setup,
                "brokers_overdue": brokers_overdue,
                "brokers_ready_to_pay": len([b for b in brokers_ready if b['commission_owed'] > 0 and b.get('payment_setup_complete', False)])
            }
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Get brokers ready to pay error: {error_msg}")
        import traceback
        traceback_str = traceback.format_exc()
        print(f"❌ Traceback:\n{traceback_str}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to get brokers ready to pay: {error_msg}",
                "traceback": traceback_str
            }
        )

def send_broker_password_reset_email(email: str, name: str, reset_link: str):
    """Send password reset email to broker"""
    try:
        from api.admin import send_email_sync
        
        subject = "Reset Your LienDeadline Partner Password"
        
        body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f9fafb;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                    <tr>
                        <td style="padding: 40px 40px 30px; text-align: center; border-bottom: 1px solid #e5e7eb;">
                            <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #1f2937;">
                                📋 LienDeadline
                            </h1>
                            <p style="margin: 12px 0 0; font-size: 16px; color: #6b7280;">
                                Partner Program
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 40px 20px;">
                            <h2 style="margin: 0 0 16px; font-size: 24px; font-weight: 600; color: #1f2937;">
                                Password Reset Request
                            </h2>
                            <p style="margin: 0 0 24px; font-size: 16px; color: #4b5563; line-height: 1.6;">
                                Hi {name},
                            </p>
                            <p style="margin: 0 0 24px; font-size: 16px; color: #4b5563; line-height: 1.6;">
                                You requested a password reset for your LienDeadline Partner account. Click the button below to reset your password:
                            </p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{reset_link}" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; padding: 14px 32px; border-radius: 6px;">
                                    Reset Password
                                </a>
                            </div>
                            <p style="margin: 24px 0 0; font-size: 14px; color: #6b7280;">
                                This link will expire in 24 hours. If you didn't request this, please ignore this email.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 32px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                                © 2025 LienDeadline. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
        
        send_email_sync(email, subject, body_html)
        print(f"✅ Password reset email sent to broker: {email}")
        
    except Exception as e:
        print(f"❌ Password reset email error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
