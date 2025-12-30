from fastapi import APIRouter, HTTPException, Request, Header, status
from fastapi.responses import JSONResponse
import stripe
import os
import json
import secrets
import bcrypt
import traceback
import urllib.request
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
from typing import Optional, List, Tuple

# Database imports
from api.database import get_db, execute_query
from api.services.email import send_welcome_email, send_admin_fraud_alert

# Initialize router
router = APIRouter()

# Environment variables
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")



# Fraud Detection Functions
def check_fraud_signals(broker_id: str, customer_email: str, customer_stripe_id: str, session_data: dict) -> Tuple[List[str], int, bool, bool]:
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
                return [], 0, False, False
            
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
            similarity = SequenceMatcher(None, broker_base, customer_base).ratio()
            
            if similarity > 0.8:  # 80% similar
                flags.append('SIMILAR_EMAIL')
                risk_score += 15  # Reduced from 30 - could be legitimate family business
            
            # Check for sequential numbers (john1@, john2@)
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
        traceback.print_exc()
        return ['ERROR_DURING_CHECK'], 0, False, False



# Stripe Webhook Handler
@router.post("/stripe")
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
    
    with get_db() as db:
    
        # IDEMPOTENCY CHECK - Check if we've already processed this event
        try:
            # Create stripe_events table if it doesn't exist
            execute_query(db, """
                CREATE TABLE IF NOT EXISTS stripe_events (
                    id SERIAL PRIMARY KEY,
                    event_id TEXT UNIQUE NOT NULL,
                    event_type TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            execute_query(db, "CREATE INDEX IF NOT EXISTS idx_stripe_events_event_id ON stripe_events(event_id)")
        
            # Check if we've already processed this event
            existing = execute_query(db, 
                "SELECT 1 FROM stripe_events WHERE event_id = ?",
                (event['id'],)
            ).fetchone()
        
            if existing:
                print(f"⚠️ Duplicate event {event['id']} - skipping")
                return {"status": "duplicate", "message": "Event already processed"}
        
            # Record this event
            execute_query(db, 
                "INSERT INTO stripe_events (event_id, event_type) VALUES (?, ?)",
                (event['id'], event['type'])
            )
            db.commit()
        except Exception as e:
            print(f"Error checking idempotency: {e}")
            db.rollback()
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
                    execute_query(db, """
                        INSERT INTO users (email, password_hash, stripe_customer_id, subscription_id, subscription_status)
                        VALUES (?, ?, ?, ?, 'active')
                    """, (email, password_hash.decode(), customer_id, subscription_id))
                
                    # Also create customer record
                    execute_query(db, """
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
                            execute_query(db, """
                                CREATE TABLE IF NOT EXISTS failed_emails (
                                    id SERIAL PRIMARY KEY,
                                    email TEXT NOT NULL,
                                    password TEXT NOT NULL,
                                    reason TEXT,
                                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                )
                            """)
                            execute_query(db, """
                                INSERT INTO failed_emails (email, password, reason)
                                VALUES (?, ?, 'Welcome email send failed')
                            """, (email, temp_password))
                            db.commit()
                            print(f"⚠️ Failed email logged to database for manual follow-up")
                        except Exception as e:
                            print(f"❌ Failed to log failed email: {e}")
                            db.rollback()
                
                    # If referral exists, create pending commission
                    if referral_code.startswith('broker_'):
                        broker = execute_query(db, 
                            "SELECT * FROM brokers WHERE referral_code = ?", 
                            (referral_code,)
                        ).fetchone()
                    
                        if broker:
                            # Create referrals table if it doesn't exist (with fraud detection fields)
                            execute_query(db, """
                                CREATE TABLE IF NOT EXISTS referrals (
                                    id SERIAL PRIMARY KEY,
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
                            execute_query(db, "CREATE INDEX IF NOT EXISTS idx_referral_status ON referrals(status)")
                            execute_query(db, "CREATE INDEX IF NOT EXISTS idx_referral_broker ON referrals(broker_id)")
                        
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
                                existing_ref = execute_query(db, """
                                    SELECT id FROM referrals 
                                    WHERE broker_id = ? AND customer_email = ? AND payout_type = 'bounty'
                                """, (broker['referral_code'], email)).fetchone()
                            
                                if existing_ref:
                                    print(f"⚠️ One-time bounty already exists for {email}, skipping duplicate")
                                    db.commit()
                                    return {"status": "skipped", "reason": "One-time bounty already paid for this customer"}
                        
                            # Store referral with fraud data and payment_date (when payment succeeded)
                            execute_query(db, """
                                INSERT INTO referrals (
                                    broker_id, broker_email, customer_email, customer_stripe_id,
                                    amount, payout, payout_type, status, 
                                    fraud_flags, hold_until, clawback_until,
                                    created_at
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """, (
                                broker['referral_code'], 
                                broker['email'], 
                                email,
                                customer_id,
                                299.00,  # Sale amount
                                payout_amount,  # Commission
                                payout_type,
                                status,
                                json.dumps(flags) if fraud_flags else None,
                                hold_until,
                                clawback_until
                            ))
                            
                            # Send admin alert if flagged
                            if should_flag:
                                send_admin_fraud_alert(broker['email'], email, fraud_flags, risk_score)
                                print(f"🚨 FRAUD ALERT: Referral flagged with score {risk_score}")
                            
                            print(f"✅ Commission recorded for broker {broker['referral_code']}")
                    
                    db.commit()
                    return {"status": "success", "email": email}
                    
                except Exception as e:
                    print(f"❌ Database error in webhook: {e}")
                    db.rollback()
                    traceback.print_exc()
                    # Return success to Stripe so it doesn't retry infinitely for DB errors
                    return {"status": "error", "message": str(e)}
            
            return {"status": "success"}
            
        except Exception as e:
            print(f"Webhook error: {e}")
            return JSONResponse(status_code=500, content={"status": "error"})
