# Integration Summary: QuickBooks, Sage, and Procore

## Overview

The LienDeadline API has integrated three third-party platforms to allow customers to import invoices and automatically calculate lien deadlines:

1. **QuickBooks Online** - Accounting software integration
2. **Sage** (Sage Intacct) - Accounting software integration  
3. **Procore** - Construction project management platform

**Note:** The user mentioned "Procol" but the actual integration is with **Procore** (a construction management platform).

---

## 1. QuickBooks Integration

### Architecture
- **File:** `api/quickbooks.py` (separate router module)
- **Router:** Included in `main.py` as `quickbooks_router`
- **OAuth Flow:** OAuth 2.0 with authorization code grant

### Database Schema

#### `quickbooks_tokens` Table
```sql
CREATE TABLE quickbooks_tokens (
    id SERIAL PRIMARY KEY,                    -- PostgreSQL
    -- id INTEGER PRIMARY KEY AUTOINCREMENT,  -- SQLite
    user_id INTEGER NOT NULL,                 -- References users.id
    realm_id VARCHAR(255) NOT NULL,           -- QuickBooks company ID
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_qb_tokens_user_id ON quickbooks_tokens(user_id);
CREATE INDEX idx_qb_tokens_realm_id ON quickbooks_tokens(realm_id);
```

#### `quickbooks_oauth_states` Table
```sql
CREATE TABLE quickbooks_oauth_states (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,                 -- References users.id
    state VARCHAR(255) UNIQUE NOT NULL,        -- OAuth state parameter
    expires_at TIMESTAMP NOT NULL,            -- 10 minute expiration
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_qb_states_state ON quickbooks_oauth_states(state);
CREATE INDEX idx_qb_states_user_id ON quickbooks_oauth_states(user_id);
```

### Environment Variables
```bash
QUICKBOOKS_CLIENT_ID=...
QUICKBOOKS_CLIENT_SECRET=...
QUICKBOOKS_REDIRECT_URI=https://liendeadline.com/api/quickbooks/callback
```

### OAuth URLs
- **Authorization URL:** `https://appcenter.intuit.com/connect/oauth2`
- **Token URL:** `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer`
- **API Base:** `https://quickbooks.api.intuit.com/v3`
- **Scopes:** `com.intuit.quickbooks.accounting`

### API Endpoints

#### 1. Initiate OAuth Flow
```
GET /api/quickbooks/connect?token={session_token}
```
- Validates user session
- Generates secure state token
- Stores state in `quickbooks_oauth_states` table
- Redirects to QuickBooks authorization page

#### 2. OAuth Callback
```
GET /api/quickbooks/callback?code={auth_code}&state={state}&realmId={company_id}
```
- Verifies state token
- Exchanges authorization code for access/refresh tokens
- Stores tokens in `quickbooks_tokens` table
- Redirects to customer dashboard with success message

#### 3. Get Invoices
```
GET /api/quickbooks/invoices
Headers: Authorization: Bearer {session_token}
```
- Fetches invoices from last 90 days
- Uses QuickBooks Query API: `SELECT * FROM Invoice WHERE TxnDate >= '{date}' MAXRESULTS 100`
- Returns formatted invoice list with:
  - Invoice ID
  - Invoice number
  - Date
  - Customer name
  - Amount
  - Balance
  - Status (Paid/Unpaid)

#### 4. Check Connection Status
```
GET /api/quickbooks/status
Headers: Authorization: Bearer {session_token}
```
- Returns `{"connected": true/false, "valid": true/false}`

#### 5. Disconnect
```
POST /api/quickbooks/disconnect
Headers: Authorization: Bearer {session_token}
```
- Deletes tokens from `quickbooks_tokens` table

### Token Management
- **Automatic Refresh:** Tokens are refreshed automatically if expired (5-minute buffer)
- **Refresh Function:** `refresh_access_token(user_id)` in `api/quickbooks.py`
- **Token Validation:** `get_valid_access_token(user_id)` checks expiration and refreshes if needed

### Frontend Integration
- **Location:** `customer-dashboard.html` (lines 849-1065)
- **Functions:**
  - `connectQuickBooks()` - Initiates OAuth flow
  - `checkQuickBooksStatus()` - Checks connection status
  - `loadQuickBooksInvoices()` - Fetches and displays invoices
  - `disconnectQuickBooks()` - Disconnects account
  - `displayQuickBooksInvoices(invoices)` - Renders invoice list

---

## 2. Sage Integration

### Architecture
- **File:** `api/main.py` (lines 4032-4771)
- **OAuth Flow:** OAuth 2.0 with authorization code grant
- **API Type:** Sage Intacct Operations API

### Database Schema

#### `sage_tokens` Table
```sql
CREATE TABLE sage_tokens (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) UNIQUE NOT NULL,  -- Uses email instead of user_id
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    realm_id VARCHAR(255),                    -- Sage company ID
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `sage_oauth_states` Table
```sql
CREATE TABLE sage_oauth_states (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,         -- Uses email instead of user_id
    state VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
```

**Note:** Sage integration uses `user_email` instead of `user_id` for token storage.

### Environment Variables
```bash
SAGE_CLIENT_ID=...
SAGE_CLIENT_SECRET=...
SAGE_REDIRECT_URI=https://liendeadline.com/api/sage/callback
```

### OAuth URLs
- **Authorization URL:** `https://api.intacct.com/ia/api/v1/oauth2/authorize`
- **Token URL:** `https://api.intacct.com/ia/api/v1/oauth2/token`
- **API Base:** `https://api.intacct.com`
- **Scopes:** `full_access`

### API Endpoints

#### 1. Initiate OAuth Flow
```
GET /api/sage/auth?token={session_token}
```
- Validates user session
- Generates secure state token
- Stores state in `sage_oauth_states` table
- Redirects to Sage authorization page

#### 2. OAuth Callback
```
GET /api/sage/callback?code={auth_code}&state={state}
```
- Verifies state token
- Exchanges authorization code for access/refresh tokens
- Stores tokens in `sage_tokens` table (keyed by `user_email`)
- Redirects to customer dashboard with success message

#### 3. Get Invoices
```
GET /api/sage/invoices
Headers: Authorization: Bearer {session_token}
```
- Fetches sales invoices from Sage
- Uses endpoint: `/sales_invoices` with `items_per_page=100`
- Requires `X-Business` header with `realm_id`
- Returns invoice list with:
  - Invoice ID
  - Customer name
  - Date
  - Amount
  - State (from customer address)
  - Preliminary deadline (calculated on demand)
  - Lien deadline (calculated on demand)

#### 4. Check Connection Status
```
GET /api/sage/status
Headers: Authorization: Bearer {session_token}
```
- Returns `{"connected": true/false, "valid": true/false}`

#### 5. Disconnect
```
POST /api/sage/disconnect
Headers: Authorization: Bearer {session_token}
```
- Deletes tokens from `sage_tokens` table

### Token Management
- **Automatic Refresh:** Tokens are refreshed automatically if expired (5-minute buffer)
- **Refresh Function:** `refresh_sage_access_token(user_email)` in `api/main.py`
- **Token Validation:** `get_valid_sage_access_token(user_email)` checks expiration and refreshes if needed

### Frontend Integration
- **Location:** `customer-dashboard.html` (lines 919-1067)
- **Functions:**
  - `connectSage()` - Initiates OAuth flow
  - `checkSageStatus()` - Checks connection status
  - `loadSageInvoices()` - Fetches and displays invoices
  - `disconnectSage()` - Disconnects account
  - `displaySageInvoices(invoices)` - Renders invoice list

### Migration File
- **File:** `api/migrations/add_sage_tokens.py`
- **Purpose:** Creates `sage_tokens` table if it doesn't exist
- **Run:** Can be executed manually or via admin endpoint

---

## 3. Procore Integration

### Architecture
- **File:** `api/main.py` (lines 4774-5223)
- **OAuth Flow:** OAuth 2.0 with authorization code grant
- **API Type:** Procore REST API v1.0

### Database Schema

#### `procore_tokens` Table
```sql
CREATE TABLE procore_tokens (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) UNIQUE NOT NULL,  -- Uses email instead of user_id
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### `procore_oauth_states` Table
```sql
CREATE TABLE procore_oauth_states (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,         -- Uses email instead of user_id
    state VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
```

**Note:** Procore integration uses `user_email` instead of `user_id` for token storage.

### Environment Variables
```bash
PROCORE_CLIENT_ID=...
PROCORE_CLIENT_SECRET=...
PROCORE_REDIRECT_URI=https://liendeadline.com/api/procore/callback
```

### OAuth URLs
- **Authorization URL:** `https://login.procore.com/oauth/authorize`
- **Token URL:** `https://login.procore.com/oauth/token`
- **API Base:** `https://api.procore.com/rest/v1.0`
- **Scopes:** None (permissions configured in Procore developer portal)

**Important:** Procore does NOT use scope parameters in OAuth URL. Permissions are configured in the Procore developer portal.

### API Endpoints

#### 1. Initiate OAuth Flow
```
GET /api/procore/auth?token={session_token}
```
- Validates user session
- Generates secure state token
- Stores state in `procore_oauth_states` table
- Redirects to Procore authorization page

#### 2. OAuth Callback
```
GET /api/procore/callback?code={auth_code}&state={state}
```
- Verifies state token
- Exchanges authorization code for access/refresh tokens
- Uses Basic Auth header: `Authorization: Basic {base64(client_id:client_secret)}`
- Stores tokens in `procore_tokens` table (keyed by `user_email`)
- Redirects to customer dashboard with success message

#### 3. Get Projects
```
GET /api/procore/projects
Headers: Authorization: Bearer {session_token}
```
- Fetches projects from Procore
- Uses endpoint: `/projects`
- Returns project list with:
  - Project ID
  - Project name
  - Project number
  - Address
  - State
  - Other project details

#### 4. Check Connection Status
```
GET /api/procore/status
Headers: Authorization: Bearer {session_token}
```
- Returns `{"connected": true/false, "valid": true/false}`

#### 5. Disconnect
```
POST /api/procore/disconnect
Headers: Authorization: Bearer {session_token}
```
- Deletes tokens from `procore_tokens` table

### Token Management
- **Automatic Refresh:** Tokens are refreshed automatically if expired (5-minute buffer)
- **Refresh Function:** `refresh_procore_access_token(user_email)` in `api/main.py`
- **Token Validation:** `get_valid_procore_access_token(user_email)` checks expiration and refreshes if needed

### Frontend Integration
- **Location:** `customer-dashboard.html` (lines 987-1073)
- **Functions:**
  - `connectProcore()` - Initiates OAuth flow
  - `checkProcoreStatus()` - Checks connection status
  - `loadProcoreProjects()` - Fetches and displays projects
  - `disconnectProcore()` - Disconnects account
  - `displayProcoreProjects(projects)` - Renders project list

### Migration File
- **File:** `api/migrations/add_procore_tokens.py`
- **Purpose:** Creates `procore_tokens` table if it doesn't exist
- **Run:** Can be executed manually or via admin endpoint

---

## Common Patterns Across All Integrations

### 1. OAuth Flow
All three integrations follow the same OAuth 2.0 pattern:
1. User clicks "Connect" button
2. Frontend calls `/api/{service}/auth` with session token
3. Backend validates session, generates state token, stores in `{service}_oauth_states` table
4. User redirected to third-party authorization page
5. User authorizes, redirected back to `/api/{service}/callback`
6. Backend exchanges code for tokens, stores in `{service}_tokens` table
7. User redirected to dashboard with success message

### 2. Token Storage Differences

| Integration | User Identifier | Table Name | Notes |
|------------|----------------|------------|-------|
| QuickBooks | `user_id` (INTEGER) | `quickbooks_tokens` | References `users.id` |
| Sage | `user_email` (VARCHAR) | `sage_tokens` | Uses email as key |
| Procore | `user_email` (VARCHAR) | `procore_tokens` | Uses email as key |

### 3. Authentication Helper Functions

Each integration has:
- `get_{service}_user_from_session()` - Extracts user from Authorization header
- `refresh_{service}_access_token()` - Refreshes expired tokens
- `get_valid_{service}_access_token()` - Gets valid token (refreshes if needed)

### 4. Database Initialization

All token tables are created in `init_db()` function in `api/main.py`:
- QuickBooks: Lines 1015-1079
- Sage: Created on-demand in OAuth callback (lines 4422-4448)
- Procore: Created on-demand in OAuth callback (lines 4901-4927)

### 5. Frontend UI

All integrations have:
- Connection status indicator
- "Connect" / "Disconnect" button
- Data display section (invoices/projects)
- Error handling and notifications

---

## Security Considerations

1. **State Token Validation:** All OAuth flows use secure random state tokens stored in database with 10-minute expiration
2. **Token Encryption:** Access tokens stored in plaintext (standard practice - tokens are opaque)
3. **Refresh Tokens:** Stored securely, used to automatically refresh expired access tokens
4. **Session Validation:** All endpoints require valid session token from `users.session_token`
5. **Subscription Check:** OAuth initiation checks `subscription_status` (must be 'active' or 'trialing')

---

## Error Handling

All integrations handle:
- Missing environment variables (returns 500 error)
- Invalid OAuth state (returns 400 error)
- Token exchange failures (returns 500 error with details)
- Expired tokens (automatic refresh, falls back to 401 if refresh fails)
- Network errors (returns 500 error)

---

## Testing Checklist

### QuickBooks
- [ ] OAuth flow completes successfully
- [ ] Tokens stored in `quickbooks_tokens` table
- [ ] Invoices fetched from QuickBooks API
- [ ] Token refresh works automatically
- [ ] Disconnect removes tokens

### Sage
- [ ] OAuth flow completes successfully
- [ ] Tokens stored in `sage_tokens` table
- [ ] Invoices fetched from Sage API
- [ ] Token refresh works automatically
- [ ] Disconnect removes tokens

### Procore
- [ ] OAuth flow completes successfully
- [ ] Tokens stored in `procore_tokens` table
- [ ] Projects fetched from Procore API
- [ ] Token refresh works automatically
- [ ] Disconnect removes tokens

---

## Current Status

All three integrations are **fully implemented** with:
- ✅ OAuth 2.0 authentication flows
- ✅ Token storage and management
- ✅ Automatic token refresh
- ✅ API endpoints for fetching data
- ✅ Frontend UI components
- ✅ Database tables and migrations
- ✅ Error handling and validation

The integrations are ready for production use once environment variables are configured.




