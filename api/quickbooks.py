"""
QuickBooks Online OAuth 2.0 Integration
Allows users to connect their QuickBooks account and import invoices
"""
import os
import base64
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import RedirectResponse
import httpx
from urllib.parse import urlencode
from api.database import get_db, get_db_cursor, DB_TYPE

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
    """Get user email from session token"""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    
    token = authorization.replace('Bearer ', '')
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT email, id FROM customers 
                    WHERE api_key = %s AND status = 'active'
                """, (token,))
            else:
                cursor.execute("""
                    SELECT email, id FROM customers 
                    WHERE api_key = ? AND status = 'active'
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


@router.get("/api/quickbooks/connect")
async def quickbooks_connect(request: Request, authorization: str = Header(None)):
    """
    Initiate QuickBooks OAuth flow
    Redirects user to QuickBooks authorization page
    """
    if not QB_CLIENT_ID or not QB_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="QuickBooks integration not configured")
    
    # Get user from session
    user = get_user_from_session(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Generate secure random state and store it with user ID
    state = secrets.token_urlsafe(32)
    
    # Store state in database temporarily (expires in 10 minutes)
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
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
    except Exception as e:
        print(f"Error storing OAuth state: {e}")
        # If table doesn't exist, we'll create it in init_db
    
    params = {
        "client_id": QB_CLIENT_ID,
        "scope": QB_SCOPES,
        "redirect_uri": QB_REDIRECT_URI,
        "response_type": "code",
        "state": state
    }
    
    auth_url = f"{QB_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/api/quickbooks/callback")
async def quickbooks_callback(code: str, state: str, realmId: str):
    """
    Handle OAuth callback from QuickBooks
    Exchange authorization code for access token
    """
    if not code or not state or not realmId:
        raise HTTPException(status_code=400, detail="Missing required parameters")
    
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
            if not result:
                raise HTTPException(status_code=400, detail="Invalid or expired state")
            
            user_id = result['user_id'] if DB_TYPE == 'postgresql' else result[0]
            
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
                print(f"QuickBooks token exchange failed: {error_detail}")
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
                        """, (realmId, tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_id))
                    else:
                        cursor.execute("""
                            UPDATE quickbooks_tokens
                            SET realm_id = ?, access_token = ?, refresh_token = ?,
                                expires_at = ?, updated_at = datetime('now')
                            WHERE user_id = ?
                        """, (realmId, tokens['access_token'], tokens.get('refresh_token', ''), 
                              expires_at, user_id))
                else:
                    # Insert new tokens
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            INSERT INTO quickbooks_tokens 
                            (user_id, realm_id, access_token, refresh_token, expires_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (user_id, realmId, tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                    else:
                        cursor.execute("""
                            INSERT INTO quickbooks_tokens 
                            (user_id, realm_id, access_token, refresh_token, expires_at)
                            VALUES (?, ?, ?, ?, ?)
                        """, (user_id, realmId, tokens['access_token'], 
                              tokens.get('refresh_token', ''), expires_at))
                
                conn.commit()
            
            # Redirect to customer dashboard with success message
            return RedirectResponse(url="/customer-dashboard.html?qb_connected=true")
            
    except httpx.HTTPError as e:
        print(f"HTTP error during token exchange: {e}")
        raise HTTPException(status_code=500, detail="Error connecting to QuickBooks")
    except Exception as e:
        print(f"Error during token exchange: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unexpected error during OAuth")


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
                    return None
                
                tokens = response.json()
                expires_in = tokens.get('expires_in', 3600)
                expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                # Update tokens
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        UPDATE quickbooks_tokens
                        SET access_token = %s, refresh_token = %s, expires_at = %s, updated_at = NOW()
                        WHERE user_id = %s
                    """, (tokens['access_token'], tokens.get('refresh_token', refresh_token), 
                          expires_at, user_id))
                else:
                    cursor.execute("""
                        UPDATE quickbooks_tokens
                        SET access_token = ?, refresh_token = ?, expires_at = ?, updated_at = datetime('now')
                        WHERE user_id = ?
                    """, (tokens['access_token'], tokens.get('refresh_token', refresh_token), 
                          expires_at, user_id))
                
                conn.commit()
                return tokens['access_token']
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


@router.get("/api/quickbooks/invoices")
async def get_quickbooks_invoices(request: Request, authorization: str = Header(None)):
    """
    Fetch invoices from QuickBooks
    Calculate lien deadlines for each
    """
    # Get user from session
    user = get_user_from_session(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    # Get valid access token
    access_token = await get_valid_access_token(user['id'])
    if not access_token:
        raise HTTPException(status_code=401, detail="QuickBooks not connected. Please connect your account first.")
    
    # Get realm_id
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT realm_id FROM quickbooks_tokens WHERE user_id = %s
                """, (user['id'],))
            else:
                cursor.execute("""
                    SELECT realm_id FROM quickbooks_tokens WHERE user_id = ?
                """, (user['id'],))
            
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=401, detail="QuickBooks not connected")
            
            realm_id = result['realm_id'] if DB_TYPE == 'postgresql' else result[0]
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting realm_id: {e}")
        raise HTTPException(status_code=500, detail="Error accessing QuickBooks connection")
    
    # Fetch invoices from QuickBooks
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{QB_API_BASE}/company/{realm_id}/query",
                headers={
                    "Accept": "application/json",
                    "Authorization": f"Bearer {access_token}"
                },
                params={
                    "query": "SELECT * FROM Invoice MAXRESULTS 100"
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
                            "query": "SELECT * FROM Invoice MAXRESULTS 100"
                        }
                    )
            
            if response.status_code != 200:
                error_detail = response.text
                print(f"QuickBooks API error: {error_detail}")
                raise HTTPException(status_code=400, detail=f"Failed to fetch invoices: {error_detail}")
            
            data = response.json()
            invoices = data.get("QueryResponse", {}).get("Invoice", [])
            
            # If single invoice, convert to list
            if isinstance(invoices, dict):
                invoices = [invoices]
            
            # Process invoices
            results = []
            for invoice in invoices:
                txn_date = invoice.get("TxnDate")
                customer_ref = invoice.get("CustomerRef", {})
                customer_name = customer_ref.get("name", "Unknown")
                amount = invoice.get("TotalAmt", 0)
                invoice_id = invoice.get("Id")
                
                # Try to get customer address for state determination
                customer_state = None
                if "BillAddr" in invoice:
                    bill_addr = invoice["BillAddr"]
                    customer_state = bill_addr.get("CountrySubDivisionCode")
                
                results.append({
                    "invoice_id": invoice_id,
                    "customer": customer_name,
                    "date": txn_date,
                    "amount": float(amount) if amount else 0.0,
                    "state": customer_state,
                    "preliminary_deadline": None,  # Will be calculated on demand
                    "lien_deadline": None  # Will be calculated on demand
                })
            
            return {"invoices": results, "count": len(results)}
            
    except httpx.HTTPError as e:
        print(f"HTTP error fetching invoices: {e}")
        raise HTTPException(status_code=500, detail="Error connecting to QuickBooks")
    except Exception as e:
        print(f"Error fetching invoices: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unexpected error fetching invoices")


@router.get("/api/quickbooks/status")
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

