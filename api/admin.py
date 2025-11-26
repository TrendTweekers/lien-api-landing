# admin.py - Admin routes for FastAPI backend
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from datetime import datetime, timedelta
import uuid
import os
import sqlite3
import stripe
import json

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

# Database path helper
def get_db_path():
    """Get database path (works in both local and Railway environments)"""
    return os.getenv("DATABASE_PATH", "admin.db")

router = APIRouter(prefix="/admin", tags=["admin"])

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
    con = sqlite3.connect("admin.db")
    # Check for both old and new column names for compatibility
    try:
        cur = con.execute("SELECT key, email, expiry_date, expiry, max_calls, calls_used, status FROM test_keys ORDER BY expiry_date DESC, expiry DESC")
    except:
        # Fallback for old schema
        cur = con.execute("SELECT key, email, expiry, expiry, max_calls, 0 as calls_used, 'active' as status FROM test_keys ORDER BY expiry DESC")
    
    rows = cur.fetchall()
    con.close()
    
    result = []
    for row in rows:
        # Handle both old and new schema
        expiry = row[2] if row[2] else row[3]  # expiry_date or expiry
        calls_used = row[5] if len(row) > 5 else 0
        status = row[6] if len(row) > 6 else 'active'
        
        # Check if expired
        if expiry:
            expiry_date = datetime.fromisoformat(expiry)
            if expiry_date < datetime.utcnow() or calls_used >= (row[4] or 50):
                status = 'expired'
        
        result.append({
            "key": row[0],
            "email": row[1],
            "expiry_date": expiry,
            "expiry": expiry,  # For backward compatibility
            "max_calls": row[4] or 50,
            "calls_used": calls_used,
            "status": status
        })
    
    return result

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

@router.get("/brokers")
def list_brokers(user: str = Depends(verify_admin)):
    """List all brokers"""
    con = sqlite3.connect("admin.db")
    cur = con.execute("SELECT id, email, name, model, referrals, earned FROM brokers")
    rows = cur.fetchall()
    con.close()
    
    return [
        {
            "referral_code": row[0],
            "email": row[1],
            "name": row[2],
            "model": row[3],
            "referrals": row[4],
            "earned": row[5]
        }
        for row in rows
    ]

@router.get("/customers")
def list_customers(user: str = Depends(verify_admin)):
    """List all customers"""
    con = sqlite3.connect(get_db_path())
    cur = con.execute("SELECT email, api_calls, status FROM customers ORDER BY email")
    rows = cur.fetchall()
    con.close()
    
    return [
        {
            "email": row[0],
            "calls": row[1],
            "status": row[2]
        }
        for row in rows
    ]

@router.get("/stats")
def get_admin_stats(user: str = Depends(verify_admin)):
    """Get real-time dashboard stats"""
    con = sqlite3.connect(get_db_path())
    
    # Count active customers
    cur = con.execute("SELECT COUNT(*) FROM customers WHERE status='active'")
    customers = cur.fetchone()[0] or 0
    
    # Count approved brokers
    cur = con.execute("SELECT COUNT(*) FROM brokers")
    brokers = cur.fetchone()[0] or 0
    
    # Calculate revenue (sum of all broker earnings + active subscriptions)
    # For MVP, we'll estimate: active customers * $299/month
    cur = con.execute("SELECT COUNT(*) FROM customers WHERE status='active'")
    active_customers = cur.fetchone()[0] or 0
    estimated_mrr = active_customers * 299
    
    # Also sum broker earnings from referrals table
    cur = con.execute("SELECT SUM(amount) FROM referrals WHERE status='paid'")
    paid_referrals = cur.fetchone()[0] or 0
    
    # Total revenue = MRR + paid referrals (for display purposes)
    revenue = estimated_mrr + (paid_referrals or 0)
    
    con.close()
    
    return {
        "customers": customers,
        "brokers": brokers,
        "revenue": revenue,
        "mrr": estimated_mrr
    }

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
                        con = sqlite3.connect(get_db_path())
                        cur = con.execute(
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
                            con.execute("""
                                INSERT INTO referrals(
                                    broker_ref, customer_email, customer_id, 
                                    amount, status, days_active
                                )
                                VALUES (?, ?, ?, ?, 'ready', ?)
                            """, (broker_ref, customer_email, customer_id, amount, int(days_active)))
                            
                            con.commit()
                        con.close()
        
        except Exception as e:
            # Log error but don't fail webhook
            print(f"Webhook error: {e}")
    
    # Handle customer.subscription.deleted (cancellation)
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription.get('customer')
        
        # Mark any pending payouts as cancelled
        con = sqlite3.connect(get_db_path())
        con.execute("""
            UPDATE referrals 
            SET status = 'cancelled' 
            WHERE customer_id = ? AND status = 'pending'
        """, (customer_id,))
        con.commit()
        con.close()
    
    return {"status": "ok"}

@router.get("/payouts/pending")
def get_pending_payouts(user: str = Depends(verify_admin)):
    """Get all payouts ready for approval"""
    con = sqlite3.connect("admin.db")
    cur = con.execute("""
        SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.days_active,
               b.name as broker_name, b.stripe_account_id
        FROM referrals r
        JOIN brokers b ON r.broker_ref = b.id
        WHERE r.status = 'ready'
        ORDER BY r.date ASC
    """)
    rows = cur.fetchall()
    con.close()
    
    return [
        {
            "id": row[0],
            "broker_ref": row[1],
            "customer_email": row[2],
            "amount": row[3],
            "days_active": row[4],
            "broker_name": row[5],
            "stripe_account_id": row[6]
        }
        for row in rows
    ]

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
    con = sqlite3.connect("admin.db")
    
    # Get payout details
    cur = con.execute("""
        SELECT r.*, b.name as broker_name, b.stripe_account_id 
        FROM referrals r
        JOIN brokers b ON r.broker_ref = b.id
        WHERE r.id = ?
    """, (payout_id,))
    
    payout_row = cur.fetchone()
    
    if not payout_row:
        con.close()
        raise HTTPException(status_code=404, detail="Payout not found")
    
    # Extract payout data
    payout = {
        'id': payout_row[0],
        'broker_ref': payout_row[1],
        'customer_email': payout_row[2],
        'customer_id': payout_row[3],
        'amount': payout_row[4],
        'status': payout_row[5],
        'broker_name': payout_row[6],
        'stripe_account_id': payout_row[7]
    }
    
    if payout['status'] != 'ready':
        con.close()
        raise HTTPException(status_code=400, detail="Payout is not ready for approval")
    
    if not payout['stripe_account_id']:
        con.close()
        raise HTTPException(status_code=400, detail="Broker has no Stripe Connect account")
    
    try:
        # Execute Stripe Connect transfer
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
        con.close()
        
        return {
            "status": "paid",
            "payout_id": payout_id,
            "amount": payout['amount'],
            "transfer_id": transfer.id,
            "paid_at": datetime.utcnow().isoformat()
        }
    
    except stripe.error.StripeError as e:
        con.close()
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")

@router.post("/reject-payout/{payout_id}")
def reject_payout(
    payout_id: int,
    reason: str = "Rejected by admin",
    user: str = Depends(verify_admin)
):
    """Reject a payout with reason"""
    con = sqlite3.connect("admin.db")
    
    # Check if payout exists
    cur = con.execute("SELECT id FROM referrals WHERE id = ?", (payout_id,))
    if not cur.fetchone():
        con.close()
        raise HTTPException(status_code=404, detail="Payout not found")
    
    # Mark as rejected
    con.execute("""
        UPDATE referrals 
        SET status='rejected', paid_at=?
        WHERE id=?
    """, (datetime.utcnow().isoformat(), payout_id))
    
    con.commit()
    con.close()
    
    return {
        "status": "rejected",
        "payout_id": payout_id,
        "reason": reason
    }

@router.get("/payouts/history")
def get_payout_history(user: str = Depends(verify_admin)):
    """Get payout history"""
    con = sqlite3.connect("admin.db")
    cur = con.execute("""
        SELECT r.id, r.broker_ref, r.customer_email, r.amount, r.status,
               r.paid_at, r.stripe_transfer_id, b.name as broker_name
        FROM referrals r
        JOIN brokers b ON r.broker_ref = b.id
        WHERE r.status IN ('paid', 'rejected')
        ORDER BY r.paid_at DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    con.close()
    
    return [
        {
            "id": row[0],
            "broker_ref": row[1],
            "customer_email": row[2],
            "amount": row[3],
            "status": row[4],
            "paid_at": row[5],
            "stripe_transfer_id": row[6],
            "broker_name": row[7]
        }
        for row in rows
    ]

