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
import subprocess
import sys
import bcrypt
# Stripe is required for payment processing - not optional
import stripe
import traceback
# REMOVED: from api.migrations.fix_production_schema import fix_postgres_schema

import httpx
from urllib.parse import urlencode
import base64
try:
    from psycopg2 import IntegrityError
except ImportError:
    # Fallback for non-postgres environments if needed, though get_db handles this
    from sqlite3 import IntegrityError

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .rate_limiter import limiter
from api.services.email import (
    send_email_sync,
    send_password_reset_email
)
from api.cron_send_reminders import send_daily_reminders

from io import BytesIO
from .calculators import (
    calculate_texas, calculate_washington, calculate_california,
    calculate_ohio, calculate_oregon, calculate_hawaii, calculate_newjersey, calculate_indiana, calculate_louisiana, calculate_massachusetts, calculate_default
)

# Unified calculation helper function - used by both PDF generation and calculate_deadline endpoint
def calculate_state_deadline(
    state_code: str,
    invoice_date: datetime,
    role: str = "supplier",
    project_type: str = "commercial",
    notice_of_completion_date: Optional[datetime] = None,
    notice_of_commencement_filed: bool = False,
    state_rules: Optional[dict] = None
):
    """
    Unified state deadline calculation function.
    Uses the same logic for all endpoints to ensure consistency.
    
    Args:
        state_code: Two-letter state code (e.g., "TX", "CA")
        invoice_date: datetime object for invoice/delivery date
        role: "supplier", "contractor", etc.
        project_type: "commercial" or "residential"
        notice_of_completion_date: Optional datetime for notice of completion
        notice_of_commencement_filed: Whether notice of commencement was filed
        state_rules: Optional dict with state rules (for default calculation)
    
    Returns:
        dict with calculation results (preliminary_deadline, lien_deadline, etc.)
    """
    state_code = state_code.upper()
    
    # State-specific calculation logic (single source of truth)
    if state_code == "TX":
        return calculate_texas(invoice_date, project_type=project_type)
    elif state_code == "WA":
        return calculate_washington(invoice_date, role=role)
    elif state_code == "CA":
        return calculate_california(
            invoice_date,
            notice_of_completion_date=notice_of_completion_date,
            role=role
        )
    elif state_code == "OH":
        return calculate_ohio(
            invoice_date,
            project_type=project_type,
            notice_of_commencement_filed=notice_of_commencement_filed
        )
    elif state_code == "OR":
        return calculate_oregon(invoice_date)
    elif state_code == "HI":
        return calculate_hawaii(invoice_date)
    else:
        # Default calculation for simple states
        if not state_rules:
            # Fallback to basic defaults if no rules provided
            prelim_required = False
            prelim_days = 20
            lien_days = 120
            special_rules = {}
        else:
            prelim_notice = state_rules.get('preliminary_notice', {})
            lien_filing = state_rules.get('lien_filing', {})
            special_rules = state_rules.get('special_rules', {})
            
            prelim_required = prelim_notice.get('required', False)
            prelim_days = prelim_notice.get('days') or prelim_notice.get('commercial_days') or 20
            lien_days = lien_filing.get('days') or lien_filing.get('commercial_days') or 120
        
        return calculate_default(
            invoice_date,
            {
                "preliminary_notice_required": prelim_required,
                "preliminary_notice_days": prelim_days,
                "lien_filing_days": lien_days,
                "notes": special_rules.get("notes", "")
            },
            weekend_extension=special_rules.get("weekend_extension", False),
            holiday_extension=special_rules.get("holiday_extension", False)
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
from .database import get_db, get_db_cursor, DB_TYPE, execute_query, BASE_DIR

# Define project root (parent of api/ directory)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# THEN import routers (after database is defined)
from .analytics import router as analytics_router
from .routers.admin import router as admin_router, verify_admin
from .quickbooks import router as quickbooks_router
from .routers.calculations import router as calculations_router
from .routers.auth import get_current_user
from .routers import auth
from .routers import webhooks
from .routers import brokers
from .routers import customer
from .routers import zapier

# Import short link generator
from .short_link_system import ShortLinkGenerator

# Import payout ledger service
try:
    from .services.payout_ledger import (
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
from .email_abuse import (
    is_disposable_email,
    generate_verification_token,
    hash_email,
    check_duplicate_email,
    validate_email_format
)

app = FastAPI(title="Lien Deadline API")

# State code to full name mapping
STATE_CODE_TO_NAME = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'DC': 'District of Columbia', 'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii',
    'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine',
    'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota',
    'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska',
    'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
    'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island',
    'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas',
    'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

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
                    
                    # REMOVED: Old sample INSERT statements - now using proper migration
            
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
                    
                    # REMOVED: Old sample INSERT statements - now using proper migration
            
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
            
            # Create api_key_requests table if it doesn't exist
            if 'api_key_requests' not in existing_tables:
                print("Creating api_key_requests table...")

                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        CREATE TABLE api_key_requests (
                            id SERIAL PRIMARY KEY,
                            company VARCHAR NOT NULL,
                            email VARCHAR NOT NULL,
                            phone VARCHAR,
                            volume VARCHAR NOT NULL,
                            use_case TEXT,
                            status VARCHAR DEFAULT 'pending',
                            ip_address VARCHAR,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_req_email ON api_key_requests(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_req_status ON api_key_requests(status)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_req_created ON api_key_requests(created_at)")
                    print("✅ Created api_key_requests table")
                else:
                    cursor.execute("""
                        CREATE TABLE api_key_requests (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            company TEXT NOT NULL,
                            email TEXT NOT NULL,
                            phone TEXT,
                            volume TEXT NOT NULL,
                            use_case TEXT,
                            status TEXT DEFAULT 'pending',
                            ip_address TEXT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_req_email ON api_key_requests(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_req_status ON api_key_requests(status)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_req_created ON api_key_requests(created_at)")
                    print("✅ Created api_key_requests table")
            
            # Create customers table if it doesn't exist
            if 'customers' not in existing_tables:
                print("Creating customers table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        CREATE TABLE customers (
                            id SERIAL PRIMARY KEY,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            stripe_customer_id VARCHAR(255),
                            subscription_id VARCHAR(255),
                            status VARCHAR(50) DEFAULT 'active',
                            plan VARCHAR(50) DEFAULT 'unlimited',
                            amount REAL DEFAULT 299.00,
                            calls_used INTEGER DEFAULT 0,
                            api_key VARCHAR(255) UNIQUE,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_stripe ON customers(stripe_customer_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)")
                    print("✅ Created customers table")
                else:
                    cursor.execute("""
                        CREATE TABLE customers (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            email TEXT UNIQUE NOT NULL,
                            stripe_customer_id TEXT,
                            subscription_id TEXT,
                            status TEXT DEFAULT 'active',
                            plan TEXT DEFAULT 'unlimited',
                            amount REAL DEFAULT 299.00,
                            calls_used INTEGER DEFAULT 0,
                            api_key TEXT UNIQUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_stripe ON customers(stripe_customer_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)")
                    print("✅ Created customers table")
            else:
                # Customers table exists, check if api_key column exists
                try:
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name='customers' AND column_name='api_key'
                        """)
                        if not cursor.fetchone():
                            cursor.execute("ALTER TABLE customers ADD COLUMN api_key VARCHAR(255) UNIQUE")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)")
                            print("✅ Added api_key column to customers table")
                    else:
                        cursor.execute("PRAGMA table_info(customers)")
                        columns = [row[1] for row in cursor.fetchall()]
                        if 'api_key' not in columns:
                            cursor.execute("ALTER TABLE customers ADD COLUMN api_key TEXT UNIQUE")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)")
                            print("✅ Added api_key column to customers table")
                except Exception as e:
                    print(f"⚠️ Could not add api_key column (may already exist): {e}")
            
            # Create api_keys table if it doesn't exist
            if 'api_keys' not in existing_tables:
                print("Creating api_keys table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        CREATE TABLE api_keys (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER,
                            customer_email VARCHAR NOT NULL,
                            api_key VARCHAR UNIQUE NOT NULL,
                            created_at TIMESTAMP DEFAULT NOW(),
                            last_used_at TIMESTAMP,
                            is_active BOOLEAN DEFAULT TRUE,
                            calls_count INTEGER DEFAULT 0,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(api_key)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_email ON api_keys(customer_email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
                    print("✅ Created api_keys table")
                else:
                    cursor.execute("""
                        CREATE TABLE api_keys (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            customer_email TEXT NOT NULL,
                            api_key TEXT UNIQUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_used_at TIMESTAMP,
                            is_active INTEGER DEFAULT 1,
                            calls_count INTEGER DEFAULT 0,
                            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(api_key)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_email ON api_keys(customer_email)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
                    print("✅ Created api_keys table")
            
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
            
            # Create QuickBooks tokens table
            if 'quickbooks_tokens' not in existing_tables:
                print("Creating quickbooks_tokens table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        CREATE TABLE quickbooks_tokens (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            realm_id VARCHAR(255) NOT NULL,
                            access_token TEXT NOT NULL,
                            refresh_token TEXT NOT NULL,
                            expires_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT NOW(),
                            updated_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_tokens_user_id ON quickbooks_tokens(user_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_tokens_realm_id ON quickbooks_tokens(realm_id)")
                else:
                    cursor.execute("""
                        CREATE TABLE quickbooks_tokens (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            realm_id TEXT NOT NULL,
                            access_token TEXT NOT NULL,
                            refresh_token TEXT NOT NULL,
                            expires_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_tokens_user_id ON quickbooks_tokens(user_id)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_tokens_realm_id ON quickbooks_tokens(realm_id)")
                conn.commit()
                print("✅ quickbooks_tokens table created")
            
            # Create QuickBooks OAuth states table
            if 'quickbooks_oauth_states' not in existing_tables:
                print("Creating quickbooks_oauth_states table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        CREATE TABLE quickbooks_oauth_states (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            state VARCHAR(255) UNIQUE NOT NULL,
                            expires_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_states_state ON quickbooks_oauth_states(state)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_states_user_id ON quickbooks_oauth_states(user_id)")
                else:
                    cursor.execute("""
                        CREATE TABLE quickbooks_oauth_states (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL,
                            state TEXT UNIQUE NOT NULL,
                            expires_at TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_states_state ON quickbooks_oauth_states(state)")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_qb_states_user_id ON quickbooks_oauth_states(user_id)")
                conn.commit()
                print("✅ quickbooks_oauth_states table created")
            
            # Commit is handled automatically by context manager
            print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        import traceback
        traceback.print_exc()
        # Rollback transaction on error to prevent "transaction aborted" errors
        try:
            with get_db() as conn:
                conn.rollback()
        except:
            pass

# Initialize Stripe - Set API key from environment variable
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY') or os.getenv('STRIPE_KEY') or ''
stripe.api_key = STRIPE_SECRET_KEY

if not STRIPE_SECRET_KEY:
    print("⚠️ Warning: STRIPE_SECRET_KEY not found in environment variables")
    print("   Stripe checkout sessions will fail without a valid API key")
else:
    print(f"✅ Stripe API key initialized (length: {len(STRIPE_SECRET_KEY)} chars)")

STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

@app.get("/api/force-db-fix")
async def force_db_fix():
    """Temporary endpoint to force database schema migration manually."""
    try:
        print("🔧 Manual trigger: Running schema fix...")
        await fix_postgres_schema()
        return {"status": "success", "message": "Schema fix executed. Check logs for details."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/clear-oauth-states")
async def clear_oauth_states():
    """TEMPORARY: Clear all OAuth states to fix stale state issue"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM quickbooks_oauth_states")
            else:
                cursor.execute("DELETE FROM quickbooks_oauth_states")
            conn.commit()
            return {"success": True, "message": "All OAuth states cleared"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# Explicit Static Page Routes (Must be defined before static mounts and catch-all routes)
@app.get("/pricing")
async def serve_pricing():
    file_path = BASE_DIR / "pricing.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="pricing.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/pricing.html")
async def serve_pricing_html():
    file_path = BASE_DIR / "pricing.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="pricing.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/state-lien-guides")
async def serve_state_lien_guides():
    file_path = BASE_DIR / "state-lien-guides.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="state-lien-guides.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/state-lien-guides.html")
async def serve_state_lien_guides_html():
    file_path = BASE_DIR / "state-lien-guides.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="state-lien-guides.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/partners")
async def serve_partners():
    file_path = BASE_DIR / "partners.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="partners.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/partners.html")
async def serve_partners_html():
    file_path = BASE_DIR / "partners.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="partners.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/contact")
async def serve_contact():
    file_path = BASE_DIR / "contact.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="contact.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/contact.html")
async def serve_contact_html():
    file_path = BASE_DIR / "contact.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="contact.html not found")
    return FileResponse(file_path, media_type="text/html")

# Include routers with full paths to match frontend calls
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(admin_router, tags=["admin"])
app.include_router(quickbooks_router, prefix="/api/quickbooks", tags=["quickbooks"])
app.include_router(calculations_router, tags=["calculations"])
app.include_router(auth.router, tags=["auth"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(brokers.router, tags=["brokers"])
app.include_router(customer.router, tags=["customer"])
app.include_router(zapier.router, prefix="/api/zapier", tags=["zapier"])





# Initialize database on startup
@app.on_event("startup")
async def startup():
    """Initialize the application on startup."""
    print("🚀 Starting application...")
    
    # REMOVED: Run reminder columns migration
    # try:
    #     from api.migrations.add_reminder_columns import add_reminder_columns
    #     print("🔄 Running reminder columns migration...")
    #     success = add_reminder_columns()
    #     if success:
    #         print("✅ Reminder columns migration completed successfully")
    #     else:
    #         print("⚠️ Reminder columns migration had issues (check logs above)")
    # except Exception as e:
    #     print(f"⚠️ Could not run reminder columns migration: {e}")
    #     import traceback
    #     traceback.print_exc()
    #     # Don't fail startup if migration fails - columns might already exist

    # REMOVED: Run project_type column migration
    # try:
    #     from api.migrations.add_project_type_column import run_migration
    #     print("🔄 Running project_type column migration...")
    #     run_migration()
    #     print("✅ Project type column migration completed")
    # except Exception as e:
    #     print(f"⚠️ Could not run project_type column migration: {e}")
    #     import traceback
    #     traceback.print_exc()
    #     # Don't fail startup if migration fails - column might already exist

    # Run schema check (temporary for debugging production)
    # REMOVED: Auto-running migration code to prevent startup failures
    # try:
    #     print("🔍 Running production schema check...")
    #     # Use python from current environment
    #     # REMOVED: result = subprocess.run([sys.executable, 'api/migrations/check_production_schema.py'], 
    #     #                       capture_output=True, text=True)
    #     # Print output to logs so it shows up in Railway logs
    #     # print(f"Schema check output:\n{result.stdout}")
    #     # if result.stderr:
    #     #     print(f"Schema check errors:\n{result.stderr}")
    #     #     
    #     # Run schema fix migration (AFTER check)
    #     # print("🔧 Running production schema fix migration...")
    #     # REMOVED: fix_result = subprocess.run([sys.executable, 'api/migrations/fix_production_schema.py'], 
    #     #                       capture_output=True, text=True, timeout=60)
    #     # 
    #     # print(f"Schema fix output:\n{fix_result.stdout}")
    #     # if fix_result.stderr:
    #     #     print(f"Schema fix errors:\n{fix_result.stderr}")
    #     # 
    #     # if fix_result.returncode == 0:
    #     #     print("✅ Schema fix migration completed")
    #     # else:
    #     #     print(f"❌ Schema fix migration failed with code {fix_result.returncode}")
    #     #     
    # except Exception as e:
    #     print(f"❌ Schema check/fix failed: {e}")
    
    print("✅ Application startup complete")



# Serve static files (CSS, JS)
try:
    static_dir = BASE_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Serve React Dashboard Assets
    dashboard_assets = BASE_DIR / "dashboard" / "assets"
    if dashboard_assets.exists():
        app.mount("/dashboard/assets", StaticFiles(directory=str(dashboard_assets)), name="dashboard-assets")

    # Serve Broker Dashboard v2 Assets
    broker_dashboard_v2_assets = BASE_DIR / "broker-dashboard-v2" / "assets"
    if broker_dashboard_v2_assets.exists():
        app.mount("/broker-dashboard-v2/assets", StaticFiles(directory=str(broker_dashboard_v2_assets)), name="broker-dashboard-v2-assets")

except Exception as e:
    print(f"Warning: Could not mount static files: {e}")

# Serve React Dashboard SPA
@app.get("/dashboard")
async def serve_dashboard_root():
    """Serve React App Root"""
    file_path = BASE_DIR / "dashboard" / "index.html"
    if file_path.exists():
        return FileResponse(file_path)
    return Response("Dashboard not found", status_code=404)

@app.get("/dashboard/{full_path:path}")
async def serve_dashboard(full_path: str):
    """Serve React App Paths (SPA Routing)"""
    # Check if file exists (e.g. favicon.ico, manifest.json)
    file_path = BASE_DIR / "dashboard" / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Fallback to index.html for SPA routing
    index_path = BASE_DIR / "dashboard" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return Response("Dashboard not found", status_code=404)


# Serve Broker Dashboard v2 SPA
@app.get("/broker-dashboard-v2")
async def serve_broker_dashboard_v2_root():
    """Serve Broker React App Root"""
    file_path = BASE_DIR / "broker-dashboard-v2" / "index.html"
    if file_path.exists():
        return FileResponse(file_path)
    return Response("Broker Dashboard not found", status_code=404)

@app.get("/broker-dashboard-v2/{full_path:path}")
async def serve_broker_dashboard_v2(full_path: str):
    """Serve Broker React App Paths (SPA Routing)"""
    # Check if file exists (e.g. favicon.ico, manifest.json)
    file_path = BASE_DIR / "broker-dashboard-v2" / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    
    # Fallback to index.html for SPA routing
    index_path = BASE_DIR / "broker-dashboard-v2" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return Response("Broker Dashboard not found", status_code=404)

# Images mount will be moved to right before the / mount to ensure proper order
# Serve Images
images_dir = BASE_DIR / "images"
if images_dir.exists():
    app.mount("/images", StaticFiles(directory=str(images_dir)), name="images")

# Serve State Lien Guides (PDFs/Static Pages)
guides_dir = BASE_DIR / "state-lien-guides"
if guides_dir.exists():
    app.mount("/state-lien-guides", StaticFiles(directory=str(guides_dir)), name="guides")

# Redirect www to non-www
@app.middleware("http")
async def redirect_www(request: Request, call_next):
    host = request.headers.get("host", "")
    if host.startswith("www."):
        url = request.url.replace(netloc=host[4:])
        return RedirectResponse(url=str(url), status_code=301)
    return await call_next(request)

# HTTP Basic Auth for admin routes - MOVED TO admin.py
# security = HTTPBasic()
# verify_admin moved to admin.py


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

@app.get("/login")
async def serve_login():
    """Serve login.html page at root"""
    file_path = BASE_DIR / "login.html"
    if not file_path.exists():
        # Fallback to index if login doesn't exist? Or 404. 
        # User said ensure login.html is in root.
        raise HTTPException(status_code=404, detail="login.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/login.html")
async def serve_login_html():
    """Serve login.html page directly"""
    file_path = BASE_DIR / "login.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="login.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/register.html")
async def serve_register_html():
    """Serve register.html page directly"""
    # Try root directory first (for compatibility)
    file_path = BASE_DIR / "register.html"
    if not file_path.exists():
        # Fallback to public directory
        file_path = BASE_DIR / "public" / "register.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="register.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/test-api")
async def test_api():
    """Serve test-api.html API tester page"""
    file_path = BASE_DIR / "test-api.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="test-api.html not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/favicon.ico")
async def favicon():
    file_path = BASE_DIR / "favicon.ico"
    if file_path.exists():
        return FileResponse(file_path)
    return Response(status_code=404)

@app.get("/robots.txt")
async def robots():
    file_path = BASE_DIR / "robots.txt"
    if file_path.exists():
        return FileResponse(file_path)
    return Response(status_code=404)

@app.get("/site.webmanifest")
async def manifest():
    file_path = BASE_DIR / "site.webmanifest"
    if file_path.exists():
        return FileResponse(file_path)
    return Response(status_code=404)

@app.get("/api/state-rules")
async def get_state_rules():
    """Return the state rules JSON configuration"""
    if not STATE_RULES:
        # Try reloading from disk if global dict is empty
        try:
            with open(BASE_DIR / "state_rules.json", 'r') as f:
                return json.load(f)
        except Exception:
            raise HTTPException(status_code=404, detail="State rules not found")
    return STATE_RULES

@app.get("/health")
def health():
    return {"status": "ok", "message": "API is running"}

# Legacy referral route removed - Tolt handles referral tracking now
# Old route: /r/{short_code} - No longer needed


@app.get("/api/v1/guide/{state_code}/pdf")
async def generate_state_guide_pdf(state_code: str, request: Request):
    """Generate PDF guide for a specific state"""
    # Check if ReportLab is available
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation is temporarily unavailable. ReportLab library is not installed. Please contact support."
        )
    
    state_code = state_code.upper()
    
    # Query database for state data
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Try state code first
            state_upper = state_code.upper()
            if DB_TYPE == 'postgresql':
                cursor.execute(
                    "SELECT * FROM lien_deadlines WHERE UPPER(state_code) = %s LIMIT 1",
                    (state_upper,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM lien_deadlines WHERE UPPER(state_code) = ? LIMIT 1",
                    (state_upper,)
                )
            db_state = cursor.fetchone()
            
            # If not found by code, try by state name
            if not db_state and state_upper in STATE_CODE_TO_NAME:
                full_name = STATE_CODE_TO_NAME[state_upper]
                if DB_TYPE == 'postgresql':
                    cursor.execute(
                        "SELECT * FROM lien_deadlines WHERE UPPER(state_name) = %s LIMIT 1",
                        (full_name.upper(),)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM lien_deadlines WHERE UPPER(state_name) = ? LIMIT 1",
                        (full_name.upper(),)
                    )
                db_state = cursor.fetchone()
            
            if not db_state:
                # Get available states from database
                cursor.execute("SELECT state_code FROM lien_deadlines ORDER BY state_code")
                available_states = []
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        available_states.append(row.get('state_code'))
                    elif isinstance(row, (tuple, list)):
                        available_states.append(row[0] if len(row) > 0 else None)
                    else:
                        available_states.append(str(row))
                available_states = [s for s in available_states if s]
                
                raise HTTPException(
                    status_code=404,
                    detail=f"State '{state_code}' not found. Available states: {', '.join(available_states[:20])}" + (f" and {len(available_states) - 20} more" if len(available_states) > 20 else "")
                )
            
            # Convert database row to dict format
            if isinstance(db_state, dict):
                state_data = {
                    'state_code': db_state.get('state_code'),
                    'state_name': db_state.get('state_name'),
                    'preliminary_notice': {
                        'required': db_state.get('preliminary_notice_required', False),
                        'days': db_state.get('preliminary_notice_days'),
                        'formula': db_state.get('preliminary_notice_formula'),
                        'description': db_state.get('preliminary_notice_deadline_description'),
                        'statute': db_state.get('preliminary_notice_statute')
                    },
                    'lien_filing': {
                        'days': db_state.get('lien_filing_days'),
                        'formula': db_state.get('lien_filing_formula'),
                        'description': db_state.get('lien_filing_deadline_description'),
                        'statute': db_state.get('lien_filing_statute')
                    },
                    'special_rules': {
                        'weekend_extension': db_state.get('weekend_extension', False),
                        'holiday_extension': db_state.get('holiday_extension', False),
                        'residential_vs_commercial': db_state.get('residential_vs_commercial', False),
                        'notice_of_completion_trigger': db_state.get('notice_of_completion_trigger', False),
                        'notes': db_state.get('notes', '')
                    }
                }
            else:
                # Handle tuple/list result - need to map by column order
                # Assuming standard column order from CREATE TABLE
                state_data = {
                    'state_code': db_state[1] if len(db_state) > 1 else state_code,
                    'state_name': db_state[2] if len(db_state) > 2 else STATE_CODE_TO_NAME.get(state_upper, state_code.title()),
                    'preliminary_notice': {
                        'required': bool(db_state[3]) if len(db_state) > 3 else False,
                        'days': db_state[4] if len(db_state) > 4 else None,
                        'formula': db_state[5] if len(db_state) > 5 else None,
                        'description': db_state[6] if len(db_state) > 6 else None,
                        'statute': db_state[7] if len(db_state) > 7 else None
                    },
                    'lien_filing': {
                        'days': db_state[8] if len(db_state) > 8 else None,
                        'formula': db_state[9] if len(db_state) > 9 else None,
                        'description': db_state[10] if len(db_state) > 10 else None,
                        'statute': db_state[11] if len(db_state) > 11 else None
                    },
                    'special_rules': {
                        'weekend_extension': bool(db_state[12]) if len(db_state) > 12 else False,
                        'holiday_extension': bool(db_state[13]) if len(db_state) > 13 else False,
                        'residential_vs_commercial': bool(db_state[14]) if len(db_state) > 14 else False,
                        'notice_of_completion_trigger': bool(db_state[15]) if len(db_state) > 15 else False,
                        'notes': db_state[16] if len(db_state) > 16 else ''
                    }
                }
    except HTTPException:
        raise
    except Exception as e:
        # Fallback to STATE_RULES if database query fails
        print(f"⚠️ Database query failed for PDF generation: {e}")
        if state_code in STATE_RULES:
            state_data = STATE_RULES[state_code]
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Unable to retrieve state data. Error: {str(e)[:100]}"
            )
    
    # Get state name - priority order:
    # 1. state_name query parameter (from frontend)
    # 2. state_data from database
    # 3. Convert state code to full name
    state_name_param = request.query_params.get('state_name', '')
    
    if state_name_param:
        # Frontend sent the full state name
        state_name = state_name_param
    elif state_data:
        # Try state_name column first, then state column
        state_name = state_data.get('state_name') or state_data.get('state', '')
        
        # If it's a 2-letter code, convert to full name
        if state_name and len(state_name) == 2:
            state_name = STATE_CODE_TO_NAME.get(state_name.upper(), state_name)
    else:
        # Fallback: convert state code to full name
        state_upper = state_code.upper()
        state_name = STATE_CODE_TO_NAME.get(state_upper, state_code.title())
    
    # Final safety check - always convert codes to full names
    if state_name and len(state_name) == 2:
        state_name = STATE_CODE_TO_NAME.get(state_name.upper(), state_name)
    
    # Additional safety check - ensure we have a name
    if not state_name:
        state_name = STATE_CODE_TO_NAME.get(state_code.upper(), state_code.title())
    
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
    
    # ===== PROFESSIONAL HEADER SECTION =====
    # Company branding with enhanced styling
    header_text = f"<b>LienDeadline</b>"
    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=18,
        textColor=navy,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=6
    )
    story.append(Paragraph(header_text, header_style))
    
    subtitle_text = "Mechanics Lien Deadline Report"
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#6b7280'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    story.append(Paragraph(subtitle_text, subtitle_style))
    
    # Generation date
    gen_date = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')
    gen_text = Paragraph(f"<b>Generated:</b> {gen_date}", ParagraphStyle('GenDate', parent=styles['Normal'], fontSize=9, textColor=HexColor('#6b7280'), alignment=TA_CENTER))
    story.append(gen_text)
    story.append(Spacer(1, 0.3*inch))
    
    # Title
    title_text = f"{state_name} Mechanics Lien Guide<br/>for Material Suppliers"
    story.append(Paragraph(title_text, title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Deadline Summary Box
    prelim_notice = state_data.get('preliminary_notice', {})
    lien_filing = state_data.get('lien_filing', {})
    
    prelim_days = prelim_notice.get('days', prelim_notice.get('commercial_days', prelim_notice.get('standard_days', None)))
    lien_days = lien_filing.get('days', lien_filing.get('commercial_days', lien_filing.get('standard_days', 120)))
    prelim_required = prelim_notice.get('required', False)
    
    # Get invoice_date from query parameters (optional)
    invoice_date_str = request.query_params.get('invoice_date', '')
    has_invoice_date = bool(invoice_date_str)
    
    # Calculate actual deadline dates if invoice_date is provided
    prelim_deadline_str = None
    lien_deadline_str = None
    prelim_days_remaining = None
    lien_days_remaining = None
    invoice_dt_str = None
    
    if invoice_date_str:
        try:
            from .calculators import calculate_default, calculate_texas, calculate_washington, calculate_california, calculate_ohio, calculate_oregon, calculate_hawaii
            
            # Parse invoice date - handle both MM/DD/YYYY and YYYY-MM-DD formats
            try:
                invoice_dt = datetime.strptime(invoice_date_str, "%m/%d/%Y")
            except ValueError:
                try:
                    invoice_dt = datetime.strptime(invoice_date_str, "%Y-%m-%d")
                except ValueError:
                    invoice_dt = datetime.fromisoformat(invoice_date_str.replace('Z', '+00:00'))
            
            invoice_dt_str = invoice_dt.strftime('%B %d, %Y')
            
            # Use the SAME calculation logic as calculate_deadline endpoint
            # Extract hardcoded values into variables to match calculator pattern
            role = "supplier"  # PDF default (no user input)
            project_type = "commercial"  # PDF default (no user input)
            notice_of_completion_date = None  # PDF default (no user input)
            notice_of_commencement_filed = False  # PDF default (no user input)
            
            # Import calculation functions
            from .calculators import calculate_default, calculate_texas, calculate_washington, calculate_california, calculate_ohio, calculate_oregon, calculate_hawaii, calculate_newjersey, calculate_indiana, calculate_louisiana, calculate_massachusetts
            
            special_rules = state_data.get('special_rules', {})
            result = None
            
            # Exact same if/elif chain as calculate_deadline endpoint (using variables)
            if state_code == "TX":
                result = calculate_texas(invoice_dt, project_type=project_type)
            elif state_code == "WA":
                result = calculate_washington(invoice_dt, role=role)
            elif state_code == "CA":
                result = calculate_california(invoice_dt, notice_of_completion_date=notice_of_completion_date, role=role)
            elif state_code == "OH":
                result = calculate_ohio(invoice_dt, project_type=project_type, notice_of_commencement_filed=notice_of_commencement_filed)
            elif state_code == "OR":
                result = calculate_oregon(invoice_dt)
            elif state_code == "HI":
                result = calculate_hawaii(invoice_dt)
            elif state_code == "NJ":
                result = calculate_newjersey(invoice_dt, project_type=project_type)
            elif state_code == "IN":
                result = calculate_indiana(invoice_dt, project_type=project_type)
            elif state_code == "LA":
                result = calculate_louisiana(invoice_dt, project_type=project_type)
            elif state_code == "MA":
                result = calculate_massachusetts(invoice_dt, project_type=project_type)
            else:
                # Default calculation for simple states (same as calculate_deadline endpoint)
                prelim_notice = state_data.get("preliminary_notice", {})
                lien_filing = state_data.get("lien_filing", {})
                
                result = calculate_default(
                    invoice_dt,
                    {
                        "preliminary_notice_required": prelim_notice.get("required", False),
                        "preliminary_notice_days": prelim_notice.get("days"),
                        "lien_filing_days": lien_filing.get("days"),
                        "notes": special_rules.get("notes", "")
                    },
                    weekend_extension=special_rules.get("weekend_extension", False),
                    holiday_extension=special_rules.get("holiday_extension", False)
                )
            
            # Extract deadlines from result
            prelim_deadline = result.get("preliminary_deadline")
            lien_deadline = result.get("lien_deadline")
            
            if prelim_deadline:
                prelim_deadline_str = prelim_deadline.strftime('%B %d, %Y')
                prelim_days_remaining = (prelim_deadline - datetime.now()).days
            
            if lien_deadline:
                lien_deadline_str = lien_deadline.strftime('%B %d, %Y')
                lien_days_remaining = (lien_deadline - datetime.now()).days
                
        except Exception as e:
            print(f"⚠️ Error calculating deadlines for PDF: {e}")
            # Fall back to showing general rules only
            has_invoice_date = False
    
    # Determine urgency colors
    def get_urgency_color(days_remaining):
        if days_remaining is None:
            return HexColor('#1f2937')  # Default gray
        if days_remaining < 0:
            return HexColor('#dc2626')  # Red - overdue
        elif days_remaining < 7:
            return HexColor('#ea580c')  # Orange - urgent
        elif days_remaining < 30:
            return HexColor('#f59e0b')  # Yellow - soon
        else:
            return HexColor('#16a34a')  # Green - safe
    
    # Create summary table - always show calculated dates if invoice_date provided, plus general rules
    summary_data = [
        ['Deadline Summary', ''],
    ]
    
    # Track row indices for styling
    current_row = 1
    
    # Add invoice date if provided
    if has_invoice_date and invoice_dt_str:
        summary_data.extend([
            ['', ''],
            ['Invoice/Delivery Date:', invoice_dt_str],
            ['', ''],
        ])
        invoice_date_row = current_row + 1  # Row 2 (0-indexed)
        current_row += 3
    
    # Add preliminary notice section
    prelim_deadline_row = None
    prelim_subtext_row = None
    if prelim_required:
        if has_invoice_date and prelim_deadline_str:
            # Show calculated deadline with general rule
            prelim_days_display = prelim_days if prelim_days else 'N/A'
            prelim_days_remaining_str = f'{prelim_days_remaining} days remaining' if prelim_days_remaining is not None else ''
            summary_data.extend([
                ['Preliminary Notice Deadline:', prelim_deadline_str],
                [f'  (Within {prelim_days_display} days of delivery)', prelim_days_remaining_str],
                ['', '']
            ])
            prelim_deadline_row = current_row
            prelim_subtext_row = current_row + 1
            current_row += 3
        else:
            # Show general rule only
            prelim_days_display = f'{prelim_days} days' if prelim_days and prelim_days != 'N/A' else 'Not required'
            summary_data.extend([
                ['Preliminary Notice Deadline:', prelim_days_display],
            ])
            prelim_deadline_row = current_row
            current_row += 1
    else:
        if has_invoice_date:
            # Show "Not Required" with calculated context
            summary_data.extend([
                ['Preliminary Notice Deadline:', 'Not Required'],
                ['  (None required for suppliers)', ''],
                ['', '']
            ])
            prelim_deadline_row = current_row
            current_row += 3
        else:
            # Show general rule only
            summary_data.extend([
                ['Preliminary Notice Deadline:', 'Not Required'],
            ])
            prelim_deadline_row = current_row
            current_row += 1
    
    # Add lien filing section
    lien_deadline_row = None
    lien_subtext_row = None
    if has_invoice_date and lien_deadline_str:
        # Show calculated deadline with general rule
        lien_days_display = lien_days if lien_days else 120
        lien_days_remaining_str = f'{lien_days_remaining} days remaining' if lien_days_remaining is not None else ''
        summary_data.extend([
            ['Lien Filing Deadline:', lien_deadline_str],
            [f'  (Within {lien_days_display} days of last furnishing)', lien_days_remaining_str]
        ])
        lien_deadline_row = current_row
        lien_subtext_row = current_row + 1
    else:
        # Show general rule only
        lien_days_display = f'{lien_days} days' if lien_days and lien_days != 'N/A' else 'N/A'
        summary_data.extend([
            ['Lien Filing Deadline:', lien_days_display],
        ])
        lien_deadline_row = current_row
    
    # Build table style
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 13),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 14),
        ('TOPPADDING', (0, 0), (-1, 0), 14),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f9fafb')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, HexColor('#e5e7eb')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        # Text colors
        ('TEXTCOLOR', (0, 1), (0, -1), HexColor('#374151')),
        ('TEXTCOLOR', (1, 1), (1, -1), HexColor('#1f2937')),
    ]
    
    # Add invoice date row styling if present
    if has_invoice_date and invoice_dt_str:
        table_style.extend([
            ('FONTNAME', (0, invoice_date_row), (-1, invoice_date_row), 'Helvetica-Bold'),
            ('FONTSIZE', (0, invoice_date_row), (-1, invoice_date_row), 11),
        ])
    
    # Add preliminary notice deadline row styling
    if prelim_deadline_row is not None:
        table_style.append(('FONTNAME', (0, prelim_deadline_row), (0, prelim_deadline_row), 'Helvetica-Bold'))
        
        # Add subtext styling if present
        if prelim_subtext_row is not None:
            table_style.extend([
                ('FONTNAME', (0, prelim_subtext_row), (-1, prelim_subtext_row), 'Helvetica-Oblique'),
                ('FONTSIZE', (0, prelim_subtext_row), (-1, prelim_subtext_row), 9),
            ])
            # Add urgency color for days remaining
            if prelim_days_remaining is not None:
                prelim_color = get_urgency_color(prelim_days_remaining)
                table_style.append(('TEXTCOLOR', (1, prelim_subtext_row), (1, prelim_subtext_row), prelim_color))
    
    # Add lien filing deadline row styling
    if lien_deadline_row is not None:
        table_style.append(('FONTNAME', (0, lien_deadline_row), (0, lien_deadline_row), 'Helvetica-Bold'))
        
        # Add subtext styling if present
        if lien_subtext_row is not None:
            table_style.extend([
                ('FONTNAME', (0, lien_subtext_row), (-1, lien_subtext_row), 'Helvetica-Oblique'),
                ('FONTSIZE', (0, lien_subtext_row), (-1, lien_subtext_row), 9),
            ])
            # Add urgency color for days remaining
            if lien_days_remaining is not None:
                lien_color = get_urgency_color(lien_days_remaining)
                table_style.append(('TEXTCOLOR', (1, lien_subtext_row), (1, lien_subtext_row), lien_color))
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle(table_style))
    
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
    
    # ===== DISCLAIMER SECTION =====
    story.append(Spacer(1, 0.4*inch))
    disclaimer_text = """
    <b>DISCLAIMER</b><br/>
    This is general information only, NOT legal advice. Always consult a licensed construction 
    attorney before taking any legal action. Deadlines vary based on project specifics, and this 
    tool cannot account for all variables. LienDeadline assumes no liability for missed deadlines 
    or legal consequences.
    """
    
    disclaimer_style = ParagraphStyle(
        'Disclaimer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#6b7280'),
        alignment=TA_LEFT,
        leftIndent=0,
        rightIndent=0,
        spaceAfter=8
    )
    disclaimer = Paragraph(disclaimer_text, disclaimer_style)
    
    # Create disclaimer box with border
    disclaimer_table = Table([[disclaimer]], colWidths=[5.5*inch])
    disclaimer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f3f4f6')),
        ('BOX', (0, 0), (-1, -1), 1, HexColor('#d1d5db')),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(disclaimer_table)
    story.append(Spacer(1, 0.2*inch))
    
    # ===== FOOTER SECTION =====
    footer_text = f"Page 1 of 1 | LienDeadline.com | Not Legal Advice"
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#9ca3af'),
        alignment=TA_CENTER,
        spaceAfter=4
    )
    story.append(Paragraph(footer_text, footer_style))
    
    # Social proof
    social_proof = "Trusted by 500+ material suppliers | ⭐⭐⭐⭐⭐ 4.9/5 rating"
    story.append(Paragraph(social_proof, ParagraphStyle('SocialProof', parent=styles['Normal'], fontSize=7, textColor=HexColor('#9ca3af'), alignment=TA_CENTER)))
    
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

class APIKeyRequest(BaseModel):
    company: str
    email: EmailStr
    phone: str | None = None
    volume: str
    use_case: str | None = None



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

@app.post("/api/logout")
async def logout(request: Request):
    """Logout endpoint - clears session token on server side"""
    authorization = request.headers.get('authorization', '')
    if not authorization or not authorization.startswith('Bearer '):
        return JSONResponse(
            status_code=200,
            content={"message": "Logged out successfully"}
        )
    
    token = authorization.replace('Bearer ', '')
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Clear session token in database
            if DB_TYPE == 'postgresql':
                cursor.execute("UPDATE users SET session_token = NULL WHERE session_token = %s", (token,))
            else:
                cursor.execute("UPDATE users SET session_token = NULL WHERE session_token = ?", (token,))
            
            conn.commit()
            print(f"✅ Session token cleared for logout")
    except Exception as e:
        print(f"⚠️ Error clearing session token: {e}")
        # Don't fail logout if DB update fails - client-side clearing is sufficient
    
    return JSONResponse(
        status_code=200,
        content={"message": "Logged out successfully"}
    )

@app.delete("/api/calculations/{calculation_id}")
async def delete_calculation(calculation_id: int, request: Request):
    """Delete a saved calculation/project"""
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Verify ownership before deleting
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    DELETE FROM calculations 
                    WHERE id = %s AND user_email = %s
                    RETURNING id
                """, (calculation_id, user['email']))
            else:
                cursor.execute("""
                    DELETE FROM calculations 
                    WHERE id = ? AND user_email = ?
                """, (calculation_id, user['email']))
            
            deleted = cursor.fetchone()
            
            if not deleted:
                raise HTTPException(404, "Project not found or you don't have permission to delete it")
            
            conn.commit()
            
            return {"success": True, "message": "Project deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting calculation: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, "Failed to delete project")



@app.post("/api/v1/request-api-key")
@limiter.limit("3/minute")
async def request_api_key(request: Request, api_request: APIKeyRequest):
    """
    Handle API key request submissions.
    Stores in database and sends notification emails.
    """
    
    try:
        # Get client IP
        client_ip = get_client_ip(request)
        
        # Server-side validation
        if not api_request.company or len(api_request.company.strip()) < 2:
            raise HTTPException(status_code=400, detail="Company name must be at least 2 characters")
        
        valid_volumes = ["<100", "100-500", "500-1000", ">1000"]
        if api_request.volume not in valid_volumes:
            raise HTTPException(status_code=400, detail=f"Volume must be one of: {', '.join(valid_volumes)}")
        
        # Store in database
        try:
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        INSERT INTO api_key_requests (company, email, phone, volume, use_case, ip_address, status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                    """, (
                        api_request.company.strip(),
                        api_request.email.strip(),
                        api_request.phone.strip() if api_request.phone else None,
                        api_request.volume,
                        api_request.use_case.strip() if api_request.use_case else None,
                        client_ip
                    ))
                else:
                    cursor.execute("""
                        INSERT INTO api_key_requests (company, email, phone, volume, use_case, ip_address, status)
                        VALUES (?, ?, ?, ?, ?, ?, 'pending')
                    """, (
                        api_request.company.strip(),
                        api_request.email.strip(),
                        api_request.phone.strip() if api_request.phone else None,
                        api_request.volume,
                        api_request.use_case.strip() if api_request.use_case else None,
                        client_ip
                    ))
                
                conn.commit()
                print(f"✅ API key request saved: {api_request.email} - {api_request.company}")
        except Exception as db_error:
            print(f"⚠️ Failed to save API key request to database: {db_error}")
            import traceback
            traceback.print_exc()
            # Continue even if DB save fails - still send email
        
        # Create email subject
        subject = f"[API Key Request] {api_request.company} – {api_request.email}"
        
        # Create email body (HTML)
        import html
        
        company_escaped = html.escape(api_request.company)
        email_escaped = html.escape(api_request.email)
        phone_escaped = html.escape(api_request.phone) if api_request.phone else "Not provided"
        volume_escaped = html.escape(api_request.volume)
        use_case_escaped = html.escape(api_request.use_case).replace('\n', '<br>') if api_request.use_case else "Not provided"
        ip_escaped = html.escape(client_ip)
        
        body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f9fafb; border-radius: 8px; padding: 24px; border: 1px solid #e5e7eb;">
        <h2 style="color: #1f2937; margin-top: 0; font-size: 24px;">New API Key Request</h2>
        
        <div style="background-color: white; border-radius: 6px; padding: 20px; margin-top: 16px;">
            <p><strong>Company:</strong> {company_escaped}</p>
            <p><strong>Email:</strong> <a href="mailto:{email_escaped}">{email_escaped}</a></p>
            <p><strong>Phone:</strong> {phone_escaped}</p>
            <p><strong>Monthly Project Volume:</strong> {volume_escaped}</p>
            <p><strong>IP Address:</strong> {ip_escaped}</p>
        </div>
        
        <div style="background-color: white; border-radius: 6px; padding: 20px; margin-top: 16px;">
            <h3 style="color: #1f2937; margin-top: 0;">Use Case:</h3>
            <div style="white-space: pre-wrap; color: #4b5563; line-height: 1.8;">{use_case_escaped}</div>
        </div>
        
        <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
            <p style="color: #6b7280; font-size: 14px; margin: 0;">
                Review this request in the admin dashboard and approve to send API key.
            </p>
        </div>
    </div>
</body>
</html>"""
        
        # Send notification email to admin
        admin_email = "support@liendeadline.com"
        try:
            send_email_sync(admin_email, subject, body_html)
            print(f"✅ Notification email sent to {admin_email}")
        except Exception as email_error:
            print(f"⚠️ Failed to send notification email: {email_error}")
            import traceback
            traceback.print_exc()
        
        # Send confirmation email to requester
        confirmation_subject = "API Key Request Received - LienDeadline"
        confirmation_body_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f9fafb; border-radius: 8px; padding: 24px; border: 1px solid #e5e7eb;">
        <h2 style="color: #1f2937; margin-top: 0; font-size: 24px;">Thank You for Your API Key Request</h2>
        
        <p>Hi {company_escaped},</p>
        
        <p>We've received your request for API access. Our team will review your application and send your API key within 24 hours.</p>
        
        <div style="background-color: white; border-radius: 6px; padding: 20px; margin: 20px 0;">
            <h3 style="color: #1f2937; margin-top: 0;">Request Details:</h3>
            <p><strong>Company:</strong> {company_escaped}</p>
            <p><strong>Monthly Project Volume:</strong> {volume_escaped}</p>
        </div>
        
        <p>In the meantime, you can:</p>
        <ul>
            <li>Try our <a href="https://liendeadline.com/test-api" style="color: #2563eb;">API tester</a> to see how it works</li>
            <li>Review our <a href="https://liendeadline.com/api.html#technical-docs" style="color: #2563eb;">technical documentation</a></li>
            <li>Check out our <a href="https://liendeadline.com/comparison.html" style="color: #2563eb;">comparison page</a> to see how we stack up</li>
        </ul>
        
        <p>If you have any questions, feel free to reply to this email.</p>
        
        <p style="margin-top: 24px; color: #6b7280; font-size: 14px;">
            Best regards,<br>
            The LienDeadline Team
        </p>
    </div>
</body>
</html>"""
        
        try:
            send_email_sync(api_request.email.strip(), confirmation_subject, confirmation_body_html)
            print(f"✅ Confirmation email sent to {api_request.email}")
        except Exception as email_error:
            print(f"⚠️ Failed to send confirmation email: {email_error}")
            import traceback
            traceback.print_exc()
        
        return JSONResponse(content={
            "success": True,
            "message": "API key request received. We'll review and send your API key within 24 hours."
        })
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error processing API key request: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Internal server error. Please try again later.")

@app.post("/api/contact")
@limiter.limit("5/minute")
async def submit_contact_form(request: Request, contact_data: ContactRequest):
    """
    Handle contact form submissions.
    Validates input, stores in database, and sends email via Resend.
    """
    
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
            # Fallback
            if os.path.exists("admin-dashboard.html"):
                file_path = Path("admin-dashboard.html")
            else:
                raise HTTPException(status_code=404, detail="Admin dashboard V1 not found")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    else:
        # Serve V2 dashboard (default)
        file_path = BASE_DIR / "admin-dashboard-v2.html"
        if not file_path.exists():
            # Fallback
            if os.path.exists("admin-dashboard-v2.html"):
                file_path = Path("admin-dashboard-v2.html")
            else:
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

@app.get("/admin-dashboard.html")
async def serve_admin_dashboard_html(username: str = Depends(verify_admin)):
    """Serve admin dashboard V1 with HTTP Basic Auth"""
    file_path = BASE_DIR / "admin-dashboard.html"
    if not file_path.exists():
        if os.path.exists("admin-dashboard.html"):
            file_path = Path("admin-dashboard.html")
        else:
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

@app.get("/admin-dashboard-v2")
async def serve_admin_dashboard_v2(username: str = Depends(verify_admin)):
    """Serve admin dashboard V2 with HTTP Basic Auth"""
    file_path = BASE_DIR / "admin-dashboard-v2.html"
    if not file_path.exists():
        if os.path.exists("admin-dashboard-v2.html"):
            file_path = Path("admin-dashboard-v2.html")
        else:
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

@app.get("/admin-dashboard.js")
async def serve_admin_dashboard_js(username: str = Depends(verify_admin)):
    """Serve admin dashboard V1 JavaScript"""
    file_path = BASE_DIR / "admin-dashboard.js"
    if not file_path.exists():
         if os.path.exists("admin-dashboard.js"):
            file_path = Path("admin-dashboard.js")
         else:
            raise HTTPException(status_code=404, detail="Admin dashboard JS not found")
    
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

@app.get("/admin-dashboard-v2.js")
async def serve_admin_dashboard_v2_js(username: str = Depends(verify_admin)):
    """Serve admin dashboard V2 JavaScript"""
    file_path = BASE_DIR / "admin-dashboard-v2.js"
    if not file_path.exists():
         if os.path.exists("admin-dashboard-v2.js"):
            file_path = Path("admin-dashboard-v2.js")
         else:
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

@app.get("/state-coverage.html")
async def serve_state_coverage_html():
    """Redirect state-coverage.html to homepage"""
    return RedirectResponse(url="/", status_code=301)

@app.get("/state-coverage")
async def serve_state_coverage_clean():
    """Redirect /state-coverage to homepage"""
    return RedirectResponse(url="/", status_code=301)

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

@app.get("/privacy.html")
async def serve_privacy_html():
    """Serve privacy policy page"""
    file_path = BASE_DIR / "privacy.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="privacy.html not found in project root")
    return FileResponse(file_path, media_type="text/html")

@app.get("/help.html")
async def serve_help_html():
    """Serve help center page"""
    file_path = BASE_DIR / "help.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="help.html not found in project root")
    return FileResponse(file_path, media_type="text/html")

@app.get("/about.html")
async def serve_about_html():
    """Serve about us page"""
    file_path = BASE_DIR / "about.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="about.html not found in project root")
    return FileResponse(file_path, media_type="text/html")

@app.get("/security.html")
async def serve_security_html():
    """Serve security page"""
    file_path = BASE_DIR / "security.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="security.html not found in project root")
    return FileResponse(file_path, media_type="text/html")

@app.get("/cookies.html")
async def serve_cookies_html():
    """Serve cookie policy page"""
    file_path = BASE_DIR / "cookies.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="cookies.html not found in project root")
    return FileResponse(file_path, media_type="text/html")

# Clean URLs (without .html extension)
@app.get("/calculator")
async def serve_calculator_clean():
    """Clean URL: /calculator → calculator.html"""
    file_path = BASE_DIR / "calculator.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Calculator not found")
    return FileResponse(file_path)

# Removed redirect - /dashboard now serves React app (see line 1295)


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

@app.get("/privacy")
async def serve_privacy_clean():
    """Clean URL: /privacy → privacy.html"""
    file_path = BASE_DIR / "privacy.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Privacy page not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/help")
async def serve_help_clean():
    """Clean URL: /help → help.html"""
    file_path = BASE_DIR / "help.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Help page not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/about")
async def serve_about_clean():
    """Clean URL: /about → about.html"""
    file_path = BASE_DIR / "about.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="About page not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/security")
async def serve_security_clean():
    """Clean URL: /security → security.html"""
    file_path = BASE_DIR / "security.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Security page not found")
    return FileResponse(file_path, media_type="text/html")

@app.get("/cookies")
async def serve_cookies_clean():
    """Clean URL: /cookies → cookies.html"""
    file_path = BASE_DIR / "cookies.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Cookies page not found")
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
    Redirect /customer-dashboard to React dashboard at /dashboard
    """
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard", status_code=301)







class ChangePasswordRequest(BaseModel):
    email: str
    old_password: str
    new_password: str





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



# Track email endpoint for calculator gating
class TrackEmailRequest(BaseModel):
    email: str
    timestamp: str





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



@app.post("/v1/send-email")
async def send_email(data: dict):
    """Send calculation results via email using centralized service"""
    try:
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
        
        # Send via centralized service
        success = send_email_sync(
            to_email=to_email,
            subject="Your Lien Deadline Calculation - LienDeadline.com",
            content=html_content
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to send email. Please check server logs.")
        
        return {"status": "success", "message": "Email sent successfully!"}
        
    except Exception as e:
        print(f"Email error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")





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




# ==========================================
# TEST EMAIL ENDPOINT (REMOVE AFTER TESTING)
# ==========================================


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
                content="If you received this, SMTP works.",
                is_html=False
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































# ==========================================
# SAGE OAuth Integration
# ==========================================

# Sage OAuth credentials from environment
SAGE_CLIENT_ID = os.getenv("SAGE_CLIENT_ID")
SAGE_CLIENT_SECRET = os.getenv("SAGE_CLIENT_SECRET")
SAGE_REDIRECT_URI = os.getenv("SAGE_REDIRECT_URI", "https://liendeadline.com/api/sage/callback")

# Sage OAuth URLs
# Using Sage Operations API endpoints (uses Sage Intacct OAuth 2.0 infrastructure)
SAGE_AUTH_URL = "https://api.intacct.com/ia/api/v1/oauth2/authorize"
SAGE_TOKEN_URL = "https://api.intacct.com/ia/api/v1/oauth2/token"
SAGE_API_BASE = "https://api.intacct.com"

# Sage scopes
SAGE_SCOPES = "full_access"

# Procore OAuth credentials from environment
PROCORE_CLIENT_ID = os.getenv("PROCORE_CLIENT_ID")
PROCORE_CLIENT_SECRET = os.getenv("PROCORE_CLIENT_SECRET")
PROCORE_REDIRECT_URI = os.getenv("PROCORE_REDIRECT_URI", "https://liendeadline.com/api/procore/callback")

# Procore OAuth URLs
PROCORE_AUTH_URL = "https://login.procore.com/oauth/authorize"
PROCORE_TOKEN_URL = "https://login.procore.com/oauth/token"
PROCORE_API_BASE = "https://api.procore.com/rest/v1.0"

# Procore OAuth does not use scope parameters - permissions are configured in developer portal


def get_sage_basic_auth():
    """Create Basic Auth header for Sage token exchange"""
    credentials = f"{SAGE_CLIENT_ID}:{SAGE_CLIENT_SECRET}"
    return base64.b64encode(credentials.encode()).decode()


def get_sage_user_from_session(authorization: str = Header(None)):
    """Get user email from session token for Sage - matches working endpoints"""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    
    token = authorization.replace('Bearer ', '')
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Use same lookup as working endpoints: users table with session_token
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT email, id FROM users 
                    WHERE session_token = %s
                """, (token,))
            else:
                cursor.execute("""
                    SELECT email, id FROM users 
                    WHERE session_token = ?
                """, (token,))
            
            result = cursor.fetchone()
            if result:
                if DB_TYPE == 'postgresql':
                    return {"email": result['email'], "id": result['id']}
                else:
                    return {"email": result[0], "id": result[1]}
    except Exception as e:
        print(f"Error getting user from session: {e}")
    
    return None


def get_procore_basic_auth():
    """Create Basic Auth header for Procore token exchange"""
    credentials = f"{PROCORE_CLIENT_ID}:{PROCORE_CLIENT_SECRET}"
    return base64.b64encode(credentials.encode()).decode()


def get_procore_user_from_session(authorization: str = Header(None)):
    """Get user email from session token for Procore - matches working endpoints"""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    
    token = authorization.replace('Bearer ', '')
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Use same lookup as working endpoints: users table with session_token
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT email, id FROM users 
                    WHERE session_token = %s
                """, (token,))
            else:
                cursor.execute("""
                    SELECT email, id FROM users 
                    WHERE session_token = ?
                """, (token,))
            
            result = cursor.fetchone()
            if result:
                if DB_TYPE == 'postgresql':
                    return {"email": result['email'], "id": result['id']}
                else:
                    return {"email": result[0], "id": result[1]}
    except Exception as e:
        print(f"Error getting user from session: {e}")
    
    return None


async def refresh_procore_access_token(user_email: str):
    """Refresh Procore access token using refresh token"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT refresh_token FROM procore_tokens WHERE user_email = %s
                """, (user_email,))
            else:
                cursor.execute("""
                    SELECT refresh_token FROM procore_tokens WHERE user_email = ?
                """, (user_email,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            refresh_token = result['refresh_token'] if DB_TYPE == 'postgresql' else result[0]
            
            if not refresh_token:
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    PROCORE_TOKEN_URL,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    data={
                        "client_id": PROCORE_CLIENT_ID,
                        "client_secret": PROCORE_CLIENT_SECRET,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                )
                
                if response.status_code != 200:
                    return None
                
                tokens = response.json()
                expires_in = tokens.get('expires_in', 3600)
                expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # Update tokens
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE procore_tokens
                        SET access_token = %s, refresh_token = %s, expires_at = %s, updated_at = NOW()
                        WHERE user_email = %s
                    """, (tokens['access_token'], tokens.get('refresh_token', refresh_token), 
                          expires_at, user_email))
                else:
                    cursor.execute("""
                        UPDATE procore_tokens
                        SET access_token = ?, refresh_token = ?, expires_at = ?, updated_at = datetime('now')
                        WHERE user_email = ?
                    """, (tokens['access_token'], tokens.get('refresh_token', refresh_token), 
                          expires_at, user_email))
                
                conn.commit()
                return tokens['access_token']
    except Exception as e:
        print(f"Error refreshing Procore token: {e}")
        return None


async def get_valid_procore_access_token(user_email: str):
    """Get valid Procore access token, refreshing if necessary"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT access_token, expires_at FROM procore_tokens WHERE user_email = %s
                """, (user_email,))
            else:
                cursor.execute("""
                    SELECT access_token, expires_at FROM procore_tokens WHERE user_email = ?
                """, (user_email,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            if DB_TYPE == 'postgresql':
                access_token = result['access_token']
                expires_at = result['expires_at']
            else:
                access_token = result[0]
                expires_at = datetime.fromisoformat(result[1]) if isinstance(result[1], str) else result[1]
            
            # Check if token is expired (with 5 minute buffer)
            if expires_at and expires_at < datetime.now() + timedelta(minutes=5):
                # Refresh token
                new_token = await refresh_procore_access_token(user_email)
                if new_token:
                    return new_token
                return None
            
            return access_token
    except Exception as e:
        print(f"Error getting valid Procore token: {e}")
        return None


async def refresh_sage_access_token(user_email: str):
    """Refresh Sage access token using refresh token"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT refresh_token FROM sage_tokens WHERE user_email = %s
                """, (user_email,))
            else:
                cursor.execute("""
                    SELECT refresh_token FROM sage_tokens WHERE user_email = ?
                """, (user_email,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            refresh_token = result['refresh_token'] if DB_TYPE == 'postgresql' else result[0]
            
            if not refresh_token:
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    SAGE_TOKEN_URL,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {get_sage_basic_auth()}"
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                )
                
                if response.status_code != 200:
                    return None
                
                tokens = response.json()
                expires_in = tokens.get('expires_in', 3600)
                expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # Update tokens
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE sage_tokens
                        SET access_token = %s, refresh_token = %s, expires_at = %s, updated_at = NOW()
                        WHERE user_email = %s
                    """, (tokens['access_token'], tokens.get('refresh_token', refresh_token), 
                          expires_at, user_email))
                else:
                    cursor.execute("""
                        UPDATE sage_tokens
                        SET access_token = ?, refresh_token = ?, expires_at = ?, updated_at = datetime('now')
                        WHERE user_email = ?
                    """, (tokens['access_token'], tokens.get('refresh_token', refresh_token), 
                          expires_at, user_email))
                
                conn.commit()
                return tokens['access_token']
    except Exception as e:
        print(f"Error refreshing Sage token: {e}")
        return None


async def get_valid_sage_access_token(user_email: str):
    """Get valid Sage access token, refreshing if necessary"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT access_token, expires_at FROM sage_tokens WHERE user_email = %s
                """, (user_email,))
            else:
                cursor.execute("""
                    SELECT access_token, expires_at FROM sage_tokens WHERE user_email = ?
                """, (user_email,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            if DB_TYPE == 'postgresql':
                access_token = result['access_token']
                expires_at = result['expires_at']
            else:
                access_token = result[0]
                expires_at = datetime.fromisoformat(result[1]) if isinstance(result[1], str) else result[1]
            
            # Check if token is expired (with 5 minute buffer)
            if expires_at and expires_at < datetime.now() + timedelta(minutes=5):
                # Refresh token
                new_token = await refresh_sage_access_token(user_email)
                return new_token if new_token else access_token
            
            return access_token
    except Exception as e:
        print(f"Error getting Sage access token: {e}")
        return None


@app.get("/api/sage/auth")
async def sage_auth(request: Request):
    """
    Initiate Sage OAuth flow
    Redirects user to Sage authorization page
    Accepts token via query parameter (for browser redirects) or Authorization header
    """
    if not SAGE_CLIENT_ID or not SAGE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Sage integration not configured")
    
    # Extract token from query parameter (browser redirect) or Authorization header
    token = request.query_params.get('token')
    if not token:
        # Try Authorization header
        authorization = request.headers.get('authorization') or request.headers.get('Authorization')
        if authorization and authorization.startswith('Bearer '):
            token = authorization.replace('Bearer ', '').strip()
    
    if not token:
        # Redirect to login if no token
        return RedirectResponse(url="/dashboard?error=Please log in first")
    
    # Look up user from token
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = ?", (token,))
            
            user_result = cursor.fetchone()
            
            if not user_result:
                return RedirectResponse(url="/dashboard?error=Invalid session")
            
            # Extract user info
            if isinstance(user_result, dict):
                user_id = user_result.get('id')
                user_email = user_result.get('email', '')
                subscription_status = user_result.get('subscription_status', '')
            else:
                user_id = user_result[0] if len(user_result) > 0 else None
                user_email = user_result[1] if len(user_result) > 1 else ''
                subscription_status = user_result[2] if len(user_result) > 2 else ''
            
            if subscription_status not in ['active', 'trialing']:
                return RedirectResponse(url="/dashboard?error=Subscription expired")
            
            user = {"id": user_id, "email": user_email}
    except Exception as e:
        print(f"Error looking up user: {e}")
        return RedirectResponse(url="/dashboard?error=Authentication failed")
    
    # Generate secure random state and store it with user email
    state = secrets.token_urlsafe(32)
    
    # Store state temporarily (expires in 10 minutes)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create oauth_states table if it doesn't exist (for Sage)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sage_oauth_states (
                        id SERIAL PRIMARY KEY,
                        user_email VARCHAR(255) NOT NULL,
                        state VARCHAR(255) UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL
                    )
                """)
                cursor.execute("""
                    INSERT INTO sage_oauth_states (user_email, state, expires_at)
                    VALUES (%s, %s, %s)
                """, (user['email'], state, datetime.now() + timedelta(minutes=10)))
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sage_oauth_states (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_email TEXT NOT NULL,
                        state TEXT UNIQUE NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    INSERT INTO sage_oauth_states (user_email, state, expires_at)
                    VALUES (?, ?, ?)
                """, (user['email'], state, datetime.now() + timedelta(minutes=10)))
            
            conn.commit()
    except Exception as e:
        print(f"Error storing Sage OAuth state: {e}")
    
    params = {
        "client_id": SAGE_CLIENT_ID,
        "scope": SAGE_SCOPES,
        "redirect_uri": SAGE_REDIRECT_URI,
        "response_type": "code",
        "state": state
    }
    
    auth_url = f"{SAGE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@app.get("/api/sage/callback")
async def sage_callback(code: str, state: str):
    """
    Handle OAuth callback from Sage
    Exchange authorization code for access token
    """
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing required parameters")
    
    # Verify state and get user email
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT user_email FROM sage_oauth_states
                    WHERE state = %s AND expires_at > NOW()
                """, (state,))
            else:
                cursor.execute("""
                    SELECT user_email FROM sage_oauth_states
                    WHERE state = ? AND expires_at > datetime('now')
                """, (state,))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=400, detail="Invalid or expired state")
            
            user_email = result['user_email'] if DB_TYPE == 'postgresql' else result[0]
            
            # Delete used state
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM sage_oauth_states WHERE state = %s", (state,))
            else:
                cursor.execute("DELETE FROM sage_oauth_states WHERE state = ?", (state,))
            
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying Sage state: {e}")
        raise HTTPException(status_code=500, detail="Error verifying OAuth state")
    
    # Exchange code for tokens
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SAGE_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {get_sage_basic_auth()}"
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": SAGE_REDIRECT_URI
                }
            )
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"Sage token exchange failed: {error_detail}")
                raise HTTPException(status_code=400, detail=f"Failed to get access token: {error_detail}")
            
            tokens = response.json()
            
            # Calculate expiration time
            expires_in = tokens.get('expires_in', 3600)  # Default 1 hour
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Save tokens to database
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                # Check if user already has tokens
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id FROM sage_tokens WHERE user_email = %s
                    """, (user_email,))
                else:
                    cursor.execute("""
                        SELECT id FROM sage_tokens WHERE user_email = ?
                    """, (user_email,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing tokens
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            UPDATE sage_tokens
                            SET realm_id = %s, access_token = %s, refresh_token = %s,
                                expires_at = %s, updated_at = NOW()
                            WHERE user_email = %s
                        """, (tokens.get('realm_id'), tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_email))
                    else:
                        cursor.execute("""
                            UPDATE sage_tokens
                            SET realm_id = ?, access_token = ?, refresh_token = ?,
                                expires_at = ?, updated_at = datetime('now')
                            WHERE user_email = ?
                        """, (tokens.get('realm_id'), tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_email))
                else:
                    # Insert new tokens
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            INSERT INTO sage_tokens 
                            (user_email, realm_id, access_token, refresh_token, expires_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (user_email, tokens.get('realm_id'), tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                    else:
                        cursor.execute("""
                            INSERT INTO sage_tokens 
                            (user_email, realm_id, access_token, refresh_token, expires_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (user_email, tokens.get('realm_id'), tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                
                conn.commit()
            
            # Redirect to customer dashboard with success message
            return RedirectResponse(url="/customer-dashboard.html?sage_connected=true")
            
    except httpx.HTTPError as e:
        print(f"HTTP error during Sage token exchange: {e}")
        raise HTTPException(status_code=500, detail="Error connecting to Sage")
    except Exception as e:
        print(f"Error during Sage token exchange: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unexpected error during OAuth")


@app.get("/api/sage/status")
async def get_sage_status(request: Request, authorization: str = Header(None)):
    """Check if user has Sage connected"""
    user = get_sage_user_from_session(authorization)
    if not user:
        return {"connected": False}
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT realm_id, expires_at FROM sage_tokens WHERE user_email = %s
                """, (user['email'],))
            else:
                cursor.execute("""
                    SELECT realm_id, expires_at FROM sage_tokens WHERE user_email = ?
                """, (user['email'],))
            
            result = cursor.fetchone()
            if result:
                expires_at = result['expires_at'] if DB_TYPE == 'postgresql' else result[1]
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                is_valid = expires_at and expires_at > datetime.now()
                return {"connected": True, "valid": is_valid}
    except Exception:
        pass
    
    return {"connected": False}


@app.post("/api/sage/disconnect")
async def disconnect_sage(request: Request, current_user: dict = Depends(get_current_user)):
    """Disconnect Sage account"""
    user = current_user
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM sage_tokens WHERE user_email = %s", (user['email'],))
            else:
                cursor.execute("DELETE FROM sage_tokens WHERE user_email = ?", (user['email'],))
            
            conn.commit()
            return {"success": True, "message": "Sage account disconnected"}
    except Exception as e:
        print(f"Error disconnecting Sage: {e}")
        raise HTTPException(status_code=500, detail="Error disconnecting Sage account")


@app.get("/api/sage/invoices")
async def get_sage_invoices(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Fetch invoices from Sage
    Calculate lien deadlines for each
    """
    # Use current_user from dependency
    user = current_user
    
    # Get valid access token
    access_token = await get_valid_sage_access_token(user['email'])
    if not access_token:
        raise HTTPException(status_code=401, detail="Sage not connected. Please connect your account first.")
    
    # Get realm_id
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT realm_id FROM sage_tokens WHERE user_email = %s
                """, (user['email'],))
            else:
                cursor.execute("""
                    SELECT realm_id FROM sage_tokens WHERE user_email = ?
                """, (user['email'],))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=401, detail="Sage not connected")
            
            realm_id = result['realm_id'] if DB_TYPE == 'postgresql' else result[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting realm_id: {e}")
        raise HTTPException(status_code=500, detail="Error accessing Sage connection")
    
    # Fetch invoices from Sage
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SAGE_API_BASE}/sales_invoices",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}",
                    "X-Business": realm_id
                },
                params={
                    "items_per_page": 100
                }
            )
            
            if response.status_code == 401:
                # Token expired, try refreshing
                new_token = await refresh_sage_access_token(user['email'])
                if new_token:
                    # Retry with new token
                    response = await client.get(
                        f"{SAGE_API_BASE}/sales_invoices",
                        headers={
                            "Accept": "application/json",
                            "Authorization": f"Bearer {new_token}",
                            "X-Business": realm_id
                        },
                        params={
                            "items_per_page": 100
                        }
                    )
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"Sage API error: {error_detail}")
                raise HTTPException(status_code=400, detail=f"Failed to fetch invoices: {error_detail}")
            
            data = response.json()
            invoices = data.get("$items", [])
            
            # Process invoices
            results = []
            for invoice in invoices:
                invoice_date = invoice.get("date")
                contact = invoice.get("contact", {})
                customer_name = contact.get("displayed_as", "Unknown")
                amount = invoice.get("net_amount", 0)
                invoice_id = invoice.get("id")
                
                # Try to get customer address for state determination
                customer_state = None
                if "main_address" in contact:
                    main_addr = contact["main_address"]
                    customer_state = main_addr.get("region")
                
                results.append({
                    "invoice_id": invoice_id,
                    "customer": customer_name,
                    "date": invoice_date,
                    "amount": float(amount) if amount else 0.0,
                    "state": customer_state,
                    "preliminary_deadline": None,  # Will be calculated on demand
                    "lien_deadline": None  # Will be calculated on demand
                })
            
            return {"invoices": results, "count": len(results)}
            
    except httpx.HTTPError as e:
        print(f"HTTP error fetching Sage invoices: {e}")
        raise HTTPException(status_code=500, detail="Error connecting to Sage")
    except Exception as e:
        print(f"Error fetching Sage invoices: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unexpected error fetching invoices")


# ============================================================================
# PROCORE OAUTH INTEGRATION ENDPOINTS
# ============================================================================

@app.get("/api/procore/auth")
async def procore_auth(request: Request):
    """
    Initiate Procore OAuth flow
    Redirects user to Procore authorization page
    Accepts token via query parameter (for browser redirects) or Authorization header
    """
    if not PROCORE_CLIENT_ID or not PROCORE_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Procore integration not configured")
    
    # Extract token from query parameter (browser redirect) or Authorization header
    token = request.query_params.get('token')
    if not token:
        # Try Authorization header
        authorization = request.headers.get('authorization') or request.headers.get('Authorization')
        if authorization and authorization.startswith('Bearer '):
            token = authorization.replace('Bearer ', '').strip()
    
    if not token:
        # Redirect to login if no token
        return RedirectResponse(url="/dashboard?error=Please log in first")
    
    # Look up user from token
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = ?", (token,))
            
            user_result = cursor.fetchone()
            
            if not user_result:
                return RedirectResponse(url="/dashboard?error=Invalid session")
            
            # Extract user info
            if isinstance(user_result, dict):
                user_id = user_result.get('id')
                user_email = user_result.get('email', '')
                subscription_status = user_result.get('subscription_status', '')
            else:
                user_id = user_result[0] if len(user_result) > 0 else None
                user_email = user_result[1] if len(user_result) > 1 else ''
                subscription_status = user_result[2] if len(user_result) > 2 else ''
            
            if subscription_status not in ['active', 'trialing']:
                return RedirectResponse(url="/dashboard?error=Subscription expired")
            
            user = {"id": user_id, "email": user_email}
    except Exception as e:
        print(f"Error looking up user: {e}")
        return RedirectResponse(url="/dashboard?error=Authentication failed")
    
    # Generate secure random state and store it with user email
    state = secrets.token_urlsafe(32)
    
    # Store state temporarily (expires in 10 minutes)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Create oauth_states table if it doesn't exist (for Procore)
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS procore_oauth_states (
                        id SERIAL PRIMARY KEY,
                        user_email VARCHAR(255) NOT NULL,
                        state VARCHAR(255) UNIQUE NOT NULL,
                        expires_at TIMESTAMP NOT NULL
                    )
                """)
                cursor.execute("""
                    INSERT INTO procore_oauth_states (user_email, state, expires_at)
                    VALUES (%s, %s, %s)
                """, (user['email'], state, datetime.now() + timedelta(minutes=10)))
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS procore_oauth_states (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_email TEXT NOT NULL,
                        state TEXT UNIQUE NOT NULL,
                        expires_at TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    INSERT INTO procore_oauth_states (user_email, state, expires_at)
                    VALUES (?, ?, ?)
                """, (user['email'], state, datetime.now() + timedelta(minutes=10)))
            
            conn.commit()
    except Exception as e:
        print(f"Error storing Procore OAuth state: {e}")
    
    # Build OAuth URL properly - Procore does NOT use scope parameters
    # Permissions are configured in the Procore developer portal
    params = {
        "response_type": "code",
        "client_id": PROCORE_CLIENT_ID,
        "redirect_uri": PROCORE_REDIRECT_URI,
        "state": state
    }
    
    # Use urlencode() to properly encode all parameters
    auth_url = f"{PROCORE_AUTH_URL}?{urlencode(params)}"
    
    # Debug logging
    print("=" * 60)
    print("🔍 Procore OAuth Connect Debug")
    print("=" * 60)
    print(f"PROCORE_CLIENT_ID: {PROCORE_CLIENT_ID[:10]}..." if PROCORE_CLIENT_ID else "PROCORE_CLIENT_ID: None")
    print(f"PROCORE_REDIRECT_URI: {PROCORE_REDIRECT_URI}")
    print(f"PROCORE_AUTH_URL: {PROCORE_AUTH_URL}")
    print(f"Complete OAuth URL: {auth_url}")
    print("=" * 60)
    
    return RedirectResponse(url=auth_url)


@app.get("/api/procore/callback")
async def procore_callback(code: str, state: str):
    """
    Handle OAuth callback from Procore
    Exchange authorization code for access token
    """
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing required parameters")
    
    # Verify state and get user email
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT user_email FROM procore_oauth_states
                    WHERE state = %s AND expires_at > NOW()
                """, (state,))
            else:
                cursor.execute("""
                    SELECT user_email FROM procore_oauth_states
                    WHERE state = ? AND expires_at > datetime('now')
                """, (state,))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=400, detail="Invalid or expired state")
            
            user_email = result['user_email'] if DB_TYPE == 'postgresql' else result[0]
            
            # Delete used state
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM procore_oauth_states WHERE state = %s", (state,))
            else:
                cursor.execute("DELETE FROM procore_oauth_states WHERE state = ?", (state,))
            
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying Procore state: {e}")
        raise HTTPException(status_code=500, detail="Error verifying OAuth state")
    
    # Exchange code for tokens
    # Procore requires Basic Authentication - client_id:client_secret in Authorization header
    # Do NOT include client_id/client_secret in POST body
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                PROCORE_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {get_procore_basic_auth()}"
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": PROCORE_REDIRECT_URI
                }
            )
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"Procore token exchange failed: {error_detail}")
                raise HTTPException(status_code=400, detail=f"Failed to get access token: {error_detail}")
            
            tokens = response.json()
            
            # Calculate expiration time
            expires_in = tokens.get('expires_in', 3600)  # Default 1 hour
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Save tokens to database
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                # Check if user already has tokens
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id FROM procore_tokens WHERE user_email = %s
                    """, (user_email,))
                else:
                    cursor.execute("""
                        SELECT id FROM procore_tokens WHERE user_email = ?
                    """, (user_email,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing tokens
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            UPDATE procore_tokens
                            SET access_token = %s, refresh_token = %s,
                                expires_at = %s, updated_at = NOW()
                            WHERE user_email = %s
                        """, (tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_email))
                    else:
                        cursor.execute("""
                            UPDATE procore_tokens
                            SET access_token = ?, refresh_token = ?,
                                expires_at = ?, updated_at = datetime('now')
                            WHERE user_email = ?
                        """, (tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_email))
                else:
                    # Insert new tokens
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            INSERT INTO procore_tokens 
                            (user_email, access_token, refresh_token, expires_at)
                            VALUES (%s, %s, %s, %s)
                        """, (user_email, tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                    else:
                        cursor.execute("""
                            INSERT INTO procore_tokens 
                            (user_email, access_token, refresh_token, expires_at)
                            VALUES (?, ?, ?, ?)
                        """, (user_email, tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                
                conn.commit()
            
            # Redirect to customer dashboard with success message
            return RedirectResponse(url="/dashboard?procore_connected=true")
            
    except httpx.HTTPError as e:
        print(f"HTTP error during Procore token exchange: {e}")
        raise HTTPException(status_code=500, detail="Error connecting to Procore")
    except Exception as e:
        print(f"Error during Procore token exchange: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unexpected error during OAuth")


@app.get("/api/procore/status")
async def get_procore_status(request: Request, authorization: str = Header(None)):
    """Check if user has Procore connected"""
    user = get_procore_user_from_session(authorization)
    if not user:
        return {"connected": False}
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT expires_at FROM procore_tokens WHERE user_email = %s
                """, (user['email'],))
            else:
                cursor.execute("""
                    SELECT expires_at FROM procore_tokens WHERE user_email = ?
                """, (user['email'],))
            
            result = cursor.fetchone()
            if result:
                expires_at = result['expires_at'] if DB_TYPE == 'postgresql' else result[0]
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                is_valid = expires_at and expires_at > datetime.now()
                return {"connected": True, "valid": is_valid}
    except Exception:
        pass
    
    return {"connected": False}


@app.post("/api/procore/disconnect")
async def disconnect_procore(request: Request, current_user: dict = Depends(get_current_user)):
    """Disconnect Procore account"""
    user = current_user
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM procore_tokens WHERE user_email = %s", (user['email'],))
            else:
                cursor.execute("DELETE FROM procore_tokens WHERE user_email = ?", (user['email'],))
            
            conn.commit()
            return {"success": True, "message": "Procore account disconnected"}
    except Exception as e:
        print(f"Error disconnecting Procore: {e}")
        raise HTTPException(status_code=500, detail="Error disconnecting Procore account")


@app.get("/api/procore/projects")
async def get_procore_projects(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Fetch projects from Procore
    """
    # Use current_user from dependency
    user = current_user
    
    # Get valid access token
    access_token = await get_valid_procore_access_token(user['email'])
    if not access_token:
        raise HTTPException(status_code=401, detail="Procore not connected. Please connect your account first.")
    
    # Fetch projects from Procore
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{PROCORE_API_BASE}/projects",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}"
                }
            )
            
            if response.status_code == 401:
                # Token expired, try refreshing
                new_token = await refresh_procore_access_token(user['email'])
                if new_token:
                    response = await client.get(
                        f"{PROCORE_API_BASE}/projects",
                        headers={
                            "Accept": "application/json",
                            "Authorization": f"Bearer {new_token}"
                        }
                    )
                else:
                    raise HTTPException(status_code=401, detail="Procore token expired. Please reconnect.")
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Procore API error: {response.text}")
            
            projects = response.json()
            return {"projects": projects}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching Procore projects: {e}")
        raise HTTPException(status_code=500, detail="Error fetching Procore projects")


# Serve images from public/images directory
# IMPORTANT: Use explicit route instead of mount to avoid conflicts with catch-all / mount
images_dir = PROJECT_ROOT / "public" / "images"
# Create directories if they don't exist (resilience fix)
os.makedirs(str(images_dir), exist_ok=True)
print(f"🖼️ images_dir={images_dir} exists={images_dir.exists()}")
if images_dir.exists():
    logo_path = images_dir / "liendeadline-logo.png"
    print(f"📸 Logo file exists: {logo_path.exists()} at {logo_path}")
    
    @app.get("/images/{filename}")
    async def serve_image(filename: str):
        """Serve images from public/images directory"""
        file_path = images_dir / filename
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        raise HTTPException(status_code=404, detail="Image not found")
    
    print(f"✅ Registered /images/{{filename}} route -> {images_dir}")
else:
    print(f"⚠️ WARNING: images_dir does not exist: {images_dir}")

# Serve static files from public directory (favicons, manifest, etc.)
# This mount must be LAST so API routes take precedence
public_dir = PROJECT_ROOT / "public"
# Create directory if it doesn't exist (resilience fix)
os.makedirs(str(public_dir), exist_ok=True)
print(f"📁 public_dir={public_dir} exists={public_dir.exists()}")

# State guide routes - must be BEFORE StaticFiles mount to prevent redirect loops
# Handle trailing slash: redirect /state-lien-guides/{state}/ -> /state-lien-guides/{state}
@app.get("/state-lien-guides/{state}/")
async def redirect_state_guide_trailing_slash(state: str):
    """Redirect trailing slash to non-trailing slash for state guides"""
    return RedirectResponse(url=f"/state-lien-guides/{state}", status_code=301)

# Handle non-trailing slash: serve index.html if it exists
@app.get("/state-lien-guides/{state}")
async def serve_state_guide(state: str):
    """Serve state guide index.html file"""
    if public_dir.exists():
        index_file = public_dir / "state-lien-guides" / state / "index.html"
        if index_file.exists() and index_file.is_file():
            return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="State guide not found")




# Stripe Checkout Session Endpoint
class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str
    email: Optional[str] = None
    referral_id: Optional[str] = None

# SIMPLE TEST VERSION - Uncomment this to test if endpoint works at all:
# @app.post("/api/create-checkout-session")
# async def create_checkout_session(request: Request, checkout_request: CheckoutRequest):
#     return {"test": "endpoint works", "stripe_installed": stripe is not None}

@app.post("/api/create-checkout-session")
async def create_checkout_session(request: Request, checkout_request: CheckoutRequest):
    print("ENDPOINT CALLED", flush=True)
    import sys
    sys.stdout.flush()
    
    print("========== CHECKOUT SESSION ENDPOINT HIT ==========", flush=True)
    
    # Set Stripe API key IMMEDIATELY - must be set before accessing checkout
    import os
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY not set in environment")
    
    # Explicit checks at the very start - before any other code
    if stripe is None:
        raise HTTPException(status_code=500, detail="Stripe module is None - not installed")
    
    if not hasattr(stripe, 'checkout'):
        raise HTTPException(status_code=500, detail=f"Stripe has no checkout attr. Type: {type(stripe)}, Value: {stripe}")
    
    try:
        # Stripe API key is already set above (line 5241) - no need to set again
        
        # Build metadata for Stripe (Tolt uses this to track commissions)
        # Tolt requires the referral ID in metadata to track the 30% commission
        metadata = {}
        if checkout_request.referral_id:
            metadata["tolt_referral"] = checkout_request.referral_id
            print(f"✅ Adding tolt_referral to Stripe metadata: {checkout_request.referral_id}")
        
        # Use standard Stripe API (v8.7.0)
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': checkout_request.price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=checkout_request.success_url,
            cancel_url=checkout_request.cancel_url,
            client_reference_id=checkout_request.email,
            customer_email=checkout_request.email,
            metadata=metadata,
        )
        return {"url": session.url}
    except HTTPException:
        # Re-raise HTTPExceptions (like our configuration errors)
        raise
    except Exception as e:
        # Log full error details including traceback
        print(f"❌ Error creating checkout session: {e}")
        import traceback
        traceback.print_exc()
        # Return proper error response with full details
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "type": type(e).__name__,
                "message": f"Failed to create checkout session: {str(e)}"
            }
        )

@app.get("/api/debug-trigger-reminders")
async def debug_trigger_reminders(background_tasks: BackgroundTasks):
    from api.cron_send_reminders import send_daily_reminders
    background_tasks.add_task(send_daily_reminders)
    return {"status": "success", "message": "Reminders triggered! (Version 2)"}

@app.get("/api/force-test-email")
async def force_test_email(to: str):
    """
    Force send a test email with the REAL reminder template.
    """
    from api.services.email import send_email_sync
    from datetime import date, timedelta
    
    # Dummy data for preview
    project_name = "Test Construction Project"
    client_name = "Acme Builders Inc."
    amount = 15450.00
    state = "Texas"
    deadline_type_display = "Preliminary Notice"
    deadline_date = date.today() + timedelta(days=3)
    formatted_deadline = deadline_date.strftime('%B %d, %Y')
    day_of_week = deadline_date.strftime('%A')
    days_until = 3
    urgency = "🟡 SOON"
    urgency_color = "#f59e0b"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color:#f3f4f6;">
        
        <!-- Main Container -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6; padding:20px 0;">
            <tr>
                <td align="center">
                    
                    <!-- Email Card -->
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:white; border-radius:8px; box-shadow:0 4px 6px rgba(0,0,0,0.1); overflow:hidden;">
                        
                        <!-- Header -->
                        <tr>
                            <td style="background-color:#1e3a8a; padding:30px; text-align:center;">
                                <h1 style="margin:0; color:white; font-size:24px; font-weight:600;">
                                    ⚠️ Lien Deadline Reminder
                                </h1>
                                <p style="margin:10px 0 0 0; color:#e0e7ff; font-size:14px;">
                                    {{urgency}} - {{days_until}} days remaining
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Body -->
                        <tr>
                            <td style="padding:40px 30px;">
                                
                                <!-- Greeting -->
                                <p style="margin:0 0 20px 0; font-size:16px; color:#374151;">
                                    Your <strong>{{deadline_type_display}}</strong> deadline is coming up:
                                </p>
                                
                                <!-- Project Details Box -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f9fafb; border:2px solid #e5e7eb; border-radius:8px; margin-bottom:30px;">
                                    <tr>
                                        <td style="padding:20px;">
                                            <h2 style="margin:0 0 15px 0; font-size:18px; color:#1e3a8a;">
                                                📋 Project Details
                                            </h2>
                                            
                                            <table width="100%" cellpadding="8" cellspacing="0">
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600; width:140px;">Project:</td>
                                                    <td style="color:#111827; font-weight:600;">{{project_name}}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Client:</td>
                                                    <td style="color:#111827;">{{client_name}}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Amount:</td>
                                                    <td style="color:#111827;">${{amount:,.2f}}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">State:</td>
                                                    <td style="color:#111827;">{{state}}</td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                                
                                <!-- Deadline Info Box -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#fef2f2; border:2px solid {{urgency_color}}; border-radius:8px; margin-bottom:30px;">
                                    <tr>
                                        <td style="padding:20px;">
                                            <h2 style="margin:0 0 15px 0; font-size:18px; color:{{urgency_color}};">
                                                ⏰ Deadline Information
                                            </h2>
                                            
                                            <table width="100%" cellpadding="8" cellspacing="0">
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600; width:140px;">Deadline Type:</td>
                                                    <td style="color:#111827; font-weight:600;">{{deadline_type_display}}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Due Date:</td>
                                                    <td style="color:{{urgency_color}}; font-weight:700; font-size:18px;">
                                                        {{formatted_deadline}} ({{day_of_week}})
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Days Left:</td>
                                                    <td style="color:{{urgency_color}}; font-weight:700; font-size:18px;">
                                                        {{days_until}} days
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                                
                                <!-- Notes -->
                                <div style="background-color:#fffbeb; border-left:4px solid #f59e0b; padding:15px; margin-bottom:30px;">
                                    <p style="margin:0; color:#92400e; font-size:14px;">
                                        <strong>📝 Your Notes:</strong><br>
                                        This is a test reminder email to verify the template layout.
                                    </p>
                                </div>
                                
                                <!-- Action Buttons -->
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="padding:20px 0;">
                                            <a href="https://liendeadline.com/dashboard" 
                                               style="display:inline-block; background-color:#f97316; color:white; text-decoration:none; padding:14px 28px; border-radius:6px; font-weight:600; font-size:16px; margin:0 5px;">
                                                View Dashboard
                                            </a>
                                            <a href="#" 
                                               style="display:inline-block; background-color:#3b82f6; color:white; text-decoration:none; padding:14px 28px; border-radius:6px; font-weight:600; font-size:16px; margin:0 5px;">
                                                Download PDF Guide
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color:#f9fafb; padding:20px 30px; border-top:1px solid #e5e7eb;">
                                <p style="margin:0 0 10px 0; font-size:12px; color:#6b7280; text-align:center;">
                                    Questions? Reply to this email or visit 
                                    <a href="https://liendeadline.com/help" style="color:#f97316;">our help center</a>
                                </p>
                                <p style="margin:0; font-size:11px; color:#9ca3af; text-align:center;">
                                    You're receiving this because you set a reminder at LienDeadline.com<br>
                                    <a href="https://liendeadline.com/dashboard" style="color:#9ca3af;">Manage your reminders</a>
                                </p>
                            </td>
                        </tr>
                        
                    </table>
                    
                </td>
            </tr>
        </table>
        
    </body>
    </html>
    """.format(
        urgency=urgency,
        days_until=days_until,
        deadline_type_display=deadline_type_display,
        project_name=project_name,
        client_name=client_name,
        amount=amount,
        state=state,
        urgency_color=urgency_color,
        formatted_deadline=formatted_deadline,
        day_of_week=day_of_week
    )
    
    result = send_email_sync(
        to_email=to,
        subject="[PREVIEW] Lien Deadline Reminder",
        content=html_content,
        is_html=True
    )
    
    if result:
        return {"status": "success", "message": f"Sent real template preview to {to}"}
    else:
        return {"status": "error", "message": "Email function returned False"}



# Log startup
import logging
logger = logging.getLogger("uvicorn")
logger.info("🚀 SERVER RESTART: Patch V2 Applied")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
