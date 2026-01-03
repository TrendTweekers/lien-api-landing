from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import secrets
import bcrypt
import traceback
import string
import os

from api.database import get_db, get_db_cursor, DB_TYPE
from api.services.email import send_broker_welcome_email, send_broker_notification, send_welcome_email_background, send_broker_password_reset_email
from api.encryption import encrypt_data, decrypt_data, mask_sensitive_data
from api.short_link_system import ShortLinkGenerator

router = APIRouter()

# Models
class BrokerApplication(BaseModel):
    name: str
    email: EmailStr
    company: str
    message: str = ""
    commission_model: str  # "bounty" or "recurring"

class BrokerLoginRequest(BaseModel):
    email: str
    password: str

class BrokerUpdatePaymentRequest(BaseModel):
    email: str
    payment_method: str = ""
    payment_email: str = ""
    iban: str = ""
    swift_code: str = ""
    bank_name: str = ""
    bank_address: str = ""
    account_holder_name: str = ""
    crypto_wallet: str = ""
    crypto_currency: str = ""
    tax_id: str = ""

# Helper Functions

async def auto_approve_broker(name: str, email: str, company: str, commission_model: str, message: str):
    """Auto-approve broker and create account immediately"""
    
    try:
        print("=" * 60)
        print("🚀 AUTO-APPROVING BROKER")
        print("=" * 60)
        
        # Generate referral code: broker_[random6]
        random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
        referral_code = f"broker_{random_suffix}"
        
        # Use professional referral link format with ?via= parameter
        referral_link = f"https://liendeadline.com/?via={referral_code}"
        
        # Generate short code for legacy compatibility (not used in referral link anymore)
        short_code = ShortLinkGenerator.generate_short_code(email, length=4)
        
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
                # Collision - generate new referral code
                random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
                referral_code = f"broker_{random_suffix}"
                referral_link = f"https://liendeadline.com/?via={referral_code}"
                short_code = ShortLinkGenerator.generate_random_code(length=6)
                print(f"⚠️ Short code collision, using new referral code: {referral_code}")
            
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

# Endpoints

@router.post("/api/v1/broker/login")
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

@router.post("/api/v1/broker/logout")
async def broker_logout(authorization: str = Header(None)):
    """
    Logout broker by clearing their session
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No authorization token provided")
    
    token = authorization.replace("Bearer ", "")
    
    try:
        # Find broker by token (stored in localStorage, not DB)
        # Since we don't store tokens in DB yet, we can't invalidate server-side
        # For now, just return success (client will clear localStorage)
        # TODO: Add session_token column to brokers table for proper logout
        
        print(f"✅ Broker logout requested (token: {token[:10]}...)")
        
        return {
            "status": "success",
            "message": "Logged out successfully"
        }
        
    except Exception as e:
        print(f"❌ Broker logout error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Logout failed")

@router.get("/api/v1/broker/dashboard")
async def broker_dashboard(request: Request, email: str, authorization: str = Header(None)):
    """Get broker dashboard data - requires approved status"""
    # Validate token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
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

@router.post("/api/v1/broker/payment-info")
async def save_broker_payment_info(request: Request, data: dict, authorization: str = Header(None)):
    """Save or update broker payment information (international support)"""
    # Validate token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
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

@router.get("/api/v1/broker/payment-info")
async def get_broker_payment_info(request: Request, email: str, authorization: str = Header(None)):
    """Get broker payment information (masked for security)"""
    # Validate token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    
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

@router.post("/api/v1/apply-partner")
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
        
        # Auto-approval logic - ALL applicants are auto-approved
        print("🚀 AUTO-APPROVAL: Creating broker immediately...")
        return await auto_approve_broker(name, email, company, commission_model, message)
        
        # NOTE: The code below is no longer reached as all applicants are auto-approved
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
                except Exception:
                    pass  # Column already exists
                # Add commission_model column if it doesn't exist (SQLite)
                try:
                    cursor.execute("ALTER TABLE partner_applications ADD COLUMN commission_model TEXT DEFAULT 'bounty'")
                except Exception:
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

@router.post("/api/v1/broker/change-password")
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

@router.post("/api/v1/broker/request-password-reset")
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

@router.post("/api/v1/broker/reset-password")
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
