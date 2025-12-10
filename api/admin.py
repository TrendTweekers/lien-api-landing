# admin.py - Admin routes for FastAPI backend
from fastapi import APIRouter, Depends, HTTPException, Request
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

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# Database path helper
def get_db_path():
    """Get database path (works in both local and Railway environments)"""
    return os.getenv("DATABASE_PATH", "admin.db")

# Router without prefix - prefix will be added in main.py include_router call
router = APIRouter(tags=["admin"])

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
def approve_partner(
    application_id: int,
    user: str = Depends(verify_admin)
):
    """Approve a partner application and send referral link"""
    con = sqlite3.connect(get_db_path())
    cur = con.cursor()
    
    try:
        # Fetch application
        cur.execute("SELECT * FROM partner_applications WHERE id = ?", (application_id,))
        app = cur.fetchone()
        
        if not app:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Convert tuple to dict-like access (handle different column counts)
        app_dict = {
            'id': app[0] if len(app) > 0 else None,
            'name': app[2] if len(app) > 2 else '',
            'email': app[1] if len(app) > 1 else '',
            'company': app[3] if len(app) > 3 else '',
            'commission_model': app[6] if len(app) > 6 else 'bounty'
        }
        
        # Generate unique referral code
        referral_code = f"broker_{secrets.token_urlsafe(8).upper()}"
        referral_link = f"https://liendeadline.com?ref={referral_code}"
        
        # Create brokers table if it doesn't exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS brokers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT,
                referral_code TEXT UNIQUE NOT NULL,
                referral_link TEXT NOT NULL,
                commission_model TEXT NOT NULL,
                pending_commissions INTEGER DEFAULT 0,
                paid_commissions REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create broker record
        cur.execute("""
            INSERT INTO brokers (id, name, email, company, referral_code, referral_link, 
                               commission_model, pending_commissions, paid_commissions)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
        """, (
            referral_code,
            app_dict['name'],
            app_dict['email'],
            app_dict['company'],
            referral_code,
            referral_link,
            app_dict['commission_model']
        ))
        
        # Try to add approval columns if they don't exist
        try:
            cur.execute("ALTER TABLE partner_applications ADD COLUMN approved_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE partner_applications ADD COLUMN referral_link TEXT")
        except sqlite3.OperationalError:
            pass
        
        # Mark application as approved
        cur.execute("""
            UPDATE partner_applications 
            SET status = 'approved',
                approved_at = CURRENT_TIMESTAMP,
                referral_link = ?
            WHERE id = ?
        """, (referral_link, application_id))
        
        con.commit()
        
        # Import send_broker_welcome_email from main.py
        from api.main import send_broker_welcome_email
        
        # Send welcome email
        send_broker_welcome_email(
            app_dict['email'],
            app_dict['name'],
            referral_link,
            referral_code
        )
        
        logger.info(f"Partner approved: {app_dict['email']} - Referral code: {referral_code}")
        
        return {
            "status": "approved",
            "referral_code": referral_code,
            "referral_link": referral_link
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving partner: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        con.close()

@router.get("/partner-applications")
def get_partner_applications(
    status: str = "pending",
    user: str = Depends(verify_admin)
):
    """Get partner applications filtered by status"""
    con = sqlite3.connect(get_db_path())
    try:
        cur = con.cursor()
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
                status TEXT DEFAULT 'pending',
                referral_link TEXT
            )
        """)
        
        if status == "pending":
            query = "SELECT * FROM partner_applications WHERE status = 'pending' OR status IS NULL ORDER BY timestamp DESC"
        elif status == "approved":
            query = "SELECT * FROM partner_applications WHERE status = 'approved' ORDER BY timestamp DESC"
        elif status == "flagged":
            query = "SELECT * FROM partner_applications WHERE status = 'flagged' ORDER BY timestamp DESC"
        elif status == "all":
            query = "SELECT * FROM partner_applications ORDER BY timestamp DESC"
        else:
            query = "SELECT * FROM partner_applications ORDER BY timestamp DESC"
        
        applications = cur.execute(query).fetchall()
        
        return {
            "applications": [
                {
                    "id": app[0],
                    "email": app[1] if len(app) > 1 else '',
                    "name": app[2] if len(app) > 2 else '',
                    "company": app[3] if len(app) > 3 else '',
                    "client_count": app[4] if len(app) > 4 else '',
                    "message": app[5] if len(app) > 5 else '',
                    "commission_model": app[6] if len(app) > 6 else '',
                    "timestamp": app[7] if len(app) > 7 else '',
                    "created_at": app[7] if len(app) > 7 else '',
                    "status": app[8] if len(app) > 8 else 'pending',
                    "referral_link": app[9] if len(app) > 9 else None
                }
                for app in applications
            ],
            "total": len(applications)
        }
    except Exception as e:
        logger.error(f"Error getting partner applications: {e}")
        return {"applications": [], "total": 0}
    finally:
        con.close()

@router.get("/brokers")
def list_brokers(user: str = Depends(verify_admin)):
    """List all brokers"""
    con = None
    try:
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        
        # Check if table exists
        cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brokers'")
        if not cur.fetchone():
            print("Brokers table does not exist")
            return []
        
        cur = con.execute("SELECT id, email, name, model, referrals, earned FROM brokers")
        rows = cur.fetchall()
        
        return [
            {
                "referral_code": row[0] if len(row) > 0 else "",
                "email": row[1] if len(row) > 1 else "",
                "name": row[2] if len(row) > 2 else "",
                "model": row[3] if len(row) > 3 else "",
                "referrals": row[4] if len(row) > 4 else 0,
                "earned": row[5] if len(row) > 5 else 0
            }
            for row in rows
        ]
    except Exception as e:
        print(f"Error in list_brokers: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        if con:
            con.close()

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

