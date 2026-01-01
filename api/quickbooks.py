"""
QuickBooks Online OAuth 2.0 Integration
Allows users to connect their QuickBooks account and import invoices
"""
import os
import base64
import secrets
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import RedirectResponse
from starlette.requests import Request
import httpx
from urllib.parse import urlencode, quote
from api.database import get_db, get_db_cursor, DB_TYPE
from api.routers.auth import get_current_user
from api.calculators import calculate_state_deadline

router = APIRouter()

# QuickBooks OAuth credentials from environment
QB_CLIENT_ID = os.getenv("QUICKBOOKS_CLIENT_ID")
QB_CLIENT_SECRET = os.getenv("QUICKBOOKS_CLIENT_SECRET")
QB_REDIRECT_URI = os.getenv("QUICKBOOKS_REDIRECT_URI", "https://liendeadline.com/api/quickbooks/callback")

# QuickBooks OAuth URLs
QB_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QB_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QB_API_BASE = "https://quickbooks.api.intuit.com/v3"

# QuickBooks scopes
QB_SCOPES = "com.intuit.quickbooks.accounting"


def get_basic_auth():
    """Create Basic Auth header for token exchange"""
    credentials = f"{QB_CLIENT_ID}:{QB_CLIENT_SECRET}"
    return base64.b64encode(credentials.encode()).decode()


def get_user_from_session(authorization: str = Header(None)):
    """Get user email from session token - matches working endpoints"""
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


@router.get("/status")
async def quickbooks_status(current_user: dict = Depends(get_current_user)):
    """
    Check if user is connected to QuickBooks
    """
    user_id = current_user['id']
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT expires_at FROM quickbooks_tokens WHERE user_id = %s", (user_id,))
            else:
                cursor.execute("SELECT expires_at FROM quickbooks_tokens WHERE user_id = ?", (user_id,))
            
            token = cursor.fetchone()
            
            if token:
                return {"connected": True}
            else:
                return {"connected": False}
    except Exception as e:
        print(f"Error checking QB status: {e}")
        return {"connected": False}


@router.get("/connect")
async def quickbooks_connect(request: Request):
    """
    Initiate QuickBooks OAuth flow
    Redirects user to QuickBooks authorization page
    Accepts token via query parameter (for browser redirects) or Authorization header
    """
    if not QB_CLIENT_ID or not QB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="QuickBooks integration not configured")
    
    # Extract token from query parameter (browser redirect) or Authorization header
    token = request.query_params.get('token')
    if not token:
        # Try Authorization header
        authorization = request.headers.get('authorization') or request.headers.get('Authorization')
        if authorization and authorization.startswith('Bearer '):
            token = authorization.replace('Bearer ', '').strip()
    
    if not token:
        # Redirect to login if no token
        return RedirectResponse(url=f"/dashboard?error={quote('Please log in first')}")
    
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
                return RedirectResponse(url=f"/dashboard?error={quote('Invalid session')}")
            
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
                return RedirectResponse(url=f"/dashboard?error={quote('Subscription expired')}")
            
            user = {"id": user_id, "email": user_email}

            # Check if already connected
            if DB_TYPE == 'postgresql':
                cursor.execute("SELECT expires_at FROM quickbooks_tokens WHERE user_id = %s", (user_id,))
            else:
                cursor.execute("SELECT expires_at FROM quickbooks_tokens WHERE user_id = ?", (user_id,))
            
            existing_token = cursor.fetchone()
            if existing_token:
                # User is already connected, redirect to dashboard
                print(f"ℹ️ User {user_id} already connected to QuickBooks. Redirecting.")
                return RedirectResponse(url=f"/dashboard-v2?qb_connected=true&already_connected=true")

    except Exception as e:
        print(f"Error looking up user: {e}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url=f"/dashboard?error={quote('Authentication failed')}")
    
    # Generate secure random state and store it with user ID
    state = secrets.token_urlsafe(32)
    
    # Store state in database temporarily (expires in 10 minutes)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # First verify table exists before attempting to store state
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'quickbooks_oauth_states'
                    )
                """)
                table_exists_result = cursor.fetchone()
                table_exists = table_exists_result['exists'] if table_exists_result else False
            else:
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='quickbooks_oauth_states'
                """)
                table_exists_result = cursor.fetchone()
                table_exists = table_exists_result is not None and len(table_exists_result) > 0
            
            if not table_exists:
                error_msg = "❌ CRITICAL: quickbooks_oauth_states table does not exist!"
                print(error_msg)
                import traceback
                traceback.print_exc()
                return RedirectResponse(url=f"/dashboard-v2?error={quote('System configuration error. Please contact support.')}")
            
            print("✅ quickbooks_oauth_states table exists - proceeding with state storage")
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    INSERT INTO quickbooks_oauth_states (user_id, state, expires_at)
                    VALUES (%s, %s, %s)
                """, (user['id'], state, datetime.now() + timedelta(minutes=10)))
            else:
                cursor.execute("""
                    INSERT INTO quickbooks_oauth_states (user_id, state, expires_at)
                    VALUES (?, ?, ?)
                """, (user['id'], state, datetime.now() + timedelta(minutes=10)))
            
            conn.commit()
            print(f"✅ OAuth state stored successfully for user {user['id']}: {state[:20]}...")
    except Exception as e:
        error_msg = f"❌ CRITICAL: Failed to store OAuth state: {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        # DO NOT redirect to QuickBooks if we can't store state!
        return RedirectResponse(url=f"/dashboard-v2?error={quote('Database error. Please try again or contact support.')}")
    
    params = {
        "client_id": QB_CLIENT_ID,
        "scope": QB_SCOPES,
        "redirect_uri": QB_REDIRECT_URI,
        "response_type": "code",
        "state": state,
        "locale": "en_US"  # Force English locale to prevent Swedish locale issues
    }
    
    auth_url = f"{QB_AUTH_URL}?{urlencode(params)}"
    
    # Debug logging
    print("=" * 60)
    print("🔍 QuickBooks OAuth Connect Debug")
    print("=" * 60)
    print(f"QB_REDIRECT_URI (from env): {QB_REDIRECT_URI}")
    print(f"QB_CLIENT_ID: {QB_CLIENT_ID[:10]}..." if QB_CLIENT_ID else "QB_CLIENT_ID: None")
    print(f"QB_AUTH_URL: {QB_AUTH_URL}")
    print(f"Redirect URI being sent: {QB_REDIRECT_URI}")
    print(f"Complete OAuth URL: {auth_url}")
    print("=" * 60)
    
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def quickbooks_callback(request: Request, code: str = None, state: str = None, realmId: str = None, realm_id: str = None):
    """
    Handle OAuth callback from QuickBooks
    Exchange authorization code for access token
    """
    print("=" * 60)
    print("🔍 QuickBooks OAuth Callback Debug")
    print("=" * 60)
    print(f"✅ CALLBACK ENDPOINT CALLED!")
    print(f"Request URL: {request.url}")
    print(f"Request path: {request.url.path}")
    print(f"Query params: {dict(request.query_params)}")
    print(f"code: {code}")
    print(f"state: {state}")
    print(f"realmId: {realmId}")
    print(f"realm_id: {realm_id}")
    
    # QuickBooks may send realmId or realm_id - try both
    realm_id_value = realmId or realm_id
    
    if not code or not state:
        error_msg = f"Missing required parameters: code={bool(code)}, state={bool(state)}"
        print(f"❌ {error_msg}")
        return RedirectResponse(url=f"/dashboard-v2?error={quote('Missing OAuth parameters')}")
    
    if not realm_id_value:
        error_msg = "Missing realmId parameter"
        print(f"❌ {error_msg}")
        return RedirectResponse(url=f"/dashboard-v2?error={quote('Missing company ID')}")
    
    # Verify state and get user ID
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT user_id FROM quickbooks_oauth_states
                    WHERE state = %s AND expires_at > NOW()
                """, (state,))
            else:
                cursor.execute("""
                    SELECT user_id FROM quickbooks_oauth_states
                    WHERE state = ? AND expires_at > datetime('now')
                """, (state,))
            
            result = cursor.fetchone()
            
            # Debug logging
            print(f"🔍 State validation debug:")
            print(f"   Looking for state: {state[:20]}...")
            print(f"   Found result: {result}")
            
            if not result:
                # Check what states exist in the table for debugging
                try:
                    cursor.execute("SELECT state, user_id, expires_at FROM quickbooks_oauth_states ORDER BY created_at DESC LIMIT 5")
                    all_states = cursor.fetchall()
                    print(f"   Recent states in DB: {len(all_states) if all_states else 0}")
                    if all_states:
                        for idx, s in enumerate(all_states):
                            print(f"      [{idx}] State: {str(s)[:100]}...")
                except Exception as debug_e:
                    print(f"   Could not fetch debug states: {debug_e}")
                
                error_msg = "Invalid or expired OAuth state"
                print(f"❌ {error_msg}")
                return RedirectResponse(url=f"/dashboard-v2?error={quote(error_msg)}")
            
            # Extract user_id - handle both dict and tuple results
            if isinstance(result, dict):
                user_id = result.get('user_id')
            else:
                user_id = result[0] if len(result) > 0 else None
            
            print(f"✅ Found user_id: {user_id} for state: {state[:10]}...")
            
            # Delete used state
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM quickbooks_oauth_states WHERE state = %s", (state,))
            else:
                cursor.execute("DELETE FROM quickbooks_oauth_states WHERE state = ?", (state,))
            
            conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying state: {e}")
        raise HTTPException(status_code=500, detail="Error verifying OAuth state")
    
    # Exchange code for tokens
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                QB_TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": f"Basic {get_basic_auth()}"
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": QB_REDIRECT_URI
                }
            )
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"❌ QuickBooks token exchange failed:")
                print(f"   Status: {response.status_code}")
                print(f"   Response: {error_detail}")
                return RedirectResponse(url=f"/dashboard-v2?error={quote('Failed to get access token')}")
            
            tokens = response.json()
            print(f"✅ Token exchange successful")
            print(f"   Access token: {tokens.get('access_token', '')[:20]}...")
            print(f"   Refresh token: {bool(tokens.get('refresh_token'))}")
            print(f"   Expires in: {tokens.get('expires_in')} seconds")
            
            # Calculate expiration time
            expires_in = tokens.get('expires_in', 3600)  # Default 1 hour
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            # Save tokens to database
            with get_db() as conn:
                cursor = get_db_cursor(conn)
                
                # Check if user already has tokens
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT id FROM quickbooks_tokens WHERE user_id = %s
                    """, (user_id,))
                else:
                    cursor.execute("""
                        SELECT id FROM quickbooks_tokens WHERE user_id = ?
                    """, (user_id,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing tokens
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            UPDATE quickbooks_tokens
                            SET realm_id = %s, access_token = %s, refresh_token = %s,
                                expires_at = %s, updated_at = NOW()
                            WHERE user_id = %s
                        """, (realm_id_value, tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_id))
                    else:
                        cursor.execute("""
                            UPDATE quickbooks_tokens
                            SET realm_id = ?, access_token = ?, refresh_token = ?,
                                expires_at = ?, updated_at = datetime('now')
                            WHERE user_id = ?
                        """, (realm_id_value, tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_id))
                    print(f"✅ Updated existing QuickBooks tokens for user_id: {user_id}")
                else:
                    # Insert new tokens
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            INSERT INTO quickbooks_tokens 
                            (user_id, realm_id, access_token, refresh_token, expires_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (user_id, realm_id_value, tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                    else:
                        cursor.execute("""
                            INSERT INTO quickbooks_tokens 
                            (user_id, realm_id, access_token, refresh_token, expires_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (user_id, realm_id_value, tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                    print(f"✅ Inserted new QuickBooks tokens for user_id: {user_id}, realm_id: {realm_id_value}")
                
                conn.commit()
                print(f"✅ Database commit successful")
            
            # Redirect to customer dashboard with success message
            print(f"✅ Redirecting to dashboard with success")
            return RedirectResponse(url=f"/dashboard-v2?qb_connected=true&cache_bust={int(time.time())}")
            
    except httpx.HTTPError as e:
        error_msg = f"HTTP error during token exchange: {e}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url=f"/dashboard-v2?error={quote('Network error connecting to QuickBooks')}")
    except Exception as e:
        error_msg = f"Error during token exchange: {e}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return RedirectResponse(url=f"/dashboard-v2?error={quote('Unexpected error during OAuth')}")


async def refresh_access_token(user_id: int):
    """Refresh QuickBooks access token using refresh token"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT refresh_token FROM quickbooks_tokens WHERE user_id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT refresh_token FROM quickbooks_tokens WHERE user_id = ?
                """, (user_id,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            refresh_token = result['refresh_token'] if DB_TYPE == 'postgresql' else result[0]
            
            if not refresh_token:
                return None
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    QB_TOKEN_URL,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Authorization": f"Basic {get_basic_auth()}"
                    },
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token
                    }
                )
                
                if response.status_code != 200:
                    print(f"❌ Failed to refresh token: {response.text}")
                    return None
                
                tokens = response.json()
                
                # 1. Capture the New Token
                new_access_token = tokens.get('access_token')
                new_refresh_token = tokens.get('refresh_token')
                expires_in = tokens.get('expires_in', 3600)
                
                if not new_access_token:
                    print("❌ Error: No access token in refresh response")
                    return None

                # Log rotation
                if new_refresh_token:
                    print("✅ QuickBooks rotated the refresh token. Saving new one.")
                else:
                    print("⚠️ No new refresh token provided. Keeping old one.")
                
                # Use new refresh token if provided, otherwise keep old one
                final_refresh_token = new_refresh_token if new_refresh_token else refresh_token
                
                expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # 2. Update Database (Access Token + Refresh Token + Expires At)
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE quickbooks_tokens
                        SET access_token = %s, refresh_token = %s, expires_at = %s, updated_at = NOW()
                        WHERE user_id = %s
                    """, (new_access_token, final_refresh_token, expires_at, user_id))
                else:
                    cursor.execute("""
                        UPDATE quickbooks_tokens
                        SET access_token = ?, refresh_token = ?, expires_at = ?, updated_at = datetime('now')
                        WHERE user_id = ?
                    """, (new_access_token, final_refresh_token, expires_at, user_id))
                
                conn.commit()
                print(f"✅ Successfully updated QuickBooks tokens for user {user_id}")
                return new_access_token
    except Exception as e:
        print(f"Error refreshing token: {e}")
        return None


async def get_valid_access_token(user_id: int):
    """Get valid access token, refreshing if necessary"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT access_token, expires_at FROM quickbooks_tokens WHERE user_id = %s
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT access_token, expires_at FROM quickbooks_tokens WHERE user_id = ?
                """, (user_id,))
            
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
                new_token = await refresh_access_token(user_id)
                return new_token if new_token else access_token
            
            return access_token
    except Exception as e:
        print(f"Error getting access token: {e}")
        return None


@router.get("/invoices")
async def get_quickbooks_invoices(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Fetch invoices from QuickBooks for the logged-in user
    Returns invoices from last 90 days
    """
    # Use current_user from dependency
    user = current_user
    
    # Get user's QuickBooks tokens
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT access_token, refresh_token, realm_id, expires_at
                    FROM quickbooks_tokens
                    WHERE user_id = %s
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT access_token, refresh_token, realm_id, expires_at
                    FROM quickbooks_tokens
                    WHERE user_id = ?
                """, (user['id'],))
            
            qb_token = cursor.fetchone()
            
            if not qb_token:
                raise HTTPException(status_code=404, detail="QuickBooks not connected")
            
            # Extract token data
            if DB_TYPE == 'postgresql':
                access_token = qb_token.get('access_token')
                refresh_token = qb_token.get('refresh_token')
                realm_id = qb_token.get('realm_id')
                expires_at = qb_token.get('expires_at')
            else:
                access_token = qb_token[0] if len(qb_token) > 0 else None
                refresh_token = qb_token[1] if len(qb_token) > 1 else None
                realm_id = qb_token[2] if len(qb_token) > 2 else None
                expires_at = qb_token[3] if len(qb_token) > 3 else None
            
            # Refresh token if expired
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expires_at < datetime.now() + timedelta(minutes=5):
                    # Token expired, refresh it
                    new_token = await refresh_access_token(user['id'])
                    if new_token:
                        access_token = new_token
                    else:
                        raise HTTPException(status_code=401, detail="Failed to refresh QuickBooks token")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting QuickBooks tokens: {e}")
        raise HTTPException(status_code=500, detail="Error accessing QuickBooks connection")
    
    # Fetch invoices from QuickBooks API
    # Get invoices from last 90 days
    ninety_days_ago = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    query = f"SELECT * FROM Invoice WHERE TxnDate >= '{ninety_days_ago}' MAXRESULTS 100"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{QB_API_BASE}/company/{realm_id}/query",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}"
                },
                params={
                    "query": query
                }
            )
            
            if response.status_code == 401:
                # Token expired, try refreshing
                new_token = await refresh_access_token(user['id'])
                if new_token:
                    # Retry with new token
                    response = await client.get(
                        f"{QB_API_BASE}/company/{realm_id}/query",
                        headers={
                            "Accept": "application/json",
                            "Authorization": f"Bearer {new_token}"
                        },
                        params={
                            "query": query
                        }
                    )
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"QuickBooks API error: {error_detail}")
                raise HTTPException(status_code=500, detail=f"Failed to fetch invoices from QuickBooks: {error_detail}")
            
            data = response.json()
            invoices = data.get("QueryResponse", {}).get("Invoice", [])
            
            # If single invoice, convert to list
            if isinstance(invoices, dict):
                invoices = [invoices]
            
            # Format invoices for frontend
            formatted_invoices = []
            today = datetime.now().date()
            
            for inv in invoices:
                # Extract state from shipping or billing address
                state = "TX"  # Default
                
                # Try ShipAddr first (job site)
                if inv.get("ShipAddr") and inv.get("ShipAddr", {}).get("CountrySubDivisionCode"):
                    state = inv.get("ShipAddr", {}).get("CountrySubDivisionCode")
                # Fallback to BillAddr
                elif inv.get("BillAddr") and inv.get("BillAddr", {}).get("CountrySubDivisionCode"):
                    state = inv.get("BillAddr", {}).get("CountrySubDivisionCode")
                
                # Calculate deadlines
                try:
                    invoice_date_str = inv.get("TxnDate")
                    invoice_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
                    
                    deadlines = calculate_state_deadline(
                        state_code=state,
                        invoice_date=invoice_date
                    )
                    
                    prelim_deadline = deadlines.get("preliminary_deadline")
                    lien_deadline = deadlines.get("lien_deadline")
                    
                    # Calculate days remaining
                    prelim_days = None
                    if prelim_deadline:
                        prelim_days = (prelim_deadline.date() - today).days
                        
                    lien_days = None
                    if lien_deadline:
                        lien_days = (lien_deadline.date() - today).days
                        
                    # Format dates for JSON
                    prelim_str = prelim_deadline.strftime("%Y-%m-%d") if prelim_deadline else None
                    lien_str = lien_deadline.strftime("%Y-%m-%d") if lien_deadline else None
                    
                except Exception as e:
                    print(f"Error calculating deadlines for invoice {inv.get('DocNumber')}: {e}")
                    prelim_str = None
                    lien_str = None
                    prelim_days = None
                    lien_days = None
                    state = "Unknown"

                formatted_invoices.append({
                    "id": inv.get("Id"),
                    "invoice_number": inv.get("DocNumber"),
                    "date": inv.get("TxnDate"),
                    "customer_name": inv.get("CustomerRef", {}).get("name", "Unknown"),
                    "amount": float(inv.get("TotalAmt", 0)),
                    "balance": float(inv.get("Balance", 0)),
                    "status": "Unpaid" if float(inv.get("Balance", 0)) > 0 else "Paid",
                    "state": state,
                    "preliminary_deadline": prelim_str,
                    "lien_deadline": lien_str,
                    "prelim_days_remaining": prelim_days,
                    "lien_days_remaining": lien_days
                })
            
            return {
                "invoices": formatted_invoices,
                "count": len(formatted_invoices)
            }
            
    except httpx.HTTPError as e:
        print(f"HTTP error fetching invoices: {e}")
        raise HTTPException(status_code=500, detail="Error connecting to QuickBooks")
    except Exception as e:
        print(f"Error fetching invoices: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unexpected error fetching invoices")


@router.get("/status")
async def get_quickbooks_status(request: Request, authorization: str = Header(None)):
    """Check if user has QuickBooks connected"""
    user = get_user_from_session(authorization)
    if not user:
        return {"connected": False}
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT realm_id, expires_at FROM quickbooks_tokens WHERE user_id = %s
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT realm_id, expires_at FROM quickbooks_tokens WHERE user_id = ?
                """, (user['id'],))
            
            result = cursor.fetchone()
            if result:
                expires_at = result['expires_at'] if DB_TYPE == 'postgresql' else result[1]
                is_valid = expires_at and expires_at > datetime.now()
                return {"connected": True, "valid": is_valid}
    except Exception:
        pass
    
    return {"connected": False}


@router.post("/disconnect")
async def disconnect_quickbooks(request: Request, current_user: dict = Depends(get_current_user)):
    """Disconnect QuickBooks account"""
    user = current_user
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("DELETE FROM quickbooks_tokens WHERE user_id = %s", (user['id'],))
            else:
                cursor.execute("DELETE FROM quickbooks_tokens WHERE user_id = ?", (user['id'],))
            
            conn.commit()
            return {"success": True, "message": "QuickBooks account disconnected"}
    except Exception as e:
        print(f"Error disconnecting QuickBooks: {e}")
        raise HTTPException(status_code=500, detail="Error disconnecting QuickBooks account")
