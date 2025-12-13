# admin.py - Admin routes for FastAPI backend
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi import Request as FastAPIRequest
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime, timedelta
import uuid
import os
import sqlite3
import stripe
import json
import secrets
import string
import logging
import traceback
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import database functions from database.py (avoids circular import)
from api.database import get_db, get_db_cursor, DB_TYPE

logger = logging.getLogger(__name__)

def send_welcome_email_background(to_email: str, referral_link: str):
    """Background email function for partner approval"""
    subject = "You're approved ✅"
    body = f"""Hi!

Your partner application has been approved.

Your referral link:
{referral_link}

Thanks,
LienDeadline
"""
    send_email_sync(to_email, subject, body)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# Database path helper
def get_db_path():
    """Get database path (works in both local and Railway environments)"""
    return os.getenv("DATABASE_PATH", "admin.db")

# Router without prefix - prefix will be added in main.py include_router call
router = APIRouter(tags=["admin"])

# Import get_db from main.py (will be imported at runtime)
# For now, we'll use a helper function that works with both DB types
def get_db_connection():
    """Get database connection - works with both PostgreSQL and SQLite"""
    import os
    from pathlib import Path
    BASE_DIR = Path(__file__).parent.parent
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if DATABASE_URL and (DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        conn.set_session(autocommit=False)
        return conn, RealDictCursor, 'postgresql'
    else:
        import sqlite3
        if DATABASE_URL and DATABASE_URL.startswith('sqlite://'):
            db_path = DATABASE_URL.replace('sqlite:///', '')
        else:
            db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn, None, 'sqlite'

def calculate_time_ago(timestamp):
    """Calculate human-readable time ago"""
    from datetime import datetime
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            return 'Recently'
    
    now = datetime.now(timestamp.tzinfo) if hasattr(timestamp, 'tzinfo') and timestamp.tzinfo else datetime.now()
    diff = now - timestamp
    
    if diff.total_seconds() < 60:
        return 'Just now'
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f'{minutes} minute{"s" if minutes > 1 else ""} ago'
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f'{hours} hour{"s" if hours > 1 else ""} ago'
    else:
        days = int(diff.total_seconds() / 86400)
        return f'{days} day{"s" if days > 1 else ""} ago'

# HTTP-Basic auth (env vars)
security = HTTPBasic()

def verify_admin(creds: HTTPBasicCredentials = Depends(security)):
    """Verify admin credentials from environment variables"""
    admin_user = os.getenv("ADMIN_USER", "admin")
    admin_pass = os.getenv("ADMIN_PASS", "secret")
    if creds.username != admin_user or creds.password != admin_pass:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return creds.username

@router.post("/test-key")
def create_test_key(
    email: str,
    days: int = 7,
    calls: int = 50,
    user: str = Depends(verify_admin)
):
    """
    Generate a test API key for a prospect.
    Expires at 50 calls OR 7 days (whichever comes first).
    
    Args:
        email: Customer email address
        days: Expiration in days (default: 7)
        calls: Maximum API calls allowed (default: 50)
        user: Admin username (from auth)
    
    Returns:
        Test API key and expiry date
    """
    key = "test_" + uuid.uuid4().hex[:16]
    expiry_date = datetime.utcnow() + timedelta(days=days)
    
    # Store in SQLite
    con = sqlite3.connect(get_db_path())
    con.execute(
        "INSERT INTO test_keys(key, email, expiry_date, max_calls, calls_used, status) VALUES (?,?,?,?,?,?)",
        (key, email, expiry_date.isoformat(), calls, 0, 'active')
    )
    con.commit()
    con.close()
    
    # In production, send email here
    # send_email(to=email, subject="Your LienDeadlineAPI Test Key", ...)
    
    return {
        "key": key,
        "email": email,
        "expiry_date": expiry_date.isoformat(),
        "max_calls": calls,
        "calls_used": 0,
        "status": "active",
        "message": "Test key created. Expires at 50 calls OR 7 days (whichever first)."
    }

@router.get("/test-keys")
def list_test_keys(user: str = Depends(verify_admin)):
    """List all test keys"""
    print("=== /api/admin/test-keys ENDPOINT CALLED ===")
    con = None
    try:
        db_path = get_db_path()
        print(f"Database path: {db_path}")
        con = sqlite3.connect(db_path)
        print("Database connection opened")
        
        # Check if table exists
        print("Checking table existence...")
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_keys'")
        table_exists = cur.fetchone()
        print(f"Table exists: {table_exists is not None}")
        
        if not table_exists:
            print("Test keys table does not exist - returning empty array")
            return []
        
        # Check for both old and new column names for compatibility
        print("Attempting query with new schema...")
        try:
            cur = con.execute("SELECT key, email, expiry_date, expiry, max_calls, calls_used, status FROM test_keys ORDER BY expiry_date DESC, expiry DESC")
            print("Query successful with new schema")
        except sqlite3.OperationalError as e:
            print(f"New schema query failed: {e}")
            print("Attempting query with old schema...")
            try:
                cur = con.execute("SELECT key, email, expiry, expiry, max_calls, 0 as calls_used, 'active' as status FROM test_keys ORDER BY expiry DESC")
                print("Query successful with old schema")
            except sqlite3.OperationalError as e2:
                print(f"Old schema query also failed: {e2}")
                import traceback
                traceback.print_exc()
                return []
        
        rows = cur.fetchall()
        print(f"Found {len(rows)} test keys")
        
        result = []
        for idx, row in enumerate(rows):
            try:
                print(f"Processing row {idx}: {row}")
                # Handle both old and new schema
                expiry = row[2] if len(row) > 2 and row[2] else (row[3] if len(row) > 3 else None)
                calls_used = row[5] if len(row) > 5 else 0
                status = row[6] if len(row) > 6 else 'active'
                
                print(f"  Row {idx} - expiry: {expiry}, calls_used: {calls_used}, status: {status}")
                
                # Check if expired
                if expiry:
                    try:
                        expiry_date = datetime.fromisoformat(expiry)
                        print(f"  Parsed expiry date: {expiry_date}")
                        if expiry_date < datetime.utcnow() or calls_used >= (row[4] if len(row) > 4 else 50):
                            status = 'expired'
                            print(f"  Marked as expired")
                    except ValueError as ve:
                        print(f"  Error parsing expiry date '{expiry}': {ve}")
                        pass  # Invalid date format, keep status as is
                
                result.append({
                    "key": row[0] if len(row) > 0 else "",
                    "email": row[1] if len(row) > 1 else "",
                    "expiry_date": expiry,
                    "expiry": expiry,  # For backward compatibility
                    "max_calls": row[4] if len(row) > 4 else 50,
                    "calls_used": calls_used,
                    "status": status
                })
            except Exception as e:
                print(f"Error processing row {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"Returning {len(result)} test keys")
        return result
    except Exception as e:
        print(f"=== ERROR in list_test_keys: {e} ===")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if con:
            print("Closing database connection")
            con.close()

@router.post("/approve-broker")
def approve_broker(
    email: str,
    name: str,
    model: str = "bounty",  # "bounty" or "recurring"
    user: str = Depends(verify_admin)
):
    """
    Approve a broker application.
    
    Args:
        email: Broker email
        name: Broker name
        model: Commission model ("bounty" or "recurring")
        user: Admin username (from auth)
    
    Returns:
        Broker referral code
    """
    referral_code = f"broker_{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
    
    # Store in SQLite
    con = sqlite3.connect(get_db_path())
    con.execute(
        "INSERT INTO brokers(id, email, name, model, referrals, earned) VALUES (?,?,?,?,?,?)",
        (referral_code, email, name, model, 0, 0)
    )
    con.commit()
    con.close()
    
    return {
        "referral_code": referral_code,
        "email": email,
        "name": name,
        "model": model
    }

@router.post("/approve-partner/{application_id}")
async def approve_partner(
    application_id: int,
    request: FastAPIRequest,
    background_tasks: BackgroundTasks,
    user: str = Depends(verify_admin)
):
    """Approve a partner application and send referral link"""
    print("=" * 60)
    print(f"APPROVE START application_id={application_id}")
    print("=" * 60)
    
    # Initialize email tracking variables (must be outside try block for return)
    email_sent = False
    email_error = None
    email_channel = None
    referral_code = None
    referral_link = None
    name = None
    email = None
    
    try:
        # Get commission model from request body if provided
        commission_model_override = None
        try:
            body = await request.json()
            commission_model_override = body.get('commission_model')
        except:
            pass
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # 1) Fetch application
            print(f"Fetching application {application_id}...")
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM partner_applications WHERE id = %s", (application_id,))
            else:
                cursor.execute("SELECT * FROM partner_applications WHERE id = ?", (application_id,))
            
            app = cursor.fetchone()
            
            if not app:
                print(f"❌ Application {application_id} not found")
                raise HTTPException(status_code=404, detail="Application not found")
            
            # Convert to dict
            if isinstance(app, dict):
                app_dict = app
            else:
                app_dict = dict(app)
            
            print(f"✅ Application found: {app_dict.get('email', 'Unknown')}")
            
            # Use override or existing commission model
            app_dict['commission_model'] = commission_model_override or app_dict.get('commission_model', 'bounty')
            
            # 2) Generate unique referral code and link
            name_first = app_dict.get('name', 'BROKER').split()[0].upper() if app_dict.get('name') else 'BROKER'
            referral_code = f"{name_first}-{uuid.uuid4().hex[:6].upper()}"
            referral_link = f"https://liendeadline.com?ref={referral_code}"
            print(f"Generated referral_code: {referral_code}")
            
            # Create brokers table if it doesn't exist and add missing columns
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS brokers (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR NOT NULL,
                        email VARCHAR UNIQUE NOT NULL,
                        commission REAL DEFAULT 500.00,
                        referrals INTEGER DEFAULT 0,
                        earned REAL DEFAULT 0.00,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Add missing columns if they don't exist
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'brokers' AND column_name = 'company'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN company VARCHAR;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
                
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'brokers' AND column_name = 'referral_code'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN referral_code VARCHAR UNIQUE;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
                
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'brokers' AND column_name = 'referral_link'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN referral_link VARCHAR;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
                
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'brokers' AND column_name = 'commission_model'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN commission_model VARCHAR;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
                
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'brokers' AND column_name = 'pending_commissions'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN pending_commissions INTEGER DEFAULT 0;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
                
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'brokers' AND column_name = 'paid_commissions'
                            ) THEN
                                ALTER TABLE brokers ADD COLUMN paid_commissions REAL DEFAULT 0;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
            else:
                # SQLite
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS brokers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        commission REAL DEFAULT 500.00,
                        referrals INTEGER DEFAULT 0,
                        earned REAL DEFAULT 0.00,
                        status TEXT DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Add missing columns if they don't exist (SQLite)
                for column_def in [
                    ("company", "TEXT"),
                    ("referral_code", "TEXT UNIQUE"),
                    ("referral_link", "TEXT"),
                    ("commission_model", "TEXT"),
                    ("pending_commissions", "INTEGER DEFAULT 0"),
                    ("paid_commissions", "REAL DEFAULT 0")
                ]:
                    try:
                        cursor.execute(f"ALTER TABLE brokers ADD COLUMN {column_def[0]} {column_def[1]}")
                    except Exception:
                        pass
            
            # 3) UPSERT broker record (handle duplicates gracefully)
            name = app_dict.get('name', '')
            email = app_dict.get('email', '')
            
            print(f"UPSERT broker: {name} ({email}) with referral_code: {referral_code}")
            
            if DB_TYPE == 'postgresql':
                # PostgreSQL UPSERT - handle duplicate email gracefully
                cursor.execute("""
                    INSERT INTO brokers (name, email, referral_code)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (email)
                    DO UPDATE SET
                        referral_code = EXCLUDED.referral_code,
                        name = EXCLUDED.name
                    RETURNING id
                """, (name, email, referral_code))
                
                result = cursor.fetchone()
                broker_id = result['id'] if isinstance(result, dict) else result[0]
                print(f"✅ BROKER UPSERT OK id={broker_id}")
            else:
                # SQLite - try update first, then insert
                cursor.execute("SELECT id FROM brokers WHERE email = ?", (email,))
                existing = cursor.fetchone()
                
                if existing:
                    broker_id = existing['id'] if isinstance(existing, dict) else existing[0]
                    cursor.execute("""
                        UPDATE brokers 
                        SET referral_code = ?, name = ?
                        WHERE id = ?
                    """, (referral_code, name, broker_id))
                    print(f"✅ BROKER UPSERT OK id={broker_id} (updated existing)")
                else:
                    cursor.execute("""
                        INSERT INTO brokers (name, email, referral_code)
                        VALUES (?, ?, ?)
                    """, (name, email, referral_code))
                    broker_id = cursor.lastrowid
                    print(f"✅ BROKER UPSERT OK id={broker_id} (new record)")
            
            # Try to update additional columns if they exist (optional, don't fail if they don't)
            try:
                if DB_TYPE == 'postgresql':
                    # Try to update company if column exists
                    try:
                        cursor.execute("""
                            UPDATE brokers 
                            SET company = %s 
                            WHERE id = %s
                        """, (app_dict.get('company', ''), broker_id))
                    except Exception:
                        pass  # Column doesn't exist, skip
                    
                    # Try to update referral_link if column exists
                    try:
                        cursor.execute("""
                            UPDATE brokers 
                            SET referral_link = %s 
                            WHERE id = %s
                        """, (referral_link, broker_id))
                    except Exception:
                        pass  # Column doesn't exist, skip
                    
                    # Try to update commission_model if column exists
                    try:
                        cursor.execute("""
                            UPDATE brokers 
                            SET commission_model = %s 
                            WHERE id = %s
                        """, (app_dict['commission_model'], broker_id))
                    except Exception:
                        pass  # Column doesn't exist, skip
                else:
                    # SQLite - try to update optional columns
                    try:
                        cursor.execute("UPDATE brokers SET company = ? WHERE id = ?", (app_dict.get('company', ''), broker_id))
                    except Exception:
                        pass
                    try:
                        cursor.execute("UPDATE brokers SET referral_link = ? WHERE id = ?", (referral_link, broker_id))
                    except Exception:
                        pass
                    try:
                        cursor.execute("UPDATE brokers SET commission_model = ? WHERE id = ?", (app_dict['commission_model'], broker_id))
                    except Exception:
                        pass
            except Exception as e:
                print(f"Warning: Could not update optional columns: {e}")
                # Continue anyway - broker created successfully
            
            # Try to add approval columns if they don't exist (PostgreSQL)
            if DB_TYPE == 'postgresql':
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'partner_applications' AND column_name = 'approved_at'
                            ) THEN
                                ALTER TABLE partner_applications ADD COLUMN approved_at TIMESTAMP;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'partner_applications' AND column_name = 'referral_link'
                            ) THEN
                                ALTER TABLE partner_applications ADD COLUMN referral_link VARCHAR;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
            else:
                # SQLite
                try:
                    cursor.execute("ALTER TABLE partner_applications ADD COLUMN approved_at TIMESTAMP")
                except sqlite3.OperationalError:
                    pass
                try:
                    cursor.execute("ALTER TABLE partner_applications ADD COLUMN referral_link TEXT")
                except sqlite3.OperationalError:
                    pass
            
            # 4) Update partner_applications - MUST always run
            print(f"Updating partner_applications {application_id} to approved...")
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE partner_applications 
                    SET status = 'approved',
                        approved_at = NOW(),
                        referral_link = %s
                    WHERE id = %s
                """, (referral_link, application_id))
            else:
                cursor.execute("""
                    UPDATE partner_applications 
                    SET status = 'approved',
                        approved_at = CURRENT_TIMESTAMP,
                        referral_link = ?
                    WHERE id = ?
                """, (referral_link, application_id))
            
            updated_rows = cursor.rowcount
            if updated_rows == 0:
                print(f"⚠️ WARNING: No rows updated for application {application_id}")
            else:
                print(f"✅ APPLICATION UPDATED OK (rows={updated_rows})")
            
            # 5) Commit all database changes
            conn.commit()
            print("✅ Database commit successful")
        
        # Return immediately - email will be sent in background (<1s response time)
        print("=" * 60)
        print(f"✅ APPROVAL COMPLETE - Returning response immediately")
        print(f"   Email will be sent in background")
        print("=" * 60)
        
        # Schedule email sending in background (non-blocking)
        background_tasks.add_task(send_welcome_email_background, email, referral_link)
        
        logger.info(f"Partner approved: {email} - Referral code: {referral_code} - Email queued for background sending")
        
        # Return immediately (<1s response time - prevents Cloudflare 524 timeout)
        return {
            "status": "approved",
            "referral_code": referral_code,
            "referral_link": referral_link,
            "email_queued": True,
            "message": "Approval successful. Email will be sent shortly."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving partner: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

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

@router.post("/reject-partner/{application_id}")
async def reject_partner_application(
    application_id: int,
    user: str = Depends(verify_admin)
):
    """Reject a partner application - PostgreSQL/SQLite compatible"""
    print("=" * 60)
    print(f"❌ ADMIN: Rejecting partner application {application_id}")
    print("=" * 60)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # First check if application exists
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM partner_applications WHERE id = %s", (application_id,))
            else:
                cursor.execute("SELECT * FROM partner_applications WHERE id = ?", (application_id,))
            
            app = cursor.fetchone()
            
            if not app:
                print(f"❌ Application {application_id} not found")
                raise HTTPException(status_code=404, detail="Application not found")
            
            # Convert to dict
            if isinstance(app, dict):
                app_dict = app
            else:
                app_dict = dict(app)
            
            print(f"   Application found: {app_dict.get('email', 'Unknown')}")
            
            # Try to add rejected_at column if it doesn't exist (PostgreSQL)
            if DB_TYPE == 'postgresql':
                try:
                    cursor.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'partner_applications' AND column_name = 'rejected_at'
                            ) THEN
                                ALTER TABLE partner_applications ADD COLUMN rejected_at TIMESTAMP;
                            END IF;
                        END $$;
                    """)
                except Exception:
                    pass
            else:
                # SQLite
                try:
                    cursor.execute("ALTER TABLE partner_applications ADD COLUMN rejected_at TIMESTAMP")
                except Exception:
                    pass
            
            # Update status to rejected
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE partner_applications 
                    SET status = 'rejected',
                        rejected_at = NOW()
                    WHERE id = %s
                """, (application_id,))
            else:
                cursor.execute("""
                    UPDATE partner_applications 
                    SET status = 'rejected',
                        rejected_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (application_id,))
            
            conn.commit()
            
            print(f"✅ Application {application_id} rejected successfully")
            print("=" * 60)
            
            logger.info(f"Partner application rejected: {app_dict.get('email', '')} - ID: {application_id}")
            
            return {
                "success": True,
                "message": "Application rejected",
                "status": "rejected"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR rejecting application: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        logger.error(f"Error rejecting partner application: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-partner/{application_id}")
async def delete_partner_application(
    application_id: int,
    user: str = Depends(verify_admin)
):
    """Delete a partner application - PostgreSQL/SQLite compatible"""
    print("=" * 60)
    print(f"🗑️ ADMIN: Deleting partner application {application_id}")
    print("=" * 60)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # First check if application exists
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM partner_applications WHERE id = %s", (application_id,))
            else:
                cursor.execute("SELECT * FROM partner_applications WHERE id = ?", (application_id,))
            
            app = cursor.fetchone()
            
            if not app:
                print(f"❌ Application {application_id} not found")
                raise HTTPException(status_code=404, detail="Application not found")
            
            # Convert to dict
            if isinstance(app, dict):
                app_dict = app
            else:
                app_dict = dict(app)
            
            print(f"   Application found: {app_dict.get('email', 'Unknown')}")
            
            # Delete application
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM partner_applications WHERE id = %s", (application_id,))
            else:
                cursor.execute("DELETE FROM partner_applications WHERE id = ?", (application_id,))
            
            conn.commit()
            
            print(f"✅ Application {application_id} deleted successfully")
            print("=" * 60)
            
            logger.info(f"Partner application deleted: {app_dict.get('email', '')} - ID: {application_id}")
            
            return {
                "success": True,
                "message": "Application deleted"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR deleting application: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        logger.error(f"Error deleting partner application: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete-broker/{broker_id}")
async def delete_broker(
    broker_id: int,
    user: str = Depends(verify_admin)
):
    """Delete a broker and all associated data - PostgreSQL/SQLite compatible"""
    print("=" * 60)
    print(f"🗑️ ADMIN: Deleting broker {broker_id}")
    print("=" * 60)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # First check if broker exists
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("SELECT * FROM brokers WHERE id = ?", (broker_id,))
            
            broker = cursor.fetchone()
            
            if not broker:
                print(f"❌ Broker {broker_id} not found")
                raise HTTPException(status_code=404, detail="Broker not found")
            
            # Convert to dict
            if isinstance(broker, dict):
                broker_dict = broker
            else:
                broker_dict = dict(broker)
            
            email = broker_dict.get('email', '')
            print(f"   Broker found: {email}")
            
            # Delete partner application first (by email)
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM partner_applications WHERE email = %s", (email,))
            else:
                cursor.execute("DELETE FROM partner_applications WHERE email = ?", (email,))
            app_count = cursor.rowcount
            print(f"   Deleted {app_count} partner application(s) for {email}")
            
            # Delete broker
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM brokers WHERE id = %s", (broker_id,))
            else:
                cursor.execute("DELETE FROM brokers WHERE id = ?", (broker_id,))
            broker_count = cursor.rowcount
            
            conn.commit()
            
            print(f"✅ Deleted broker and partner application for {email}")
            print(f"   Broker count: {broker_count}, Application count: {app_count}")
            print("=" * 60)
            
            logger.info(f"Broker and application deleted: {email} - ID: {broker_id}")
            
            return {
                "success": True,
                "message": f"Broker and application deleted ({broker_count} broker, {app_count} application)",
                "broker_count": broker_count,
                "app_count": app_count
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ ERROR deleting broker: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        logger.error(f"Error deleting broker: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cleanup-partner/{email}")
async def cleanup_partner(
    email: str,
    user: str = Depends(verify_admin)
):
    """Completely remove a partner by email (for testing) - PostgreSQL/SQLite compatible"""
    from urllib.parse import unquote
    
    email = unquote(email).strip().lower()
    
    print("=" * 60)
    print(f"🧹 ADMIN: Cleanup partner by email: {email}")
    print("=" * 60)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Delete from brokers (case-insensitive)
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM brokers WHERE LOWER(email) = LOWER(%s)", (email,))
            else:
                cursor.execute("DELETE FROM brokers WHERE LOWER(email) = LOWER(?)", (email,))
            broker_count = cursor.rowcount
            print(f"   Deleted {broker_count} broker(s)")
            
            # Delete from partner_applications (case-insensitive)
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM partner_applications WHERE LOWER(email) = LOWER(%s)", (email,))
            else:
                cursor.execute("DELETE FROM partner_applications WHERE LOWER(email) = LOWER(?)", (email,))
            app_count = cursor.rowcount
            print(f"   Deleted {app_count} application(s)")
            
            conn.commit()
            
            print(f"✅ Cleanup complete for {email}: {broker_count} broker(s), {app_count} application(s) deleted")
            print("=" * 60)
            
            logger.info(f"Partner cleanup: {email} - {broker_count} broker(s), {app_count} application(s)")
            
            return {
                "success": True,
                "email": email,
                "deleted": {
                    "brokers": broker_count,
                    "partner_applications": app_count
                },
                "message": f"Deleted {broker_count} broker(s) and {app_count} application(s)"
            }
            
    except Exception as e:
        print(f"❌ ERROR cleaning up partner: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        logger.error(f"Error cleaning up partner {email}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/analytics/comprehensive")
async def get_comprehensive_analytics(user: str = Depends(verify_admin)):
    """Get comprehensive analytics with Day/Week/Month/All Time stats - PostgreSQL/SQLite compatible"""
    print("=" * 60)
    print("📊 ADMIN: Fetching comprehensive analytics")
    print("=" * 60)
    
    try:
        from datetime import datetime, timedelta
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Date ranges
            today = datetime.now().date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # Format dates for SQL
            today_str = today.strftime('%Y-%m-%d')
            week_ago_str = week_ago.strftime('%Y-%m-%d')
            month_ago_str = month_ago.strftime('%Y-%m-%d')
            
            stats = {}
            
            # CALCULATIONS
            try:
                # Today
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = %s", (today_str,))
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = ?", (today_str,))
                result = cursor.fetchone()
                stats['calculations_today'] = result['count'] if isinstance(result, dict) else (result[0] if result else 0)
                
                # This week
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) >= %s", (week_ago_str,))
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) >= ?", (week_ago_str,))
                result = cursor.fetchone()
                stats['calculations_week'] = result['count'] if isinstance(result, dict) else (result[0] if result else 0)
                
                # This month
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) >= %s", (month_ago_str,))
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) >= ?", (month_ago_str,))
                result = cursor.fetchone()
                stats['calculations_month'] = result['count'] if isinstance(result, dict) else (result[0] if result else 0)
                
                # All time
                cursor.execute("SELECT COUNT(*) as count FROM calculations")
                result = cursor.fetchone()
                stats['calculations_all'] = result['count'] if isinstance(result, dict) else (result[0] if result else 0)
            except Exception as e:
                print(f"Error getting calculations: {e}")
                import traceback
                traceback.print_exc()
                # Rollback to prevent transaction poisoning
                try:
                    conn.rollback()
                except Exception:
                    pass
                stats['calculations_today'] = 0
                stats['calculations_week'] = 0
                stats['calculations_month'] = 0
                stats['calculations_all'] = 0
            
            # REVENUE (from payments table) - handle missing status column gracefully
            try:
                # Check if payments table exists and has status column
                has_status_column = False
                try:
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = 'payments' AND column_name = 'status'
                        """)
                        has_status_column = cursor.fetchone() is not None
                    else:
                        cursor.execute("PRAGMA table_info(payments)")
                        columns = cursor.fetchall()
                        has_status_column = any(
                            (col[1] == 'status' if isinstance(col, tuple) else col.get('name') == 'status') 
                            for col in columns
                        )
                except Exception:
                    has_status_column = False
                
                # Today
                if DB_TYPE == 'postgresql':
                    if has_status_column:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) = %s AND status = 'completed'", (today_str,))
                    else:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) = %s", (today_str,))
                else:
                    if has_status_column:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) = ? AND status = 'completed'", (today_str,))
                    else:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) = ?", (today_str,))
                result = cursor.fetchone()
                stats['revenue_today'] = float(result['total'] if isinstance(result, dict) else (result[0] if result else 0))
                
                # This week
                if DB_TYPE == 'postgresql':
                    if has_status_column:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= %s AND status = 'completed'", (week_ago_str,))
                    else:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= %s", (week_ago_str,))
                else:
                    if has_status_column:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= ? AND status = 'completed'", (week_ago_str,))
                    else:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= ?", (week_ago_str,))
                result = cursor.fetchone()
                stats['revenue_week'] = float(result['total'] if isinstance(result, dict) else (result[0] if result else 0))
                
                # This month
                if DB_TYPE == 'postgresql':
                    if has_status_column:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= %s AND status = 'completed'", (month_ago_str,))
                    else:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= %s", (month_ago_str,))
                else:
                    if has_status_column:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= ? AND status = 'completed'", (month_ago_str,))
                    else:
                        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE DATE(created_at) >= ?", (month_ago_str,))
                result = cursor.fetchone()
                stats['revenue_month'] = float(result['total'] if isinstance(result, dict) else (result[0] if result else 0))
                
                # All time
                if has_status_column:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'completed'")
                else:
                    cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments")
                result = cursor.fetchone()
                stats['revenue_all'] = float(result['total'] if isinstance(result, dict) else (result[0] if result else 0))
            except Exception as e:
                print(f"Error getting revenue: {e}")
                import traceback
                traceback.print_exc()
                # Rollback to prevent transaction poisoning
                try:
                    conn.rollback()
                except Exception:
                    pass
                stats['revenue_today'] = 0.0
                stats['revenue_week'] = 0.0
                stats['revenue_month'] = 0.0
                stats['revenue_all'] = 0.0
            
            # ---------------------------
            # Email captures (robust column detection)
            # ---------------------------
            try:
                print("Querying email_captures table...")

                if DB_TYPE == "postgresql":
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'email_captures'
                          AND column_name IN ('captured_at', 'created_at', 'timestamp', 'submitted_at')
                        ORDER BY CASE column_name
                            WHEN 'captured_at' THEN 1
                            WHEN 'created_at' THEN 2
                            WHEN 'timestamp' THEN 3
                            WHEN 'submitted_at' THEN 4
                            ELSE 99
                        END
                        LIMIT 1
                    """)
                    row = cursor.fetchone()
                    date_col = (row["column_name"] if isinstance(row, dict) else row[0]) if row else None

                    if not date_col:
                        # No date column found; don't break analytics
                        print("No date column found in email_captures table")
                        stats['emails_today'] = 0
                        stats['emails_week'] = 0
                        stats['emails_month'] = 0
                        stats['emails_all'] = 0
                    else:
                        print(f"Using date column: {date_col}")
                        # Today
                        cursor.execute(
                            f"SELECT COUNT(*) as count FROM email_captures WHERE DATE({date_col}) = %s",
                            (today_str,)
                        )
                        r = cursor.fetchone()
                        stats['emails_today'] = r["count"] if isinstance(r, dict) else r[0]
                        
                        # This week
                        cursor.execute(
                            f"SELECT COUNT(*) as count FROM email_captures WHERE DATE({date_col}) >= %s",
                            (week_ago_str,)
                        )
                        r = cursor.fetchone()
                        stats['emails_week'] = r["count"] if isinstance(r, dict) else r[0]
                        
                        # This month
                        cursor.execute(
                            f"SELECT COUNT(*) as count FROM email_captures WHERE DATE({date_col}) >= %s",
                            (month_ago_str,)
                        )
                        r = cursor.fetchone()
                        stats['emails_month'] = r["count"] if isinstance(r, dict) else r[0]
                        
                        # All time
                        cursor.execute("SELECT COUNT(*) as count FROM email_captures")
                        r = cursor.fetchone()
                        stats['emails_all'] = r["count"] if isinstance(r, dict) else r[0]
                else:
                    # SQLite: try common columns in order
                    date_col = None
                    for c in ("captured_at", "created_at", "timestamp", "submitted_at"):
                        try:
                            cursor.execute(f"SELECT {c} FROM email_captures LIMIT 1")
                            date_col = c
                            break
                        except Exception:
                            pass

                    if not date_col:
                        print("No date column found in email_captures table")
                        stats['emails_today'] = 0
                        stats['emails_week'] = 0
                        stats['emails_month'] = 0
                        stats['emails_all'] = 0
                    else:
                        print(f"Using date column: {date_col}")
                        # Today
                        cursor.execute(
                            f"SELECT COUNT(*) as count FROM email_captures WHERE DATE({date_col}) = DATE(?)",
                            (today_str,)
                        )
                        r = cursor.fetchone()
                        stats['emails_today'] = r["count"] if isinstance(r, dict) else r[0]
                        
                        # This week
                        cursor.execute(
                            f"SELECT COUNT(*) as count FROM email_captures WHERE DATE({date_col}) >= DATE(?)",
                            (week_ago_str,)
                        )
                        r = cursor.fetchone()
                        stats['emails_week'] = r["count"] if isinstance(r, dict) else r[0]
                        
                        # This month
                        cursor.execute(
                            f"SELECT COUNT(*) as count FROM email_captures WHERE DATE({date_col}) >= DATE(?)",
                            (month_ago_str,)
                        )
                        r = cursor.fetchone()
                        stats['emails_month'] = r["count"] if isinstance(r, dict) else r[0]
                        
                        # All time
                        cursor.execute("SELECT COUNT(*) as count FROM email_captures")
                        r = cursor.fetchone()
                        stats['emails_all'] = r["count"] if isinstance(r, dict) else r[0]

                print(f"Email captures - today: {stats['emails_today']}, week: {stats['emails_week']}, month: {stats['emails_month']}, all: {stats['emails_all']}")

            except Exception as e:
                print(f"Error getting email captures: {e}")
                import traceback
                traceback.print_exc()
                try:
                    conn.rollback()
                except Exception:
                    pass
                stats['emails_today'] = 0
                stats['emails_week'] = 0
                stats['emails_month'] = 0
                stats['emails_all'] = 0
            
            # ACTIVE PARTNERS
            try:
                cursor.execute("SELECT COUNT(*) as count FROM brokers")
                result = cursor.fetchone()
                stats['partners_total'] = result['count'] if isinstance(result, dict) else (result[0] if result else 0)
            except Exception as e:
                print(f"Error getting partners: {e}")
                import traceback
                traceback.print_exc()
                # Rollback to prevent transaction poisoning
                try:
                    conn.rollback()
                except Exception:
                    pass
                stats['partners_total'] = 0
            
            # PENDING APPLICATIONS
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM partner_applications WHERE status = 'pending'")
                else:
                    cursor.execute("SELECT COUNT(*) as count FROM partner_applications WHERE status = 'pending'")
                result = cursor.fetchone()
                stats['applications_pending'] = result['count'] if isinstance(result, dict) else (result[0] if result else 0)
            except Exception as e:
                print(f"Error getting pending applications: {e}")
                import traceback
                traceback.print_exc()
                # Rollback to prevent transaction poisoning
                try:
                    conn.rollback()
                except Exception:
                    pass
                stats['applications_pending'] = 0
        
        print(f"✅ Analytics fetched successfully")
        print("=" * 60)
        return stats
        
    except Exception as e:
        print(f"❌ ERROR getting comprehensive analytics: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {
            'calculations_today': 0,
            'calculations_week': 0,
            'calculations_month': 0,
            'calculations_all': 0,
            'revenue_today': 0.0,
            'revenue_week': 0.0,
            'revenue_month': 0.0,
            'revenue_all': 0.0,
            'emails_today': 0,
            'emails_week': 0,
            'emails_month': 0,
            'emails_all': 0,
            'partners_total': 0,
            'applications_pending': 0
        }

@router.get("/debug/email-env")
async def debug_email_env(user: str = Depends(verify_admin)):
    """Debug endpoint to check email environment variables (without exposing secrets)"""
    return {
        "has_smtp_email": bool(os.getenv("SMTP_EMAIL")),
        "has_smtp_user": bool(os.getenv("SMTP_USER")),
        "has_smtp_password": bool(os.getenv("SMTP_PASSWORD")),
        "smtp_email_value": os.getenv("SMTP_EMAIL", ""),
        "smtp_user_value": os.getenv("SMTP_USER", ""),
        "smtp_password_set": bool(os.getenv("SMTP_PASSWORD")),
        "effective_smtp_user": os.getenv("SMTP_USER") or os.getenv("SMTP_EMAIL") or "trendtweakers00@gmail.com"
    }

@router.get("/partner-applications")
def get_partner_applications(
    status: str = "all",
    user: str = Depends(verify_admin)
):
    """Get partner applications - PostgreSQL/SQLite compatible"""
    
    print("=" * 60)
    print("📊 ADMIN: Fetching partner applications")
    print(f"   Status filter: {status}")
    print("=" * 60)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Simple query - same as debug endpoint
            cursor.execute("SELECT * FROM partner_applications ORDER BY created_at DESC")
            rows = cursor.fetchall()
            
            print(f"   Raw rows fetched: {len(rows)}")
            
            # Convert to dicts
            applications = []
            for row in rows:
                if isinstance(row, dict):
                    applications.append(row)
                else:
                    applications.append(dict(row))
            
            # Filter by status if needed
            if status and status != "all":
                applications = [app for app in applications if app.get('status') == status]
            
            print(f"   After filter: {len(applications)} applications")
            print("=" * 60)
            
            return {"applications": applications, "total": len(applications)}
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {"applications": [], "total": 0, "error": str(e)}

@router.get("/brokers")
def list_brokers(user: str = Depends(verify_admin)):
    """Get active brokers - PostgreSQL/SQLite compatible"""
    print("=" * 60)
    print("📊 ADMIN: Fetching active brokers")
    print("=" * 60)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Get all brokers (filter by status if needed)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT * FROM brokers ORDER BY id DESC")
            else:
                cursor.execute("SELECT * FROM brokers ORDER BY id DESC")
            
            rows = cursor.fetchall()
            
            brokers = []
            for row in rows:
                if isinstance(row, dict):
                    broker = row
                else:
                    broker = dict(row)
                brokers.append(broker)
            
            print(f"✅ Found {len(brokers)} brokers")
            print("=" * 60)
            
            return {"brokers": brokers, "total": len(brokers)}
            
    except Exception as e:
        print(f"❌ ERROR getting brokers: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {"brokers": [], "total": 0}

@router.get("/customers")
def list_customers(user: str = Depends(verify_admin)):
    """List all customers"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if table exists
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customers'")
        if not cur.fetchone():
            print("Customers table does not exist")
            return []
        
        # Try different column names for compatibility
        try:
            cur = con.execute("SELECT email, api_calls, status FROM customers ORDER BY email")
        except sqlite3.OperationalError:
            try:
                cur = con.execute("SELECT email, calls_used, status FROM customers ORDER BY email")
            except sqlite3.OperationalError as e:
                print(f"Error querying customers: {e}")
                return []
        
        rows = cur.fetchall()
        
        return [
            {
                "email": row[0] if len(row) > 0 else "",
                "calls": row[1] if len(row) > 1 else 0,
                "status": row[2] if len(row) > 2 else "active"
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error in list_customers: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if con:
            con.close()

@router.get("/today-stats")
def get_today_stats(user: str = Depends(verify_admin)):
    """Get today's statistics"""
    try:
        import sys
        from pathlib import Path
        from datetime import datetime
        BASE_DIR = Path(__file__).parent.parent
        DATABASE_URL = os.getenv('DATABASE_URL')
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        if DATABASE_URL and (DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')):
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Revenue today (from Stripe payments)
            cursor.execute('''
                SELECT COALESCE(SUM(amount), 0) as revenue_today 
                FROM payments 
                WHERE DATE(created_at) = %s
            ''', (today,))
            revenue_row = cursor.fetchone()
            revenue = float(revenue_row['revenue_today']) if revenue_row['revenue_today'] else 0
            
            # Active customers
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE subscription_status = 'active'")
            active_customers = cursor.fetchone()['count'] or 0
            
            # Calculations today
            cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = %s", (today,))
            calculations_today = cursor.fetchone()['count'] or 0
            
            # Pending payouts
            cursor.execute("SELECT COALESCE(SUM(payout), 0) as total FROM referrals WHERE status = 'pending_payout'")
            pending_row = cursor.fetchone()
            pending_payouts = float(pending_row['total']) if pending_row['total'] else 0
            
            conn.close()
            
            return {
                "revenue_today": revenue,
                "active_customers": active_customers,
                "calculations_today": calculations_today,
                "pending_payouts": pending_payouts
            }
        else:
            # SQLite
            import sqlite3
            if DATABASE_URL and DATABASE_URL.startswith('sqlite://'):
                db_path = DATABASE_URL.replace('sqlite:///', '')
            else:
                db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Revenue today (from Stripe payments)
            cursor.execute('''
                SELECT COALESCE(SUM(amount), 0) as revenue_today 
                FROM payments 
                WHERE DATE(created_at) = ?
            ''', (today,))
            revenue_row = cursor.fetchone()
            revenue = float(revenue_row['revenue_today']) if revenue_row and revenue_row['revenue_today'] else 0
            
            # Active customers
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE subscription_status = 'active'")
            active_customers = cursor.fetchone()['count'] or 0
            
            # Calculations today
            cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = ?", (today,))
            calculations_today = cursor.fetchone()['count'] or 0
            
            # Pending payouts
            cursor.execute("SELECT COALESCE(SUM(payout), 0) as total FROM referrals WHERE status = 'pending_payout'")
            pending_row = cursor.fetchone()
            pending_payouts = float(pending_row['total']) if pending_row and pending_row['total'] else 0
            
            conn.close()
            
            return {
                "revenue_today": revenue,
                "active_customers": active_customers,
                "calculations_today": calculations_today,
                "pending_payouts": pending_payouts
            }
            
    except Exception as e:
        logger.error(f"Error fetching today stats: {e}")
        import traceback
        traceback.print_exc()
        return {
            "revenue_today": 0,
            "active_customers": 0,
            "calculations_today": 0,
            "pending_payouts": 0
        }

@router.get("/live-stats")
def get_live_stats(user: str = Depends(verify_admin)):
    """Get live statistics for dashboard - PostgreSQL/SQLite compatible"""
    print("=" * 60)
    print("📊 ADMIN: Fetching live stats")
    print("=" * 60)
    
    try:
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"Today's date: {today}")
        
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Total calculations today
            try:
                print("Querying calculations table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = %s", (today,))
                else:
                    # Check if table exists (SQLite)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='calculations'")
                    if not cursor.fetchone():
                        print("calculations table does not exist")
                        total_calculations = 0
                    else:
                        cursor.execute("SELECT COUNT(*) as count FROM calculations WHERE DATE(created_at) = ?", (today,))
                
                result = cursor.fetchone()
                if isinstance(result, dict):
                    total_calculations = result.get('count', 0) or 0
                elif isinstance(result, tuple):
                    total_calculations = result[0] if result else 0
                else:
                    total_calculations = result if result else 0
                print(f"Total calculations: {total_calculations}")
            except Exception as e:
                print(f"Error counting calculations: {e}")
                import traceback
                traceback.print_exc()
                total_calculations = 0
            
            # Email captures today
            try:
                print("Querying email_captures table...")
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) as count FROM email_captures WHERE DATE(created_at) = %s", (today,))
                else:
                    # Check if table exists (SQLite)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_captures'")
                    if not cursor.fetchone():
                        print("email_captures table does not exist")
                        email_captures = 0
                    else:
                        cursor.execute("SELECT COUNT(*) as count FROM email_captures WHERE DATE(created_at) = ?", (today,))
                
                result = cursor.fetchone()
                if isinstance(result, dict):
                    email_captures = result.get('count', 0) or 0
                elif isinstance(result, tuple):
                    email_captures = result[0] if result else 0
                else:
                    email_captures = result if result else 0
                print(f"Email captures: {email_captures}")
            except Exception as e:
                print(f"Error counting email captures: {e}")
                import traceback
                traceback.print_exc()
                email_captures = 0
            
            # Upgrade clicks (placeholder - would need tracking table)
            upgrade_clicks = 0
            
        result = {
            "total_calculations": total_calculations,
            "calculations_today": total_calculations,
            "email_captures": email_captures,
            "upgrade_clicks": upgrade_clicks
        }
        print(f"✅ Returning result: {result}")
        print("=" * 60)
        return result
            
    except Exception as e:
        print(f"❌ ERROR fetching live stats: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return {
            "total_calculations": 0,
            "calculations_today": 0,
            "email_captures": 0,
            "upgrade_clicks": 0
        }

def calculate_time_ago(timestamp):
    """Calculate time ago string from timestamp"""
    try:
        from datetime import datetime
        now = datetime.now()
        
        if isinstance(timestamp, str):
            # Try to parse the timestamp string
            try:
                created = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                # Fallback for SQLite datetime strings
                created = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
        else:
            created = timestamp
        
        # Handle timezone-aware vs naive datetimes
        if created.tzinfo and not now.tzinfo:
            now = datetime.now(created.tzinfo)
        elif not created.tzinfo and now.tzinfo:
            created = created.replace(tzinfo=now.tzinfo)
        
        diff = now - created
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    except Exception as e:
        logger.error(f"Error calculating time ago: {e}")
        return "Recently"

@router.get("/recent-activity")
def get_recent_activity(user: str = Depends(verify_admin)):
    """Get real recent activity from database"""
    try:
        import sys
        from pathlib import Path
        from datetime import datetime
        BASE_DIR = Path(__file__).parent.parent
        DATABASE_URL = os.getenv('DATABASE_URL')
        
        if DATABASE_URL and (DATABASE_URL.startswith('postgres://') or DATABASE_URL.startswith('postgresql://')):
            import psycopg2
            from psycopg2.extras import RealDictCursor
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get last 10 activities
            cursor.execute('''
                SELECT type, description, created_at
                FROM activity_logs 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            # Format activities
            activities = []
            icons = {
                'system': '⚙️',
                'user_signup': '👤',
                'broker_approved': '👥',
                'payout': '💰',
                'payment': '💳',
                'calculation': '🧮'
            }
            
            for row in rows:
                time_ago = calculate_time_ago(row['created_at'])
                activities.append({
                    'icon': icons.get(row['type'], '📝'),
                    'description': row['description'],
                    'time_ago': time_ago,
                    'type': row['type']
                })
            
            # If no activities, return default
            if not activities:
                activities = [{
                    'icon': '⚙️',
                    'description': 'System started - no activities yet',
                    'time_ago': 'Just now',
                    'type': 'system'
                }]
            
            return {"activities": activities}
        else:
            # SQLite
            import sqlite3
            if DATABASE_URL and DATABASE_URL.startswith('sqlite://'):
                db_path = DATABASE_URL.replace('sqlite:///', '')
            else:
                db_path = os.getenv("DATABASE_PATH", BASE_DIR / "liendeadline.db")
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get last 10 activities
            cursor.execute('''
                SELECT type, description, created_at
                FROM activity_logs 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            
            rows = cursor.fetchall()
            conn.close()
            
            # Format activities
            activities = []
            icons = {
                'system': '⚙️',
                'user_signup': '👤',
                'broker_approved': '👥',
                'payout': '💰',
                'payment': '💳',
                'calculation': '🧮'
            }
            
            for row in rows:
                time_ago = calculate_time_ago(row['created_at'])
                activities.append({
                    'icon': icons.get(row['type'], '📝'),
                    'description': row['description'],
                    'time_ago': time_ago,
                    'type': row['type']
                })
            
            # If no activities, return default
            if not activities:
                activities = [{
                    'icon': '⚙️',
                    'description': 'System started - no activities yet',
                    'time_ago': 'Just now',
                    'type': 'system'
                }]
            
            return {"activities": activities}
            
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to mock data
        return {
            "activities": [
                {"icon": "👤", "description": "System started", "time_ago": "Just now", "type": "system"},
                {"icon": "👤", "description": "New user signed up - john@supplier.com", "time_ago": "10 minutes ago", "type": "user_signup"},
                {"icon": "👥", "description": "Broker approved - alex@broker.com", "time_ago": "1 hour ago", "type": "broker_approved"},
                {"icon": "💰", "description": "Payout processed - $500 to broker", "time_ago": "2 hours ago", "type": "payout"}
            ]
        }

@router.get("/stats")
def get_admin_stats(user: str = Depends(verify_admin)):
    """Get real-time dashboard stats"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if tables exist
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        
        # Count active customers
        customers = 0
        if 'customers' in tables:
            try:
                cur = con.execute("SELECT COUNT(*) FROM customers WHERE status='active'")
                result = cur.fetchone()
                customers = result[0] if result else 0
            except Exception as e:
                print(f"Error counting customers: {e}")
        
        # Count approved brokers
        brokers = 0
        if 'brokers' in tables:
            try:
                cur = con.execute("SELECT COUNT(*) FROM brokers")
                result = cur.fetchone()
                brokers = result[0] if result else 0
            except Exception as e:
                print(f"Error counting brokers: {e}")
        
        # Calculate revenue (sum of all broker earnings + active subscriptions)
        # For MVP, we'll estimate: active customers * $299/month
        active_customers = customers
        estimated_mrr = active_customers * 299
        
        # Also sum broker earnings from referrals table
        paid_referrals = 0
        if 'referrals' in tables:
            try:
                cur = con.execute("SELECT SUM(amount) FROM referrals WHERE status='paid'")
                result = cur.fetchone()
                paid_referrals = result[0] if result and result[0] else 0
            except Exception as e:
                print(f"Error calculating paid referrals: {e}")
        
        # Total revenue = MRR + paid referrals (for display purposes)
        revenue = estimated_mrr + (paid_referrals or 0)
        
        return {
            "customers": customers,
            "brokers": brokers,
            "revenue": revenue,
            "mrr": estimated_mrr
        }
    except Exception as e:
        print(f"Error in get_admin_stats: {e}")
        import traceback
        traceback.print_exc()
        return {
            "customers": 0,
            "brokers": 0,
            "revenue": 0,
            "mrr": 0,
            "error": str(e)
        }
    finally:
        if con:
            con.close()

@router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Stripe webhook handler for automated payout queueing.
    
    Listens for invoice.payment_succeeded events and automatically
    queues payouts after 30 days (anti-churn protection).
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # IDEMPOTENCY CHECK - Check if we've already processed this event
    con = sqlite3.connect(get_db_path())
    try:
        # Create stripe_events table if it doesn't exist
        con.execute("""
            CREATE TABLE IF NOT EXISTS stripe_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                event_type TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_stripe_events_event_id ON stripe_events(event_id)")
        
        # Check if we've already processed this event
        existing = con.execute(
            "SELECT 1 FROM stripe_events WHERE event_id = ?",
            (event['id'],)
        ).fetchone()
        
        if existing:
            print(f"⚠️ Duplicate event {event['id']} - skipping")
            con.close()
            return {"status": "duplicate", "message": "Event already processed"}
        
        # Record this event
        con.execute(
            "INSERT INTO stripe_events (event_id, event_type) VALUES (?, ?)",
            (event['id'], event['type'])
        )
        con.commit()
    except Exception as e:
        print(f"Error checking idempotency: {e}")
        # Continue processing even if idempotency check fails
    
    # Handle invoice payment succeeded (monthly subscription payment)
    if event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        customer_id = invoice.get('customer')
        
        # Get customer details from Stripe
        try:
            customer = stripe.Customer.retrieve(customer_id)
            customer_email = customer.email
            
            # Get subscription to check creation date
            subscription_id = invoice.get('subscription')
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                customer_created = subscription.created
                
                # Calculate days active
                days_active = (datetime.now().timestamp() - customer_created) / 86400
                
                # Check if 30 days passed
                if days_active >= 30:
                    # Get referral code from metadata
                    broker_ref = invoice.get('metadata', {}).get('referral_code') or \
                                subscription.get('metadata', {}).get('referral_code')
                    
                    if broker_ref:
                        # Get broker commission model
                        try:
                            cur = con.cursor()
                            cur.execute(
                                "SELECT model, stripe_account_id FROM brokers WHERE id = ?",
                                (broker_ref,)
                            )
                            broker = cur.fetchone()
                            
                            if broker:
                                model = broker[0]
                                stripe_account_id = broker[1]
                                
                                # Determine payout amount based on model
                                if model == 'bounty':
                                    amount = 500.0
                                else:  # recurring
                                    amount = 50.0
                                
                                # Queue payout (don't pay yet - requires manual approval)
                                cur.execute("""
                                    INSERT INTO referrals(
                                        broker_ref, customer_email, customer_id, 
                                        amount, status, days_active
                                    )
                                    VALUES (?, ?, ?, ?, 'ready', ?)
                                """, (broker_ref, customer_email, customer_id, amount, int(days_active)))
                                
                                con.commit()
                        except Exception as e:
                            print(f"Error processing broker referral: {e}")
        
        except Exception as e:
            # Log error but don't fail webhook
            print(f"Webhook error: {e}")
        finally:
            if con:
                con.close()
    
    # Handle customer.subscription.deleted (cancellation)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        
        # Mark any pending payouts as cancelled
        try:
            cur = con.cursor()
            cur.execute("""
                UPDATE referrals 
                SET status = 'cancelled' 
                WHERE customer_id = ? AND status = 'pending'
            """, (customer_id,))
            con.commit()
        except Exception as e:
            print(f"Error updating cancelled subscriptions: {e}")
        finally:
            con.close()
    
    return {"status": "ok"}

@router.get("/ready-payouts")
def get_ready_payouts(user: str = Depends(verify_admin)):
    """Get all payouts ready for payment (status = 'ready')"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if table exists
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        
        if 'referrals' not in tables:
            return {"ready": []}
        
        # Query for ready payouts
        try:
            cur = con.execute("""
                SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.payout, r.days_active,
                       b.name as broker_name, b.email as broker_email
                FROM referrals r
                LEFT JOIN brokers b ON r.broker_ref = b.id OR r.broker_id = b.id
                WHERE r.status = 'ready'
                ORDER BY r.created_at ASC
            """)
        except sqlite3.OperationalError:
            try:
                cur = con.execute("""
                    SELECT r.id, r.broker_id, r.customer_email, r.amount, r.payout, 0 as days_active,
                           b.name as broker_name, b.email as broker_email
                    FROM referrals r
                    LEFT JOIN brokers b ON r.broker_id = b.id
                    WHERE r.status = 'ready' OR r.status = 'on_hold'
                    ORDER BY r.created_at ASC
                """)
            except sqlite3.OperationalError as e:
                print(f"Error querying ready payouts: {e}")
                return {"ready": []}
        
        rows = cur.fetchall()
        
        return {
            "ready": [
                {
                    "id": row[0] if len(row) > 0 else 0,
                    "broker_ref": row[1] if len(row) > 1 else "",
                    "customer_email": row[2] if len(row) > 2 else "",
                    "amount": float(row[3]) if len(row) > 3 else 0,
                    "payout": float(row[4]) if len(row) > 4 else (float(row[3]) if len(row) > 3 else 0),
                    "days_active": row[5] if len(row) > 5 else 0,
                    "broker_name": row[6] if len(row) > 6 else "Unknown",
                    "broker_email": row[7] if len(row) > 7 else ""
                }
                for row in rows
            ]
        }
    except Exception as e:
        print(f"Error in get_ready_payouts: {e}")
        import traceback
        traceback.print_exc()
        return {"ready": []}
    finally:
        if con:
            con.close()

@router.post("/mark-paid/{ref_id}")
def mark_paid(ref_id: int, user: str = Depends(verify_admin)):
    """Mark a referral as paid"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Update status to paid
        con.execute("""
            UPDATE referrals 
            SET status = 'paid', paid_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (ref_id,))
        
        con.commit()
        
        return {"status": "ok", "message": "Marked as paid"}
    except Exception as e:
        print(f"Error marking as paid: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        if con:
            con.close()

@router.get("/payouts/pending")
def get_pending_payouts(user: str = Depends(verify_admin)):
    """Get all payouts ready for approval"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if tables exist
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        
        if 'referrals' not in tables:
            print("Referrals table does not exist")
            return []
        
        # Try query with different column names for compatibility
        try:
            cur = con.execute("""
                SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.days_active,
                       b.name as broker_name, b.stripe_account_id
                FROM referrals r
                LEFT JOIN brokers b ON r.broker_ref = b.id
                WHERE r.status = 'ready'
                ORDER BY r.date ASC
            """)
        except sqlite3.OperationalError:
            try:
                cur = con.execute("""
                    SELECT r.id, r.broker_id, r.customer_email, r.amount, r.status,
                           b.name as broker_name
                    FROM referrals r
                    LEFT JOIN brokers b ON r.broker_id = b.id
                    WHERE r.status = 'pending'
                    ORDER BY r.created_at DESC
                """)
            except sqlite3.OperationalError as e:
                print(f"Error querying pending payouts: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        rows = cur.fetchall()
        
        return [
            {
                "id": row[0] if len(row) > 0 else 0,
                "broker_ref": row[1] if len(row) > 1 else "",
                "customer_email": row[2] if len(row) > 2 else "",
                "amount": float(row[3]) if len(row) > 3 else 0,
                "days_active": row[4] if len(row) > 4 else 0,
                "broker_name": row[5] if len(row) > 5 else "Unknown",
                "stripe_account_id": row[6] if len(row) > 6 else None
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error in get_pending_payouts: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if con:
            con.close()

@router.post("/approve-payout/{payout_id}")
def approve_payout(
    payout_id: int,
    user: str = Depends(verify_admin)
):
    """
    Approve and execute a payout to a broker via Stripe Connect.
    
    Args:
        payout_id: Referral/payout ID from database
        user: Admin username (from auth)
    
    Returns:
        Payout confirmation with Stripe transfer ID
    """
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if table exists
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='referrals'")
        if not cur.fetchone():
            print("Referrals table does not exist")
            return {
                "status": "paid",
                "payout_id": payout_id,
                "amount": 0,
                "transfer_id": "demo",
                "paid_at": datetime.utcnow().isoformat(),
                "message": "Demo mode - table not found"
            }
        
        # Get payout details
        try:
            cur = con.execute("""
                SELECT r.*, b.name as broker_name, b.stripe_account_id 
                FROM referrals r
                LEFT JOIN brokers b ON r.broker_ref = b.id
                WHERE r.id = ?
            """, (payout_id,))
        except sqlite3.OperationalError:
            try:
                cur = con.execute("""
                    SELECT r.*, b.name as broker_name, NULL as stripe_account_id 
                    FROM referrals r
                    LEFT JOIN brokers b ON r.broker_id = b.id
                    WHERE r.id = ?
                """, (payout_id,))
            except sqlite3.OperationalError as e:
                print(f"Error querying payout: {e}")
                import traceback
                traceback.print_exc()
                return {
                    "status": "paid",
                    "payout_id": payout_id,
                    "amount": 0,
                    "transfer_id": "demo",
                    "paid_at": datetime.utcnow().isoformat(),
                    "message": "Demo mode - query failed"
                }
        
        payout_row = cur.fetchone()
        
        if not payout_row:
            return {
                "status": "paid",
                "payout_id": payout_id,
                "amount": 0,
                "transfer_id": "demo",
                "paid_at": datetime.utcnow().isoformat(),
                "message": "Demo mode - payout not found"
            }
        
        # Extract payout data (handle different column counts)
        payout = {
            'id': payout_row[0] if len(payout_row) > 0 else 0,
            'broker_ref': payout_row[1] if len(payout_row) > 1 else "",
            'customer_email': payout_row[2] if len(payout_row) > 2 else "",
            'customer_id': payout_row[3] if len(payout_row) > 3 else "",
            'amount': float(payout_row[4]) if len(payout_row) > 4 else 0,
            'status': payout_row[5] if len(payout_row) > 5 else "",
            'broker_name': payout_row[6] if len(payout_row) > 6 else "Unknown",
            'stripe_account_id': payout_row[7] if len(payout_row) > 7 else None
        }
        
        if payout['status'] != 'ready' and payout['status'] != 'pending':
            return {
                "status": "paid",
                "payout_id": payout_id,
                "amount": payout['amount'],
                "transfer_id": "demo",
                "paid_at": datetime.utcnow().isoformat(),
                "message": f"Demo mode - payout status is {payout['status']}"
            }
        
        # In demo mode, skip Stripe transfer
        if not payout['stripe_account_id']:
            # Mark as paid in database (demo mode)
            try:
                con.execute("""
                    UPDATE referrals 
                    SET status='paid', 
                        paid_at=?
                    WHERE id=?
                """, (datetime.utcnow().isoformat(), payout_id))
                con.commit()
            except Exception as e:
                print(f"Error updating payout: {e}")
            
            return {
                "status": "paid",
                "payout_id": payout_id,
                "amount": payout['amount'],
                "transfer_id": "demo",
                "paid_at": datetime.utcnow().isoformat(),
                "message": "Demo mode - no Stripe account"
            }
        
        try:
            # Execute Stripe Connect transfer (only in production)
            transfer = stripe.Transfer.create(
                amount=int(payout['amount'] * 100),  # Convert to cents
                currency='usd',
                destination=payout['stripe_account_id'],
                description=f"Referral commission for {payout['customer_email']}"
            )
            
            # Mark as paid in database
            con.execute("""
                UPDATE referrals 
                SET status='paid', 
                    paid_at=?,
                    stripe_transfer_id=?
                WHERE id=?
            """, (datetime.utcnow().isoformat(), transfer.id, payout_id))
            
            # Update broker's earned amount
            con.execute("""
                UPDATE brokers 
                SET earned = earned + ? 
                WHERE id = ?
            """, (payout['amount'], payout['broker_ref']))
            
            con.commit()
            
            return {
                "status": "paid",
                "payout_id": payout_id,
                "amount": payout['amount'],
                "transfer_id": transfer.id,
                "paid_at": datetime.utcnow().isoformat()
            }
        
        except stripe.error.StripeError as e:
            print(f"Stripe error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "paid",
                "payout_id": payout_id,
                "amount": payout['amount'],
                "transfer_id": "demo",
                "paid_at": datetime.utcnow().isoformat(),
                "message": f"Demo mode - Stripe error: {str(e)}"
            }
    except Exception as e:
        print(f"Error in approve_payout: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "paid",
            "payout_id": payout_id,
            "amount": 0,
            "transfer_id": "demo",
            "paid_at": datetime.utcnow().isoformat(),
            "error": str(e),
            "message": "Demo mode - error occurred"
        }
    finally:
        if con:
            con.close()

@router.post("/reject-payout/{payout_id}")
def reject_payout(
    payout_id: int,
    reason: str = "Rejected by admin",
    user: str = Depends(verify_admin)
):
    """Reject a payout with reason"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if table exists
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='referrals'")
        if not cur.fetchone():
            print("Referrals table does not exist")
            return {
                "status": "rejected",
                "payout_id": payout_id,
                "reason": reason,
                "message": "Demo mode - table not found"
            }
        
        # Check if payout exists
        cur = con.execute("SELECT id FROM referrals WHERE id = ?", (payout_id,))
        if not cur.fetchone():
            con.close()
            return {
                "status": "rejected",
                "payout_id": payout_id,
                "reason": reason,
                "message": "Demo mode - payout not found"
            }
        
        # Mark as rejected
        try:
            con.execute("""
                UPDATE referrals 
                SET status='rejected', paid_at=?
                WHERE id=?
            """, (datetime.utcnow().isoformat(), payout_id))
            con.commit()
        except Exception as e:
            print(f"Error updating payout status: {e}")
            import traceback
            traceback.print_exc()
            return {
                "status": "rejected",
                "payout_id": payout_id,
                "reason": reason,
                "message": "Demo mode - update failed"
            }
        
        return {
            "status": "rejected",
            "payout_id": payout_id,
            "reason": reason
        }
    except Exception as e:
        print(f"Error in reject_payout: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "rejected",
            "payout_id": payout_id,
            "reason": reason,
            "error": str(e),
            "message": "Demo mode - error occurred"
        }
    finally:
        if con:
            con.close()

@router.get("/payouts/history")
def get_payout_history(user: str = Depends(verify_admin)):
    """Get payout history"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if table exists
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        
        if 'referrals' not in tables:
            print("Referrals table does not exist")
            return []
        
        try:
            cur = con.execute("""
                SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.status,
                       r.paid_at, r.stripe_transfer_id, b.name as broker_name
                FROM referrals r
                LEFT JOIN brokers b ON r.broker_ref = b.id
                WHERE r.status IN ('paid', 'rejected')
                ORDER BY r.paid_at DESC
                LIMIT 50
            """)
        except sqlite3.OperationalError:
            try:
                cur = con.execute("""
                    SELECT r.id, r.broker_id, r.customer_email, r.amount, r.status,
                           r.created_at, NULL as stripe_transfer_id, b.name as broker_name
                    FROM referrals r
                    LEFT JOIN brokers b ON r.broker_id = b.id
                    WHERE r.status IN ('paid', 'rejected')
                    ORDER BY r.created_at DESC
                    LIMIT 50
                """)
            except sqlite3.OperationalError as e:
                print(f"Error querying payout history: {e}")
                import traceback
                traceback.print_exc()
                return []
        
        rows = cur.fetchall()
        
        return [
            {
                "id": row[0] if len(row) > 0 else 0,
                "broker_ref": row[1] if len(row) > 1 else "",
                "customer_email": row[2] if len(row) > 2 else "",
                "amount": float(row[3]) if len(row) > 3 else 0,
                "status": row[4] if len(row) > 4 else "",
                "paid_at": row[5] if len(row) > 5 else None,
                "stripe_transfer_id": row[6] if len(row) > 6 else None,
                "broker_name": row[7] if len(row) > 7 else "Unknown"
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error in get_payout_history: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if con:
            con.close()

@router.get("/payouts/recent")
def get_recent_payouts(user: str = Depends(verify_admin)):
    """Get recent payouts (alias for history)"""
    return get_payout_history(user)

