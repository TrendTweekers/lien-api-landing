from fastapi import APIRouter, HTTPException, Request, Depends, Header
from pydantic import BaseModel
import secrets
import bcrypt
import traceback
from ..database import get_db, get_db_cursor, DB_TYPE
from ..rate_limiter import limiter

router = APIRouter()

# Authentication Models
class LoginRequest(BaseModel):
    email: str
    password: str

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
