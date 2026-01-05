from fastapi import APIRouter, HTTPException, Request, Depends, Header
from pydantic import BaseModel
import secrets
import bcrypt
import hashlib
import traceback
import os
import stripe
from datetime import datetime
from typing import Optional
from ..database import get_db, get_db_cursor, DB_TYPE
from ..rate_limiter import limiter

# Initialize Stripe (if available)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')

router = APIRouter()

# Module-level flag to track if pepper warning has been shown
PEPPER_WARNING_SHOWN = False

# --- Helper Functions ---

def hash_zapier_token(token: str, use_pepper: bool = True) -> str:
    """Hash a Zapier token using SHA-256 with optional server-side pepper
    
    In production, ZAPIER_TOKEN_PEPPER must be set or RuntimeError is raised.
    In non-production, falls back to unpeppered hashing with a warning.
    """
    global PEPPER_WARNING_SHOWN
    pepper = os.getenv('ZAPIER_TOKEN_PEPPER', '').strip()
    
    # Check if we're in production
    env = os.getenv('ENV', '').lower() or os.getenv('ENVIRONMENT', '').lower()
    is_production = env == 'production' or env == 'prod'
    
    if use_pepper and pepper:
        # Use peppered hash (new method)
        combined = pepper + token
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()
    elif use_pepper and not pepper:
        # Pepper missing but requested
        if is_production:
            # Production: pepper is required
            raise RuntimeError("ZAPIER_TOKEN_PEPPER must be set in production")
        else:
            # Non-production: log warning once and fall back
            if not PEPPER_WARNING_SHOWN:
                print("⚠️ WARNING: ZAPIER_TOKEN_PEPPER not set. Using unpeppered hashing for compatibility.")
                PEPPER_WARNING_SHOWN = True
            return hashlib.sha256(token.encode('utf-8')).hexdigest()
    else:
        # Explicitly unpeppered (for backwards compatibility check)
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

def get_user_from_zapier_token(token: str):
    """Helper to get user from Zapier API token (hashed)
    
    Checks both peppered and unpeppered hashes for backwards compatibility.
    """
    # First try peppered hash (new method)
    token_hash_peppered = hash_zapier_token(token, use_pepper=True)
    
    # Also compute unpeppered hash for backwards compatibility
    token_hash_unpeppered = hash_zapier_token(token, use_pepper=False)
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Try peppered hash first (new tokens)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE zapier_token_hash = %s", (token_hash_peppered,))
            else:
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE zapier_token_hash = ?", (token_hash_peppered,))
            
            user = cursor.fetchone()
            
            # If not found with peppered hash, try unpeppered (old tokens)
            if not user and token_hash_peppered != token_hash_unpeppered:
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT id, email, subscription_status FROM users WHERE zapier_token_hash = %s", (token_hash_unpeppered,))
                else:
                    cursor.execute("SELECT id, email, subscription_status FROM users WHERE zapier_token_hash = ?", (token_hash_unpeppered,))
                
                user = cursor.fetchone()
            
            if user:
                if isinstance(user, dict):
                    user_id = user.get('id')
                    email = user.get('email')
                    subscription_status = user.get('subscription_status')
                elif hasattr(user, 'keys'):
                    user_id = user['id'] if 'id' in user.keys() else (user[0] if len(user) > 0 else None)
                    email = user['email'] if 'email' in user.keys() else (user[1] if len(user) > 1 else None)
                    subscription_status = user['subscription_status'] if 'subscription_status' in user.keys() else (user[2] if len(user) > 2 else None)
                else:
                    user_id = user[0] if user and len(user) > 0 else None
                    email = user[1] if user and len(user) > 1 else None
                    subscription_status = user[2] if user and len(user) > 2 else None
                
                if subscription_status in ['active', 'trialing']:
                    return {
                        'id': user_id,
                        'email': email,
                        'subscription_status': subscription_status,
                        'unlimited': True
                    }
    except Exception as e:
        print(f"⚠️ Error checking Zapier token: {e}")
    
    return None

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
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = %s", (token,))
            else:
                cursor.execute("SELECT id, email, subscription_status FROM users WHERE session_token = ?", (token,))
        
            user = cursor.fetchone()
        
            if user:
                if isinstance(user, dict):
                    user_id = user.get('id')
                    email = user.get('email')
                    subscription_status = user.get('subscription_status')
                elif hasattr(user, 'keys'):
                    user_id = user['id'] if 'id' in user.keys() else (user[0] if len(user) > 0 else None)
                    email = user['email'] if 'email' in user.keys() else (user[1] if len(user) > 1 else None)
                    subscription_status = user['subscription_status'] if 'subscription_status' in user.keys() else (user[2] if len(user) > 2 else None)
                else:
                    user_id = user[0] if user and len(user) > 0 else None
                    email = user[1] if user and len(user) > 1 else None
                    subscription_status = user[2] if user and len(user) > 2 else None
            
                if subscription_status in ['active', 'trialing']:
                    return {
                        'id': user_id,
                        'email': email,
                        'subscription_status': subscription_status,
                        'unlimited': True
                    }
    except Exception as e:
        print(f"⚠️ Error checking session: {e}")

    return None

# Dependency to get current user from session token (for backward compatibility)
async def get_current_user(request: Request):
    """Get current user from session token - extract from Request headers"""
    user = get_user_from_session(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

# Dependency for Zapier endpoints - accepts either Zapier token or session token
async def get_current_user_zapier(request: Request):
    """Get current user from Zapier token OR session token (backwards compatible)"""
    authorization = request.headers.get('authorization', '')
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    token = authorization.replace('Bearer ', '')
    
    # First try Zapier token (hashed lookup)
    user = get_user_from_zapier_token(token)
    if user:
        return user
    
    # Fallback to session token (backwards compatible)
    user = get_user_from_session(request)
    if user:
        return user
    
    # Neither worked
    raise HTTPException(status_code=401, detail="Unauthorized")

# Authentication Models
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    stripe_session_id: Optional[str] = None  # Optional - for users coming from Stripe payment

# Authentication Endpoints
@router.post("/api/login")
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

@router.post("/api/register")
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest):
    """Registration endpoint - creates account or updates password for existing user"""
    print(f"📝 Registration attempt for {req.email}")
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Validate email
            email = req.email.lower().strip()
            if not email or '@' not in email:
                raise HTTPException(status_code=400, detail="Invalid email address")
            
            # Validate password
            if len(req.password) < 8:
                raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
            
            # Check if user exists (created by webhook after payment)
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT id, email, password_hash, subscription_status FROM users WHERE email = %s", (email,))
            else:
                cursor.execute("SELECT id, email, password_hash, subscription_status FROM users WHERE email = ?", (email,))
            
            user = cursor.fetchone()
            
            # Extract user data
            if user:
                if isinstance(user, dict):
                    user_id = user.get('id')
                    existing_password_hash = user.get('password_hash', '')
                    subscription_status = user.get('subscription_status', '')
                else:
                    user_id = user[0] if len(user) > 0 else None
                    existing_password_hash = user[2] if len(user) > 2 else ''
                    subscription_status = user[3] if len(user) > 3 else ''
            else:
                user_id = None
                existing_password_hash = ''
                subscription_status = ''
            
            # Hash new password
            password_hash = bcrypt.hashpw(req.password.encode('utf-8'), bcrypt.gensalt())
            
            if user_id:
                # User exists (created by webhook or previous registration)
                if existing_password_hash:
                    # User already has password - account exists, should login instead
                    raise HTTPException(status_code=400, detail="Account already exists. Please login.")
                else:
                    # Webhook created account, user setting password for first time
                    print(f"✅ User exists (from webhook), setting password for {email}")
                    
                    # Update password
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            UPDATE users 
                            SET password_hash = %s
                            WHERE email = %s
                        """, (password_hash.decode(), email))
                    else:
                        cursor.execute("""
                            UPDATE users 
                            SET password_hash = ?
                            WHERE email = ?
                        """, (password_hash.decode(), email))
            else:
                # New user - create free tier account (unless coming from Stripe payment)
                print(f"📝 Creating new account for {email}")
                
                # Determine subscription status
                if req.stripe_session_id:
                    # User came from Stripe payment - get their subscription details
                    try:
                        session = stripe.checkout.Session.retrieve(req.stripe_session_id)
                        customer_id = session.get('customer')
                        subscription_id = session.get('subscription')
                        subscription_status = 'active'
                        
                        # Create user with active subscription
                        if DB_TYPE == 'postgresql':
                            cursor.execute("""
                                INSERT INTO users (email, password_hash, subscription_status, stripe_customer_id, subscription_id, created_at)
                                VALUES (%s, %s, %s, %s, %s, NOW())
                                RETURNING id
                            """, (email, password_hash.decode(), subscription_status, customer_id, subscription_id))
                            result = cursor.fetchone()
                            user_id = result[0] if result else None
                        else:
                            cursor.execute("""
                                INSERT INTO users (email, password_hash, subscription_status, stripe_customer_id, subscription_id, created_at)
                                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """, (email, password_hash.decode(), subscription_status, customer_id, subscription_id))
                            user_id = cursor.lastrowid
                    except Exception as stripe_error:
                        print(f"⚠️ Error fetching Stripe session: {stripe_error}")
                        # Fallback to free tier if Stripe lookup fails
                        subscription_status = 'free'
                        
                        if DB_TYPE == 'postgresql':
                            cursor.execute("""
                                INSERT INTO users (email, password_hash, subscription_status, created_at)
                                VALUES (%s, %s, %s, NOW())
                                RETURNING id
                            """, (email, password_hash.decode(), subscription_status))
                            result = cursor.fetchone()
                            user_id = result[0] if result else None
                        else:
                            cursor.execute("""
                                INSERT INTO users (email, password_hash, subscription_status, created_at)
                                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                            """, (email, password_hash.decode(), subscription_status))
                            user_id = cursor.lastrowid
                else:
                    # Free tier user (no payment)
                    subscription_status = 'free'
                    
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            INSERT INTO users (email, password_hash, subscription_status, created_at)
                            VALUES (%s, %s, %s, NOW())
                            RETURNING id
                        """, (email, password_hash.decode(), subscription_status))
                        result = cursor.fetchone()
                        user_id = result[0] if result else None
                    else:
                        cursor.execute("""
                            INSERT INTO users (email, password_hash, subscription_status, created_at)
                            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """, (email, password_hash.decode(), subscription_status))
                        user_id = cursor.lastrowid
                
                conn.commit()
                print(f"✅ Account created for {email} with status: {subscription_status}")
            
            # Generate session token
            token = secrets.token_urlsafe(32)
            
            # Update session token
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users 
                    SET session_token = %s, last_login_at = NOW()
                    WHERE email = %s
                """, (token, email))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET session_token = ?, last_login_at = CURRENT_TIMESTAMP
                    WHERE email = ?
                """, (token, email))
            
            conn.commit()
            
            print(f"✅ Registration successful for {email}")
            
            return {
                "success": True,
                "session_token": token,
                "token": token,  # Keep for backwards compatibility
                "email": email,
                "redirect": "/dashboard"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Registration error: {repr(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")

@router.get("/api/stripe-session-email")
async def get_stripe_session_email(session_id: str):
    """Get email from Stripe checkout session (for registration flow)"""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        email = session.get('customer_details', {}).get('email') or session.get('customer_email')
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found in session")
        
        return {"email": email}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

@router.get("/api/verify-session")
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

@router.post("/api/logout")
async def logout(authorization: str = Header(None)):
    """Logout - invalidate session token"""
    if not authorization or not authorization.startswith('Bearer '):
        return {"success": True, "message": "No token provided"}
    
    token = authorization.replace('Bearer ', '')
    
    try:
        # Get database connection
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Clear the session token in the database
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users 
                    SET session_token = NULL, 
                        updated_at = NOW() 
                    WHERE session_token = %s
                """, (token,))
            else:  # sqlite
                cursor.execute("""
                    UPDATE users 
                    SET session_token = NULL, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE session_token = ?
                """, (token,))
            
            conn.commit()
        
        return {"success": True, "message": "Logged out successfully"}
        
    except Exception as e:
        print(f"Logout error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Logout failed")

# --- Zapier Token Management ---

def ensure_zapier_columns_exist(conn):
    """Ensure Zapier token columns exist in users table (idempotent)
    
    Runtime column creation is only allowed for:
    - SQLite databases (local development)
    - Non-production environments
    
    In production PostgreSQL, columns must be created via migration 004.
    """
    cursor = get_db_cursor(conn)
    
    # Check if we're in production
    env = os.getenv('ENV', '').lower() or os.getenv('ENVIRONMENT', '').lower()
    is_production = env == 'production' or env == 'prod'
    
    if DB_TYPE == 'postgresql':
        if is_production:
            # Production PostgreSQL: Do NOT run ALTER TABLE at runtime
            # Check if columns exist and raise error if missing
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name IN ('zapier_token_hash', 'zapier_token_last4', 'zapier_token_created_at')
            """)
            rows = cursor.fetchall()
            existing_columns = set()
            for row in rows:
                if isinstance(row, dict):
                    existing_columns.add(row.get('column_name'))
                elif isinstance(row, (list, tuple)) and len(row) > 0:
                    existing_columns.add(row[0])
                elif hasattr(row, 'keys') and 'column_name' in row.keys():
                    existing_columns.add(row['column_name'])
            
            required_columns = {'zapier_token_hash', 'zapier_token_last4', 'zapier_token_created_at'}
            missing_columns = required_columns - existing_columns
            
            if missing_columns:
                error_msg = (
                    f"❌ Zapier token columns are missing in production database: {', '.join(missing_columns)}. "
                    f"Please run migration 004_add_zapier_token_fields.sql to add these columns. "
                    f"Runtime ALTER TABLE is not allowed in production PostgreSQL."
                )
                print(error_msg)
                raise RuntimeError(error_msg)
        else:
            # Non-production PostgreSQL: Allow runtime column creation
            try:
                cursor.execute("""
                    DO $$ 
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'users' AND column_name = 'zapier_token_hash'
                        ) THEN
                            ALTER TABLE users ADD COLUMN zapier_token_hash TEXT;
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'users' AND column_name = 'zapier_token_last4'
                        ) THEN
                            ALTER TABLE users ADD COLUMN zapier_token_last4 TEXT;
                        END IF;
                        
                        IF NOT EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'users' AND column_name = 'zapier_token_created_at'
                        ) THEN
                            ALTER TABLE users ADD COLUMN zapier_token_created_at TIMESTAMP;
                        END IF;
                        
                        -- Create index if it doesn't exist
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes 
                            WHERE tablename = 'users' AND indexname = 'idx_users_zapier_token_hash'
                        ) THEN
                            CREATE INDEX idx_users_zapier_token_hash ON users(zapier_token_hash);
                        END IF;
                    END $$;
                """)
                conn.commit()
            except Exception as e:
                print(f"⚠️ Error ensuring Zapier columns (may already exist): {e}")
    else:
        # SQLite: Always allow runtime column creation (local development)
        for column in ['zapier_token_hash', 'zapier_token_last4', 'zapier_token_created_at']:
            try:
                if column == 'zapier_token_created_at':
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} TIMESTAMP")
                else:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
                conn.commit()
            except Exception:
                # Column already exists, ignore
                pass
        
        # Create index for SQLite (IF NOT EXISTS is supported)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_zapier_token_hash ON users(zapier_token_hash)")
            conn.commit()
        except Exception as e:
            print(f"⚠️ Error creating Zapier token index (may already exist): {e}")

@router.get("/api/zapier/token")
@limiter.limit("30/minute")
async def get_zapier_token_status(request: Request, current_user: dict = Depends(get_current_user)):
    """Get Zapier token status (does not return plaintext token)"""
    try:
        with get_db() as conn:
            ensure_zapier_columns_exist(conn)
            cursor = get_db_cursor(conn)
            
            user_id = current_user.get('id')
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT zapier_token_hash, zapier_token_last4, zapier_token_created_at
                    FROM users WHERE id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT zapier_token_hash, zapier_token_last4, zapier_token_created_at
                    FROM users WHERE id = ?
                """, (user_id,))
            
            result = cursor.fetchone()
            
            if isinstance(result, dict):
                token_hash = result.get('zapier_token_hash')
                last4 = result.get('zapier_token_last4')
                created_at = result.get('zapier_token_created_at')
            elif hasattr(result, 'keys'):
                token_hash = result.get('zapier_token_hash') if 'zapier_token_hash' in result.keys() else (result[0] if len(result) > 0 else None)
                last4 = result.get('zapier_token_last4') if 'zapier_token_last4' in result.keys() else (result[1] if len(result) > 1 else None)
                created_at = result.get('zapier_token_created_at') if 'zapier_token_created_at' in result.keys() else (result[2] if len(result) > 2 else None)
            else:
                token_hash = result[0] if result and len(result) > 0 else None
                last4 = result[1] if result and len(result) > 1 else None
                created_at = result[2] if result and len(result) > 2 else None
            
            has_token = token_hash is not None and token_hash != ''
            
            return {
                "has_token": has_token,
                "last4": last4 if has_token else None,
                "created_at": created_at.isoformat() if created_at and has_token else None
            }
    except Exception as e:
        print(f"❌ Error getting Zapier token status: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to get token status")

@router.post("/api/zapier/token/regenerate")
@limiter.limit("5/minute")
async def regenerate_zapier_token(request: Request, current_user: dict = Depends(get_current_user)):
    """Generate a new Zapier API token (returns plaintext ONCE)"""
    try:
        with get_db() as conn:
            ensure_zapier_columns_exist(conn)
            cursor = get_db_cursor(conn)
            
            user_id = current_user.get('id')
            
            # Generate new token
            plaintext_token = secrets.token_urlsafe(48)  # 48 bytes = ~64 chars
            token_hash = hash_zapier_token(plaintext_token)
            last4 = plaintext_token[-4:] if len(plaintext_token) >= 4 else plaintext_token
            
            # Update user record
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users 
                    SET zapier_token_hash = %s,
                        zapier_token_last4 = %s,
                        zapier_token_created_at = NOW()
                    WHERE id = %s
                """, (token_hash, last4, user_id))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET zapier_token_hash = ?,
                        zapier_token_last4 = ?,
                        zapier_token_created_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (token_hash, last4, user_id))
            
            conn.commit()
            
            print(f"✅ Generated new Zapier token for user {user_id}")
            
            # Get created_at
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT zapier_token_created_at FROM users WHERE id = %s", (user_id,))
            else:
                cursor.execute("SELECT zapier_token_created_at FROM users WHERE id = ?", (user_id,))
            
            result = cursor.fetchone()
            if isinstance(result, dict):
                created_at = result.get('zapier_token_created_at')
            elif hasattr(result, 'keys'):
                created_at = result.get('zapier_token_created_at') if 'zapier_token_created_at' in result.keys() else (result[0] if len(result) > 0 else None)
            else:
                created_at = result[0] if result and len(result) > 0 else None
            
            return {
                "token": plaintext_token,  # Return plaintext ONCE
                "last4": last4,
                "created_at": created_at.isoformat() if created_at else datetime.now().isoformat(),
                "message": "Copy this token now — you won't see it again."
            }
    except Exception as e:
        print(f"❌ Error regenerating Zapier token: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to generate token")

@router.post("/api/zapier/token/revoke")
@limiter.limit("5/minute")
async def revoke_zapier_token(request: Request, current_user: dict = Depends(get_current_user)):
    """Revoke/delete Zapier API token"""
    try:
        with get_db() as conn:
            ensure_zapier_columns_exist(conn)
            cursor = get_db_cursor(conn)
            
            user_id = current_user.get('id')
            
            # Clear token fields
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    UPDATE users 
                    SET zapier_token_hash = NULL,
                        zapier_token_last4 = NULL,
                        zapier_token_created_at = NULL
                    WHERE id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    UPDATE users 
                    SET zapier_token_hash = NULL,
                        zapier_token_last4 = NULL,
                        zapier_token_created_at = NULL
                    WHERE id = ?
                """, (user_id,))
            
            conn.commit()
            
            print(f"✅ Revoked Zapier token for user {user_id}")
            
            return {"success": True, "message": "Zapier token revoked successfully"}
    except Exception as e:
        print(f"❌ Error revoking Zapier token: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to revoke token")
