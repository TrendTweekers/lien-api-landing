# LienDeadline.com - Technical Handoff Documentation

**Document Version:** 1.0  
**Last Updated:** December 27, 2025  
**Created By:** Development Team  
**Next Review:** January 2026

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture & Tech Stack](#2-architecture--tech-stack)
3. [Database Schema](#3-database-schema)
4. [API Documentation](#4-api-documentation)
5. [Frontend Structure](#5-frontend-structure)
6. [OAuth Integrations](#6-oauth-integrations)
7. [Current Implementation Status](#7-current-implementation-status)
8. [Known Issues & Bugs](#8-known-issues--bugs)
9. [Pending Tasks](#9-pending-tasks)
10. [Deployment Guide](#10-deployment-guide)
11. [Environment Variables Reference](#11-environment-variables-reference)
12. [Testing & Quality Assurance](#12-testing--quality-assurance)
13. [Security Considerations](#13-security-considerations)
14. [Developer Notes](#14-developer-notes)
15. [Contacts & Resources](#15-contacts--resources)

---

## 1. PROJECT OVERVIEW

### What is LienDeadline?

LienDeadline.com is a SaaS platform that helps construction material suppliers and contractors calculate mechanics lien filing deadlines accurately across all 50 US states. The platform provides:

- **Automated deadline calculations** based on state-specific lien laws
- **OAuth integrations** with QuickBooks, Sage, and Procore for seamless workflow
- **Email reminders** to prevent missed deadlines
- **PDF generation** for professional deadline reports
- **REST API** for programmatic access
- **Partner/referral program** for business growth

### Target Market

- Material suppliers (primary)
- General contractors
- Subcontractors
- Construction attorneys
- Property developers

### Value Proposition

**Problem:** Construction companies lose millions annually due to missed lien deadlines, which are complex and vary by state.

**Solution:** LienDeadline provides accurate, state-specific deadline calculations with automated reminders and integrations with popular accounting/project management software.

### Key Features

- ✅ Lien deadline calculator (all 50 US states)
- ✅ QuickBooks OAuth integration
- ✅ Sage OAuth integration
- ✅ Procore OAuth integration
- ✅ Email reminders (7 days and 1 day before deadlines)
- ✅ PDF generation for deadline reports
- ✅ REST API with API key authentication
- ✅ Partner/referral program
- ✅ Customer dashboard
- ✅ Broker/partner dashboard
- ✅ Admin dashboard

---

## 2. ARCHITECTURE & TECH STACK

### Backend Architecture

```
/api
├── main.py              # Main FastAPI application (11,273 lines)
├── calculations.py      # Calculation endpoints and user auth
├── quickbooks.py        # QuickBooks OAuth integration
├── database.py          # Database connection utilities
├── calculators.py       # State-specific calculation logic
├── rate_limiter.py      # API rate limiting
└── migrations/          # Database migrations
    ├── add_all_states.py
    ├── add_calculations_tables.py
    ├── add_sage_tokens.py
    ├── add_procore_tokens.py
    └── fix_production_database.py
```

### Frontend Structure

```
/public
├── index.html           # Landing page
├── customer-dashboard.html
├── broker-dashboard.html
├── partners.html
├── comparison.html
├── features.html
├── state-coverage.html
├── images/
│   └── lien-deadline-preview.jpg
├── favicon files (apple-touch-icon, favicon-*.png, etc.)
└── site.webmanifest
```

**Note:** No separate CSS/JS files - all inline in HTML files for simplicity.

### Technology Stack

**Backend:**
- **Framework:** FastAPI 0.104.1 (Python 3.11)
- **ASGI Server:** Uvicorn 0.24.0
- **Database:** PostgreSQL (production) / SQLite (local dev)
- **ORM:** None (raw SQL with psycopg2/sqlite3)
- **Authentication:** Session tokens (stored in `users.session_token`)
- **Password Hashing:** bcrypt 4.1.2
- **PDF Generation:** ReportLab 4.0.7
- **Email:** Resend API 2.4.0
- **Payments:** Stripe 7.8.0
- **Rate Limiting:** slowapi 0.1.9

**Frontend:**
- **HTML/CSS/JS:** Vanilla (no framework)
- **Styling:** Tailwind CSS (CDN)
- **PDF Client-side:** jsPDF (CDN)

**Infrastructure:**
- **Hosting:** Railway.app
- **Domain:** liendeadline.com (Namecheap)
- **SSL:** Automatic (Railway)
- **Database:** Railway PostgreSQL

**External APIs:**
- **QuickBooks:** Intuit OAuth 2.0
- **Sage:** Sage Intacct OAuth 2.0
- **Procore:** Procore OAuth 2.0
- **Resend:** Email delivery
- **Stripe:** Payment processing

---

## 3. DATABASE SCHEMA

### Database Type

- **Production:** PostgreSQL (Railway)
- **Local Development:** SQLite (`liendeadline.db`)

### Core Tables

#### `users` Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    stripe_customer_id VARCHAR(255),
    subscription_status VARCHAR(50) DEFAULT 'inactive',
    subscription_id VARCHAR(255),
    session_token VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_session_token ON users(session_token);
CREATE INDEX idx_users_subscription_status ON users(subscription_status);
```

**Columns:**
- `id`: Auto-incrementing primary key
- `email`: Unique user email (login)
- `password_hash`: bcrypt hashed password
- `stripe_customer_id`: Stripe customer ID for billing
- `subscription_status`: 'active', 'trialing', 'inactive', 'canceled'
- `subscription_id`: Stripe subscription ID
- `session_token`: JWT-like token for session management
- `created_at`, `updated_at`, `last_login_at`: Timestamps

#### `calculations` Table

```sql
CREATE TABLE calculations (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    invoice_amount DECIMAL(12,2),
    notes TEXT,
    state VARCHAR(100) NOT NULL,
    state_code VARCHAR(2) NOT NULL,
    invoice_date DATE NOT NULL,
    prelim_deadline DATE,
    prelim_deadline_days INTEGER,
    lien_deadline DATE NOT NULL,
    lien_deadline_days INTEGER NOT NULL,
    quickbooks_invoice_id VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP
);

CREATE INDEX idx_calculations_user_email ON calculations(user_email);
CREATE INDEX idx_calculations_created_at ON calculations(created_at DESC);
```

**Purpose:** Stores user's saved calculations/projects.

#### `email_reminders` Table

```sql
CREATE TABLE email_reminders (
    id SERIAL PRIMARY KEY,
    calculation_id INTEGER NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    client_name VARCHAR(255) NOT NULL,
    invoice_amount DECIMAL(12,2),
    state VARCHAR(100) NOT NULL,
    notes TEXT,
    deadline_type VARCHAR(20) NOT NULL,  -- 'prelim' or 'lien'
    deadline_date DATE NOT NULL,
    days_before INTEGER NOT NULL,  -- 7 or 1
    send_date DATE NOT NULL,
    alert_sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reminders_send_date ON email_reminders(send_date, alert_sent);
CREATE INDEX idx_reminders_user_email ON email_reminders(user_email);
CREATE INDEX idx_reminders_calculation_id ON email_reminders(calculation_id);
```

**Purpose:** Stores email reminder schedules. Cron job (`api/cron_send_reminders.py`) sends reminders when `send_date` arrives.

#### `lien_deadlines` Table

```sql
CREATE TABLE lien_deadlines (
    id SERIAL PRIMARY KEY,
    state_code VARCHAR(2) UNIQUE NOT NULL,
    state_name VARCHAR(50) NOT NULL,
    preliminary_notice_required BOOLEAN DEFAULT FALSE,
    preliminary_notice_days INTEGER,
    preliminary_notice_formula TEXT,
    preliminary_notice_deadline_description TEXT,
    preliminary_notice_statute TEXT,
    lien_filing_days INTEGER,
    lien_filing_formula TEXT,
    lien_filing_deadline_description TEXT,
    lien_filing_statute TEXT,
    weekend_extension BOOLEAN DEFAULT FALSE,
    holiday_extension BOOLEAN DEFAULT FALSE,
    residential_vs_commercial BOOLEAN DEFAULT FALSE,
    notice_of_completion_trigger BOOLEAN DEFAULT FALSE,
    notes TEXT,
    last_updated TIMESTAMP DEFAULT NOW()
);
```

**Purpose:** Stores state-specific lien rules. Populated by `api/migrations/add_all_states.py`.

### OAuth Token Tables

#### `quickbooks_tokens` Table

```sql
CREATE TABLE quickbooks_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    realm_id VARCHAR(255),  -- QuickBooks company ID
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_qb_tokens_user_email ON quickbooks_tokens(user_email);
```

**Migration:** Created via `api/migrations/add_quickbooks_tokens.py` (if exists) or manually.

#### `sage_tokens` Table

```sql
CREATE TABLE sage_tokens (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    realm_id VARCHAR(255),
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Migration:** Run via `GET /api/admin/run-sage-migration`

#### `procore_tokens` Table

```sql
CREATE TABLE procore_tokens (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Migration:** Run via `GET /api/admin/run-procore-migration`

### OAuth State Tables

Temporary tables for OAuth flow state management:

- `quickbooks_oauth_states` - Stores OAuth state tokens for QuickBooks
- `sage_oauth_states` - Stores OAuth state tokens for Sage
- `procore_oauth_states` - Stores OAuth state tokens for Procore

**Structure:**
```sql
CREATE TABLE {integration}_oauth_states (
    id SERIAL PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    state VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL
);
```

**Purpose:** Prevents CSRF attacks during OAuth flow. States expire after 10 minutes.

### Partner/Broker Tables

#### `brokers` Table

```sql
CREATE TABLE brokers (
    id TEXT PRIMARY KEY,  -- Referral code
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    commission REAL DEFAULT 500.00,
    referrals INTEGER DEFAULT 0,
    earned REAL DEFAULT 0.00,
    status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `referrals` Table

```sql
CREATE TABLE referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_id TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_id TEXT,
    amount REAL,
    payout REAL,
    status TEXT DEFAULT 'pending',  -- 'pending', 'paid', 'on_hold'
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (broker_id) REFERENCES brokers(id)
);
```

### Other Tables

- `customers` - Legacy customer tracking (may be deprecated)
- `api_keys` - API key management (if implemented)
- `api_logs` - API usage logging (if implemented)
- `partner_applications` - Broker application queue

---

## 4. API DOCUMENTATION

### Base URL

- **Production:** `https://liendeadline.com`
- **Local:** `http://localhost:8000`

### Authentication

Most endpoints require authentication via session token:

```
Authorization: Bearer {session_token}
```

Session tokens are obtained via `/api/login` and stored in `localStorage` on the frontend.

### Public Endpoints

#### `POST /api/v1/calculate-deadline`

Calculate lien deadlines for a specific state.

**Request:**
```json
{
  "state": "TX",
  "invoice_date": "2025-12-27",
  "role": "supplier",
  "project_type": "commercial",  // optional
  "notice_of_completion_date": null,  // optional
  "notice_of_commencement_filed": false  // optional
}
```

**Response:**
```json
{
  "state": "Texas",
  "state_code": "TX",
  "preliminary_notice_required": true,
  "preliminary_deadline": "2026-01-11",
  "prelim_days_remaining": 15,
  "lien_deadline": "2026-04-15",
  "lien_days_remaining": 109,
  "preliminary_notice": {
    "name": "Preliminary Notice Deadline",
    "deadline": "2026-01-11",
    "days_from_now": 15,
    "urgency": "moderate",
    "description": "Must be sent within 15 days of first delivery"
  },
  "lien_filing": {
    "name": "Lien Filing Deadline",
    "deadline": "2026-04-15",
    "days_from_now": 109,
    "urgency": "low",
    "description": "Must be filed within 15th day of 4th month"
  }
}
```

#### `GET /api/v1/guide/{state_code}/pdf`

Generate PDF guide for a state.

**Query Parameters:**
- `invoice_date` (optional): Date in `YYYY-MM-DD` or `MM/DD/YYYY` format
- `state_name` (optional): Full state name for display

**Response:** PDF file (binary)

**Example:**
```
GET /api/v1/guide/TX/pdf?invoice_date=2025-12-27
```

#### `GET /api/v1/states`

List all supported states.

**Response:**
```json
{
  "states": [
    {"code": "TX", "name": "Texas"},
    {"code": "CA", "name": "California"},
    ...
  ]
}
```

### Authentication Endpoints

#### `POST /api/login`

Login with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "email": "user@example.com",
    "subscription_status": "active"
  }
}
```

#### `POST /api/signup`

Create new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:** Same as `/api/login`

#### `GET /api/verify-session`

Verify current session token.

**Headers:**
```
Authorization: Bearer {session_token}
```

**Response:**
```json
{
  "valid": true,
  "user": {
    "email": "user@example.com",
    "subscription_status": "active"
  }
}
```

#### `POST /api/logout`

Logout (invalidate session token).

**Headers:**
```
Authorization: Bearer {session_token}
```

**Response:**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

### Calculation Endpoints (Authenticated)

#### `POST /api/calculations/save`

Save a calculation as a project.

**Headers:**
```
Authorization: Bearer {session_token}
```

**Request:**
```json
{
  "projectName": "Downtown Office Building",
  "clientName": "ABC Construction",
  "invoiceAmount": 50000.00,
  "notes": "First delivery",
  "state": "Texas",
  "stateCode": "TX",
  "invoiceDate": "2025-12-27",
  "prelimDeadline": "2026-01-11",
  "prelimDeadlineDays": 15,
  "lienDeadline": "2026-04-15",
  "lienDeadlineDays": 109,
  "reminders": {
    "prelim7": true,
    "prelim1": true,
    "lien7": true,
    "lien1": false
  },
  "quickbooksInvoiceId": null
}
```

**Response:**
```json
{
  "success": true,
  "calculation_id": 123,
  "message": "Calculation saved successfully"
}
```

#### `GET /api/calculations/history`

Get user's saved calculations.

**Headers:**
```
Authorization: Bearer {session_token}
```

**Response:**
```json
{
  "calculations": [
    {
      "id": 123,
      "project_name": "Downtown Office Building",
      "client_name": "ABC Construction",
      "state": "Texas",
      "state_code": "TX",
      "invoice_date": "2025-12-27",
      "prelim_deadline": "2026-01-11",
      "lien_deadline": "2026-04-15",
      "created_at": "2025-12-27T10:00:00Z"
    },
    ...
  ]
}
```

### OAuth Integration Endpoints

#### QuickBooks

**`GET /api/quickbooks/connect`**

Initiate QuickBooks OAuth flow.

**Query Parameters:**
- `token` (required): User session token

**Response:** Redirects to QuickBooks authorization page

**`GET /api/quickbooks/callback`**

Handle QuickBooks OAuth callback.

**Query Parameters:**
- `code`: Authorization code from QuickBooks
- `state`: OAuth state token
- `realmId`: QuickBooks company ID

**Response:** Redirects to `/customer-dashboard.html?quickbooks_connected=true`

**`GET /api/quickbooks/status`**

Check QuickBooks connection status.

**Headers:**
```
Authorization: Bearer {session_token}
```

**Response:**
```json
{
  "connected": true,
  "realm_id": "123456789"
}
```

**`POST /api/quickbooks/disconnect`**

Disconnect QuickBooks account.

**Headers:**
```
Authorization: Bearer {session_token}
```

**Response:**
```json
{
  "success": true,
  "message": "QuickBooks account disconnected"
}
```

**`GET /api/quickbooks/invoices`**

Fetch invoices from QuickBooks (if implemented).

**Headers:**
```
Authorization: Bearer {session_token}
```

#### Sage

**`GET /api/sage/auth`**

Initiate Sage OAuth flow.

**Query Parameters:**
- `token` (required): User session token

**Response:** Redirects to Sage Intacct authorization page

**`GET /api/sage/callback`**

Handle Sage OAuth callback.

**Query Parameters:**
- `code`: Authorization code from Sage
- `state`: OAuth state token

**Response:** Redirects to `/customer-dashboard.html?sage_connected=true`

**`GET /api/sage/status`**

Check Sage connection status.

**Headers:**
```
Authorization: Bearer {session_token}
```

**Response:**
```json
{
  "connected": true
}
```

**`POST /api/sage/disconnect`**

Disconnect Sage account.

**Headers:**
```
Authorization: Bearer {session_token}
```

**`GET /api/sage/invoices`**

Fetch invoices from Sage (if implemented).

#### Procore

**`GET /api/procore/auth`**

Initiate Procore OAuth flow.

**Query Parameters:**
- `token` (required): User session token

**Response:** Redirects to Procore authorization page

**`GET /api/procore/callback`**

Handle Procore OAuth callback.

**Query Parameters:**
- `code`: Authorization code from Procore
- `state`: OAuth state token

**Response:** Redirects to `/customer-dashboard.html?procore_connected=true`

**`GET /api/procore/status`**

Check Procore connection status.

**Headers:**
```
Authorization: Bearer {session_token}
```

**Response:**
```json
{
  "connected": true
}
```

**`POST /api/procore/disconnect`**

Disconnect Procore account.

**Headers:**
```
Authorization: Bearer {session_token}
```

**`GET /api/procore/projects`**

Fetch projects from Procore (if implemented).

**Headers:**
```
Authorization: Bearer {session_token}
```

### Admin Endpoints

**Authentication:** HTTP Basic Auth
- Username: `ADMIN_USER` env var (default: `admin`)
- Password: `ADMIN_PASS` env var (default: `LienAPI2025`)

#### `GET /api/admin/run-sage-migration`

Run Sage tokens table migration.

**Response:**
```json
{
  "success": true,
  "message": "sage_tokens table created successfully"
}
```

#### `GET /api/admin/run-procore-migration`

Run Procore tokens table migration.

**Response:**
```json
{
  "success": true,
  "message": "procore_tokens table created successfully"
}
```

#### `GET /api/admin/run-state-migration`

Run state data migration (updates deadline_days for 6 states).

**Response:**
```json
{
  "success": true,
  "message": "State migration completed successfully",
  "states_updated": ["IN", "LA", "MA", "NJ", "OH", "TX"]
}
```

**Note:** Many more admin endpoints exist for broker management, payment tracking, etc. See `api/main.py` for full list.

---

## 5. FRONTEND STRUCTURE

### Landing Page (`index.html`)

**Location:** `public/index.html` (served at `/`)

**Features:**
- Hero section with value proposition
- Features section
- State coverage section
- Pricing preview
- FAQ section
- Calculator embed
- Email capture for state expansion waitlist

**JavaScript:**
- Calculator functionality (inline)
- Email capture handling
- UTM parameter tracking

### Customer Dashboard (`customer-dashboard.html`)

**Location:** `public/customer-dashboard.html` (served at `/customer-dashboard`)

**Features:**
- **Account Overview:** User email, subscription status
- **Calculate New Deadline:** Embedded calculator
- **Your Projects:** Table of saved calculations
- **Accounting Integrations:** QuickBooks, Sage, Procore cards
- **API Key Management:** Generate/view API keys
- **Usage Statistics:** API call counts
- **Billing Information:** Stripe customer portal link
- **Partner Program Promotion:** Referral program CTA

**JavaScript Functions:**
- `checkQuickBooksStatus()` - Check QuickBooks connection
- `connectQuickBooks()` - Initiate QuickBooks OAuth
- `disconnectQuickBooks()` - Disconnect QuickBooks
- `checkSageStatus()` - Check Sage connection
- `connectSage()` - Initiate Sage OAuth
- `disconnectSage()` - Disconnect Sage
- `checkProcoreStatus()` - Check Procore connection
- `connectProcore()` - Initiate Procore OAuth
- `disconnectProcore()` - Disconnect Procore
- `loadCalculations()` - Load saved projects
- `saveCalculation()` - Save new calculation
- `reportIntegrationIssue()` - Report OAuth issues

**Authentication:**
- Checks `localStorage.session_token` on page load
- Redirects to `/dashboard` if not logged in
- Handles OAuth callbacks via query parameters

### Broker Dashboard (`broker-dashboard.html`)

**Location:** `public/broker-dashboard.html` (served at `/broker-dashboard`)

**Features:**
- Referral link generation
- Referral tracking
- Commission earnings display
- Payment information form
- Password change

### Partners Page (`partners.html`)

**Location:** `public/partners.html` (served at `/partners`)

**Features:**
- Partner program overview
- Commission structure (bounty vs recurring)
- Application form
- Benefits list

### Other Pages

- `comparison.html` - Comparison with competitors
- `features.html` - Feature list
- `state-coverage.html` - State coverage map/list
- `terms.html` - Terms of service
- `privacy.html` - Privacy policy
- `help.html` - Help/FAQ

---

## 6. OAUTH INTEGRATIONS

### QuickBooks Integration

**Status:** ✅ Working (connected successfully)

**OAuth Flow:**
1. User clicks "Connect QuickBooks" in dashboard
2. Frontend redirects to `/api/quickbooks/connect?token={session_token}`
3. Backend validates token, generates OAuth state, stores in `quickbooks_oauth_states`
4. Backend redirects to Intuit authorization page with `client_id`, `scope`, `redirect_uri`, `state`, `locale=en_US`
5. User authorizes → Intuit redirects to `/api/quickbooks/callback?code={auth_code}&state={state}&realmId={company_id}`
6. Backend verifies state, exchanges code for tokens via Basic Auth
7. Backend saves tokens to `quickbooks_tokens` table
8. Backend redirects to `/customer-dashboard.html?quickbooks_connected=true`

**Credentials (Railway env vars):**
```
QUICKBOOKS_CLIENT_ID=ABRV9aq09aCvEFIGKNZp4utAydOjYUPuJmmLIaV9LogeqdlysS
QUICKBOOKS_CLIENT_SECRET=MLFX7R2VmYWsTen8O6qKqvStOCb1NxYr6KSfgdxm
QUICKBOOKS_REDIRECT_URI=https://liendeadline.com/api/quickbooks/callback
```

**OAuth URLs:**
- Authorization: `https://appcenter.intuit.com/connect/oauth2`
- Token: `https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer`
- API Base: `https://quickbooks.api.intuit.com/v3`
- Scopes: `com.intuit.quickbooks.accounting`

**Code Location:**
- Endpoints: `api/quickbooks.py`
- Database: `quickbooks_tokens` table
- Frontend: `customer-dashboard.html` (QuickBooks card)

**Known Issues:**
- ✅ [FIXED] Locale parameter issue (Swedish locale caused "undefined" error) - Fixed by adding `locale: "en_US"`
- ✅ [FIXED] Button text shows "Disconnect" when connected (was showing "Reconnect")

**Token Refresh:**
- Tokens expire after 1 hour (QuickBooks default)
- Refresh logic implemented in `get_valid_quickbooks_access_token()` helper
- Uses `refresh_token` to get new `access_token` automatically

---

### Sage Integration

**Status:** ⚠️ OAuth working, needs Sage Intacct account to test fully

**OAuth Flow:**
1. User clicks "Connect Sage" in dashboard
2. Frontend redirects to `/api/sage/auth?token={session_token}`
3. Backend validates token, generates OAuth state, stores in `sage_oauth_states`
4. Backend redirects to Sage Intacct authorization page
5. User authorizes → Sage redirects to `/api/sage/callback?code={auth_code}&state={state}`
6. Backend verifies state, exchanges code for tokens via Basic Auth
7. Backend saves tokens to `sage_tokens` table
8. Backend redirects to `/customer-dashboard.html?sage_connected=true`

**Credentials:**
```
SAGE_CLIENT_ID=Ka4F3opf0BgcYG9kqcGOa8hqvVJv4qJl
SAGE_CLIENT_SECRET=/rdnRb68xgPxlnLvLU4vOobrAphZl5Zz4Rxa0HHM
SAGE_REDIRECT_URI=https://liendeadline.com/api/sage/callback
```

**OAuth URLs:**
- Authorization: `https://api.intacct.com/ia/api/v1/oauth2/authorize`
- Token: `https://api.intacct.com/ia/api/v1/oauth2/token`
- API Base: `https://api.intacct.com`
- Scopes: `read write` (Sage Intacct doesn't use scopes in URL, but API requires them)

**Code Location:**
- Endpoints: `api/main.py` (lines ~10479-10800)
- Database: `sage_tokens` table
- Frontend: `customer-dashboard.html` (Sage card)

**Known Issues:**
- ✅ [FIXED] Wrong endpoints (was using Sage Business Cloud, now uses Sage Intacct)
- ✅ [FIXED] Swedish locale issue (removed `country=us` parameter)
- ⚠️ [PENDING] Requires actual Sage Intacct subscription to fully test API calls

**Important Notes:**
- Sage Operations API uses Sage Intacct OAuth 2.0 infrastructure
- No `scope` parameter in authorization URL (permissions configured in developer portal)
- Token exchange requires Basic Auth header (`Authorization: Basic {base64(client_id:client_secret)}`)

---

### Procore Integration

**Status:** ✅ Working (connected successfully)

**OAuth Flow:**
1. User clicks "Connect Procore" in dashboard
2. Frontend redirects to `/api/procore/auth?token={session_token}`
3. Backend validates token, generates OAuth state, stores in `procore_oauth_states`
4. Backend redirects to Procore authorization page
5. User authorizes → Procore redirects to `/api/procore/callback?code={auth_code}&state={state}`
6. Backend verifies state, exchanges code for tokens via Basic Auth
7. Backend saves tokens to `procore_tokens` table
8. Backend redirects to `/customer-dashboard.html?procore_connected=true`

**Credentials:**
```
PROCORE_CLIENT_ID=xBZ__1B9C31iDRMphjjT6yCXOnFucFJovcfJK9okCEE
PROCORE_CLIENT_SECRET=l0u7NuRyOS24neB-ZRuJUQMTyUIEsUlcVyZbMiczUWE
PROCORE_REDIRECT_URI=https://liendeadline.com/api/procore/callback
```

**Sandbox Credentials (for testing):**
```
PROCORE_SANDBOX_CLIENT_ID=gmfqRS3337q1c9tCJMXvKdC-OhVbwpWtTfiqz7FY1Wrg
PROCORE_SANDBOX_CLIENT_SECRET=yJQXWp2fb6Zgoha8MTMmUa1j6nhSiREaj66yKY4fVNs
PROCORE_SANDBOX_URL=https://sandbox.procore.com/4279807/company/home
```

**OAuth URLs:**
- Authorization: `https://login.procore.com/oauth/authorize`
- Token: `https://login.procore.com/oauth/token`
- API Base: `https://api.procore.com/rest/v1.0`

**Code Location:**
- Endpoints: `api/main.py` (lines ~10898-11250)
- Database: `procore_tokens` table
- Frontend: `customer-dashboard.html` (Procore card)

**Known Issues:**
- ✅ [FIXED] Scope parameter error (Procore doesn't use scopes) - Removed `scope` parameter
- ✅ [FIXED] Token exchange needed Basic Auth header - Fixed to use `Authorization: Basic {base64}`

**Important Notes:**
- Procore OAuth 2.0 does NOT use scope parameters
- Permissions are configured in Procore developer portal
- Token exchange requires Basic Auth header (`Authorization: Basic {base64(client_id:client_secret)}`)
- Do NOT include `client_id`/`client_secret` in POST body during token exchange

---

## 7. CURRENT IMPLEMENTATION STATUS

### ✅ COMPLETED FEATURES

**Core Functionality:**
- [x] Lien deadline calculator (all 50 states)
- [x] User authentication (signup, login, sessions)
- [x] Project saving with email reminders
- [x] Calculation history
- [x] PDF generation (⚠️ has bugs, see Known Issues)
- [x] Email reminders system (cron job: `api/cron_send_reminders.py`)

**OAuth Integrations:**
- [x] QuickBooks OAuth flow (connect/disconnect working)
- [x] Sage OAuth flow (connect/disconnect working)
- [x] Procore OAuth flow (connect/disconnect working)
- [x] Token storage and refresh logic
- [x] Connection status indicators
- [x] Disconnect functionality

**UI/UX:**
- [x] Landing page (`index.html`)
- [x] Customer dashboard (`customer-dashboard.html`)
- [x] Broker/partner dashboard (`broker-dashboard.html`)
- [x] Partners page (`partners.html`)
- [x] Comparison page (`comparison.html`)
- [x] Features page (`features.html`)
- [x] State coverage page (`state-coverage.html`)
- [x] Responsive design (Tailwind CSS)
- [x] Custom favicon
- [x] Professional branding

**Infrastructure:**
- [x] Railway deployment
- [x] PostgreSQL database
- [x] Environment variables configured
- [x] Domain setup (liendeadline.com)
- [x] SSL certificate (automatic via Railway)
- [x] Email service (Resend)
- [x] Static file serving (FastAPI StaticFiles)

---

### ⚠️ PARTIALLY COMPLETE

**QuickBooks Integration:**
- [x] OAuth connection working
- [ ] Invoice fetching implementation
- [ ] Automatic deadline calculation from invoices
- [ ] Sync functionality

**Sage Integration:**
- [x] OAuth flow complete
- [ ] Needs actual Sage Intacct account to test API calls
- [ ] Invoice/data fetching implementation
- [ ] Sync functionality

**Procore Integration:**
- [x] OAuth connection working
- [ ] Project fetching implementation
- [ ] Project data sync
- [ ] Deadline automation from project data

**Email Reminders:**
- [x] Database schema complete
- [x] Cron job script created (`api/cron_send_reminders.py`)
- [ ] Cron job configured in Railway (pending)
- [ ] Email templates (basic implementation)

---

### ❌ NOT STARTED / PENDING

**Critical Bugs to Fix:**
1. **PDF Logic Mismatch** ⚠️ HIGH PRIORITY (see Known Issues)

**Missing Features:**
1. **Pricing Page**
   - Create `/public/pricing.html`
   - Add to navigation menu
   - Stripe payment integration

2. **Blog / State Lien Guides**
   - Create `/public/blog/` directory structure
   - Individual state guides (50 pages)
   - SEO optimization for state-specific searches
   - Template: `/blog/[state]-lien-deadlines.html`

3. **Integrations Showcase**
   - Add section to landing page
   - Text-based (no official logos)
   - "Works with QuickBooks, Sage, Procore"

4. **API Key Management**
   - Generate API keys for users
   - Rate limiting per API key
   - Usage tracking

5. **Invoice/Project Import**
   - Fetch invoices from QuickBooks
   - Fetch invoices from Sage
   - Fetch projects from Procore
   - Auto-calculate deadlines from imported data

---

## 8. KNOWN ISSUES & BUGS

### 🔴 CRITICAL (Fix Immediately)

#### 1. PDF Logic Mismatch

**Issue:** PDF generator (`/api/v1/guide/{state}/pdf`) may use different calculation logic than live calculator (`/api/v1/calculate-deadline`), potentially producing incorrect deadlines.

**Impact:** Legal liability - customers could get wrong deadlines in PDFs.

**Example:** Utah shows "Not Required" in PDF but calculator shows "Jan 16, 2026"

**Root Cause:** PDF generation function (`generate_state_guide_pdf` in `api/main.py` line ~1571) was recently refactored to use the same calculation logic as the calculator endpoint, but there may still be edge cases.

**Current Status:**
- PDF generator now calls the same calculator functions (`calculate_texas`, `calculate_washington`, etc.)
- Audit script created (`scripts/auditPDFvsCalculator.js`) to verify consistency
- Script needs to be run to verify all states match

**Fix Required:**
1. Run audit script: `node scripts/auditPDFvsCalculator.js`
2. Compare PDF output vs calculator for all 50 states
3. Fix any mismatches found
4. Ensure PDF always calls the same calculation endpoint or uses identical logic

**Location:** `api/main.py` lines ~1571-2122 (`generate_state_guide_pdf` function)

**Testing:**
```bash
# Test calculator
curl -X POST http://localhost:8000/api/v1/calculate-deadline \
  -H "Content-Type: application/json" \
  -d '{"state":"UT","invoice_date":"2025-12-27","role":"supplier"}'

# Test PDF
curl "http://localhost:8000/api/v1/guide/UT/pdf?invoice_date=2025-12-27" \
  --output utah-test.pdf

# Compare dates in both outputs
```

---

### 🟡 MEDIUM (Fix Soon)

#### 2. QuickBooks Button Text (FIXED)

**Issue:** Button showed "Reconnect" when should show "Disconnect" when connected.

**Status:** ✅ Fixed - Button now shows "Disconnect" with red styling when connected.

**Location:** `customer-dashboard.html` (QuickBooks card JavaScript)

---

#### 3. Favicon Not Showing

**Issue:** Favicon files deployed but returning 404 errors.

**Status:** Files exist in `public/` directory, FastAPI configured to serve static files.

**Possible Causes:**
- Browser cache (hard refresh required: Ctrl+F5)
- Static file mount order (should be last, after API routes)
- File path case sensitivity

**Fix:** Verify static file serving in `api/main.py`:
```python
# Should be LAST mount, after all API routes
app.mount("/", StaticFiles(directory=str(public_dir), html=True), name="public")
```

**Location:** `api/main.py` (end of file, after all route definitions)

---

#### 4. Integration Invoice/Project Fetching

**Issue:** OAuth works, but not fetching actual invoices/projects from integrations.

**Impact:** Users can connect but can't import data.

**Next Steps:**
- Implement QuickBooks invoice fetching (`GET /api/quickbooks/invoices`)
- Implement Sage invoice fetching (`GET /api/sage/invoices`)
- Implement Procore project fetching (`GET /api/procore/projects`)

**Location:** 
- QuickBooks: `api/quickbooks.py` (line ~466)
- Sage: `api/main.py` (line ~10778)
- Procore: `api/main.py` (line ~11212)

---

### 🟢 LOW (Nice to Have)

#### 5. Dashboard Layout on Mobile

**Issue:** Integration cards could stack better on mobile devices.

**Fix:** Improve responsive CSS in `customer-dashboard.html`

---

#### 6. Error Messages

**Issue:** Generic error messages ("An error occurred") don't help users debug.

**Fix:** More specific, actionable error messages throughout the application.

---

## 9. PENDING TASKS

### Priority 1 (Critical - Do First)

#### Fix PDF Logic Mismatch

- [ ] Run audit script: `node scripts/auditPDFvsCalculator.js`
- [ ] Verify all 50 states match between calculator and PDF
- [ ] Fix any mismatches found
- [ ] Add automated test to prevent future mismatches

**Estimated Time:** 4-8 hours

---

#### Complete QuickBooks Integration

- [ ] Implement invoice fetching (`GET /api/quickbooks/invoices`)
- [ ] Parse invoice data (date, amount, project)
- [ ] Auto-calculate deadlines from invoices
- [ ] Display invoices in dashboard
- [ ] Allow user to select invoice and calculate deadline

**Estimated Time:** 8-16 hours

---

#### Complete Procore Integration

- [ ] Implement project fetching (`GET /api/procore/projects`)
- [ ] Parse project data (start date, completion date, etc.)
- [ ] Auto-calculate deadlines from project dates
- [ ] Display projects in dashboard
- [ ] Allow user to select project and calculate deadline

**Estimated Time:** 8-16 hours

---

### Priority 2 (Important - Do Soon)

#### Create Pricing Page

- [ ] Create `/public/pricing.html`
- [ ] Add to navigation menu (all pages)
- [ ] Design 3 tiers: Basic, Pro, Enterprise
- [ ] Integrate Stripe payment buttons
- [ ] Add pricing comparison table

**Estimated Time:** 4-8 hours

---

#### Fix Dashboard UI Issues

- [ ] Button text consistency (all integrations)
- [ ] Integration card layout improvements
- [ ] Mobile responsiveness
- [ ] Loading states for async operations
- [ ] Error message display

**Estimated Time:** 4-8 hours

---

#### Add Partner Program Promotion

- [ ] Section in `customer-dashboard.html` (already added, verify)
- [ ] Links to `partners.html`
- [ ] Encourages customer → partner conversion
- [ ] Track conversion metrics

**Estimated Time:** 2-4 hours

---

### Priority 3 (Enhancements - Do Later)

#### Create Blog / State Guides

- [ ] Create `/public/blog/` directory structure
- [ ] Generate 50 state-specific pages
- [ ] SEO optimization (meta tags, keywords)
- [ ] Internal linking structure
- [ ] Template: `blog/[state]-mechanics-lien-guide.html`

**Estimated Time:** 40-80 hours (1-2 hours per state)

---

#### Add Integrations Section to Landing Page

- [ ] Text-based section (no official logos)
- [ ] "Works with QuickBooks, Sage, Procore"
- [ ] Generic icons (📊 💼 🏗️)
- [ ] Place before pricing section

**Estimated Time:** 2-4 hours

---

#### Improve Email Templates

- [ ] Branded HTML emails
- [ ] Better formatting
- [ ] Reminder emails with deadlines
- [ ] Welcome emails
- [ ] Password reset emails

**Estimated Time:** 4-8 hours

---

#### Analytics Integration

- [ ] Google Analytics
- [ ] Conversion tracking
- [ ] User behavior analysis
- [ ] API usage analytics

**Estimated Time:** 4-8 hours

---

## 10. DEPLOYMENT GUIDE

### Railway Deployment

**Repository:** GitHub (private repo)

**Deployment Process:**
1. Push to GitHub `main` branch
2. Railway auto-detects changes and deploys (~2-3 minutes)
3. Check Railway dashboard for deployment status
4. Verify deployment at `https://liendeadline.com`

**Build Command:** (Railway auto-detects Python)
- Installs dependencies from `requirements.txt`
- Runs `api/requirements.txt` which references root `requirements.txt`

**Start Command:** 
```
uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

**Configuration File:** `railway.toml`
```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "uvicorn api.main:app --host 0.0.0.0 --port $PORT"

[build.nixPacks]
pythonVersion = "3.11"
```

**Database Migrations:**
Run via admin endpoints (HTTP Basic Auth):
- `GET /api/admin/run-sage-migration`
- `GET /api/admin/run-procore-migration`
- `GET /api/admin/run-state-migration`

**Cron Jobs:**
- Email reminders: `api/cron_send_reminders.py`
- Configure in Railway UI (Cron Runs tab)
- Schedule: Daily at 9 AM UTC (`0 9 * * *`)

---

### Local Development Setup

**Prerequisites:**
- Python 3.11+
- Node.js (for audit script)
- PostgreSQL (optional, SQLite works for local dev)

**Steps:**

1. **Clone Repository**
```bash
git clone <repository-url>
cd lien-api-landing
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Set Environment Variables**
Create `.env` file:
```env
DATABASE_URL=postgresql://user:pass@localhost/dbname
# OR use SQLite (default):
# DATABASE_PATH=./liendeadline.db
DB_TYPE=sqlite  # or 'postgresql'

RESEND_API_KEY=re_...
SMTP_FROM_EMAIL=noreply@liendeadline.com

QUICKBOOKS_CLIENT_ID=...
QUICKBOOKS_CLIENT_SECRET=...
QUICKBOOKS_REDIRECT_URI=http://localhost:8000/api/quickbooks/callback

SAGE_CLIENT_ID=...
SAGE_CLIENT_SECRET=...
SAGE_REDIRECT_URI=http://localhost:8000/api/sage/callback

PROCORE_CLIENT_ID=...
PROCORE_CLIENT_SECRET=...
PROCORE_REDIRECT_URI=http://localhost:8000/api/procore/callback
```

4. **Run Migrations**
```bash
# Run state data migration
python -c "from api.migrations.add_all_states import migrate_states; migrate_states()"

# Run calculations tables migration
python api/migrations/add_calculations_tables.py

# Run OAuth token migrations (via admin endpoints after starting server)
```

5. **Start Development Server**
```bash
uvicorn api.main:app --reload --port 8000
```

6. **Access Application**
- API: `http://localhost:8000`
- Landing Page: `http://localhost:8000/`
- Customer Dashboard: `http://localhost:8000/customer-dashboard`

---

### Database Migrations

**Manual Migrations:**

Run via Python:
```bash
python api/migrations/add_all_states.py
python api/migrations/add_calculations_tables.py
python api/migrations/add_sage_tokens.py
python api/migrations/add_procore_tokens.py
```

**Via Admin Endpoints:**

```bash
# Sage tokens
curl -u admin:LienAPI2025 \
  http://localhost:8000/api/admin/run-sage-migration

# Procore tokens
curl -u admin:LienAPI2025 \
  http://localhost:8000/api/admin/run-procore-migration

# State data
curl -u admin:LienAPI2025 \
  http://localhost:8000/api/admin/run-state-migration
```

---

## 11. ENVIRONMENT VARIABLES REFERENCE

### Required Variables

#### Database

```env
DATABASE_URL=postgresql://user:password@host:port/database
# OR for SQLite:
DATABASE_PATH=./liendeadline.db
DB_TYPE=postgresql  # or 'sqlite'
```

#### Authentication

```env
ADMIN_USER=admin
ADMIN_PASS=LienAPI2025
ENCRYPTION_KEY=<auto-generated>
```

#### Email

```env
RESEND_API_KEY=re_...
SMTP_FROM_EMAIL=noreply@liendeadline.com
```

**Optional (fallback SMTP):**
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

#### Payments (Stripe)

```env
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLIC_KEY=pk_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### OAuth Credentials

#### QuickBooks

```env
QUICKBOOKS_CLIENT_ID=ABRV9aq09aCvEFIGKNZp4utAydOjYUPuJmmLIaV9LogeqdlysS
QUICKBOOKS_CLIENT_SECRET=MLFX7R2VmYWsTen8O6qKqvStOCb1NxYr6KSfgdxm
QUICKBOOKS_REDIRECT_URI=https://liendeadline.com/api/quickbooks/callback
```

#### Sage

```env
SAGE_CLIENT_ID=Ka4F3opf0BgcYG9kqcGOa8hqvVJv4qJl
SAGE_CLIENT_SECRET=/rdnRb68xgPxlnLvLU4vOobrAphZl5Zz4Rxa0HHM
SAGE_REDIRECT_URI=https://liendeadline.com/api/sage/callback
```

#### Procore

```env
PROCORE_CLIENT_ID=xBZ__1B9C31iDRMphjjT6yCXOnFucFJovcfJK9okCEE
PROCORE_CLIENT_SECRET=l0u7NuRyOS24neB-ZRuJUQMTyUIEsUlcVyZbMiczUWE
PROCORE_REDIRECT_URI=https://liendeadline.com/api/procore/callback
```

**Sandbox (for testing):**
```env
PROCORE_SANDBOX_CLIENT_ID=gmfqRS3337q1c9tCJMXvKdC-OhVbwpWtTfiqz7FY1Wrg
PROCORE_SANDBOX_CLIENT_SECRET=yJQXWp2fb6Zgoha8MTMmUa1j6nhSiREaj66yKY4fVNs
PROCORE_SANDBOX_URL=https://sandbox.procore.com/4279807/company/home
```

### Optional Variables

```env
# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# Logging
LOG_LEVEL=INFO

# CORS
ALLOWED_ORIGINS=https://liendeadline.com,http://localhost:8000
```

---

## 12. TESTING & QUALITY ASSURANCE

### Manual Testing Checklist

#### Calculator Functionality

- [ ] Test all 50 states
- [ ] Verify preliminary notice calculations
- [ ] Verify lien filing calculations
- [ ] Test edge cases (holidays, weekends)
- [ ] Test special states (TX, CA, WA, OH, OR, HI)
- [ ] Compare with state law references

#### OAuth Integrations

- [ ] QuickBooks connect → disconnect flow
- [ ] Sage connect → disconnect flow
- [ ] Procore connect → disconnect flow
- [ ] Token refresh logic (wait 1 hour, verify refresh)
- [ ] Error handling (denied access, invalid credentials)
- [ ] Multiple users connecting same integration

#### Dashboard Features

- [ ] Project saving
- [ ] Email reminders creation
- [ ] PDF generation
- [ ] Calculation history
- [ ] Integration status display
- [ ] Disconnect functionality

#### Cross-browser Testing

- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)
- [ ] Mobile browsers (iOS Safari, Chrome Mobile)

---

### Automated Testing (To Be Implemented)

#### Unit Tests

Create `tests/test_calculations.py`:
```python
def test_utah_prelim_notice():
    result = calculate_deadline("UT", "2024-12-27", "supplier")
    assert result.prelimDeadline == "2026-01-16"

def test_texas_commercial():
    result = calculate_texas(datetime(2024, 12, 27), project_type="commercial")
    assert result["lien_deadline"] == datetime(2025, 4, 15)
```

#### Integration Tests

Create `tests/test_oauth.py`:
```python
def test_quickbooks_oauth_flow():
    # Test full OAuth flow (mock Intuit API)
    pass

def test_sage_oauth_flow():
    # Test full OAuth flow (mock Sage API)
    pass
```

#### PDF Audit Script

**Location:** `scripts/auditPDFvsCalculator.js`

**Usage:**
```bash
# Start API locally
uvicorn api.main:app --port 8000

# Run audit
node scripts/auditPDFvsCalculator.js
```

**Output:** `pdf-audit-results.json` with comparison results

---

## 13. SECURITY CONSIDERATIONS

### Current Security Measures

- [x] Password hashing (bcrypt with salt)
- [x] HTTPS/SSL enabled (Railway automatic)
- [x] Environment variables for secrets
- [x] CORS configuration
- [x] SQL injection protection (parameterized queries)
- [x] Session token validation
- [x] OAuth state tokens (CSRF protection)
- [x] HTTP Basic Auth for admin endpoints

### Security Improvements Needed

- [ ] Rate limiting on API endpoints (slowapi configured but not enforced)
- [ ] CSRF protection for forms
- [ ] API key rotation mechanism
- [ ] Audit logging
- [ ] Security headers (CSP, X-Frame-Options, HSTS)
- [ ] Input validation improvements
- [ ] OAuth token encryption at rest
- [ ] Password strength requirements
- [ ] Two-factor authentication (2FA)
- [ ] Session timeout

### Compliance

- [ ] GDPR compliance review
- [ ] Privacy policy (exists but needs legal review)
- [ ] Terms of service (exists but needs legal review)
- [ ] Data retention policy
- [ ] Right to deletion implementation
- [ ] Cookie consent banner

---

## 14. DEVELOPER NOTES

### Lessons Learned

#### OAuth Debugging

1. **Swedish Locale Issue:** Browser locale (sv) broke QuickBooks OAuth → Always force `locale=en_US` in OAuth URLs
2. **Procore Scope Parameter:** Procore doesn't use scope parameters → Remove it entirely
3. **Procore Token Exchange:** Requires Basic Auth header → Use `Authorization: Basic {base64(client_id:client_secret)}`
4. **Sage Endpoints:** Sage Operations uses Sage Intacct OAuth infrastructure → Use Intacct endpoints

#### Common Pitfalls

1. **Environment Variable Mismatches:** Local vs Railway env vars differ → Always check both
2. **Database Schema Differences:** SQLite vs PostgreSQL → Use `DB_TYPE` check in code
3. **Static File Serving:** Must be last mount → Place after all API routes
4. **Favicon Caching:** Browser cache issues → Hard refresh (Ctrl+F5) required
5. **RealDictCursor Access:** PostgreSQL returns dict-like objects → Use `result['column']` not `result[0]`

### Useful Commands

#### Local Development

```bash
# Start server
uvicorn api.main:app --reload --port 8000

# Run migrations
python api/migrations/add_all_states.py

# Test API endpoint
curl -X POST http://localhost:8000/api/v1/calculate-deadline \
  -H "Content-Type: application/json" \
  -d '{"state":"TX","invoice_date":"2025-12-27","role":"supplier"}'

# Run audit script
node scripts/auditPDFvsCalculator.js
```

#### Database

```bash
# Connect to Railway PostgreSQL
railway connect

# Backup database
pg_dump $DATABASE_URL > backup.sql

# View tables
psql $DATABASE_URL -c "\dt"

# View table schema
psql $DATABASE_URL -c "\d users"
```

#### Railway

```bash
# View logs
railway logs

# Restart service
railway restart

# View environment variables
railway variables
```

### Code Organization

**File Structure:**
- `api/main.py` - Main FastAPI app (11,273 lines - consider splitting)
- `api/calculations.py` - Calculation endpoints and user auth
- `api/quickbooks.py` - QuickBooks OAuth
- `api/database.py` - Database utilities
- `api/calculators.py` - State-specific calculation logic
- `api/migrations/` - Database migrations

**Refactoring Opportunities:**
1. Split `api/main.py` into multiple modules:
   - `api/routes/auth.py` - Authentication endpoints
   - `api/routes/admin.py` - Admin endpoints
   - `api/routes/oauth.py` - OAuth endpoints (Sage, Procore)
   - `api/routes/pdf.py` - PDF generation
2. Create `api/models/` for Pydantic models
3. Create `api/utils/` for helper functions

---

## 15. CONTACTS & RESOURCES

### Key Accounts

**Railway:**
- Dashboard: https://railway.app
- Account: [Your Railway account email]

**Namecheap:**
- Domain: liendeadline.com
- Account: [Your Namecheap account email]

**Resend:**
- Dashboard: https://resend.com
- Account: [Your Resend account email]

**Stripe:**
- Dashboard: https://dashboard.stripe.com
- Account: [Your Stripe account email]

**QuickBooks Developer:**
- Dashboard: https://developer.intuit.com
- App ID: [Your QuickBooks App ID]

**Sage Developer:**
- Dashboard: https://developer.sage.com
- App ID: [Your Sage App ID]

**Procore Developer:**
- Dashboard: https://developers.procore.com
- App ID: [Your Procore App ID]

---

### Documentation

**API Documentation:**
- FastAPI: https://fastapi.tiangolo.com
- Uvicorn: https://www.uvicorn.org
- Pydantic: https://docs.pydantic.dev

**OAuth Documentation:**
- QuickBooks: https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization
- Sage Intacct: https://developer.intacct.com/api/authentication/
- Procore: https://developers.procore.com/reference/rest/v1/authentication

**Database:**
- PostgreSQL: https://www.postgresql.org/docs/
- SQLite: https://www.sqlite.org/docs.html
- psycopg2: https://www.psycopg.org/docs/

**Email:**
- Resend: https://resend.com/docs

**Payments:**
- Stripe: https://stripe.com/docs

**PDF Generation:**
- ReportLab: https://www.reportlab.com/docs/reportlab-userguide.pdf

---

### Support Channels

**Internal:**
- GitHub Issues: [Repository URL]/issues
- Slack/Discord: [Your team channel]

**External:**
- Customer Support: support@liendeadline.com
- Partner Support: partners@liendeadline.com

---

## 16. HANDOFF CHECKLIST

Before handing off to another developer:

- [x] All environment variables documented
- [x] All API credentials accessible
- [x] Database schema documented
- [x] Known bugs documented
- [x] Pending tasks prioritized
- [ ] Code commented adequately (needs improvement)
- [ ] README.md updated (create if missing)
- [x] Deployment process documented
- [ ] Admin credentials shared securely
- [ ] GitHub access granted
- [ ] Railway access granted
- [ ] Domain registrar access shared
- [ ] OAuth app credentials shared
- [ ] Stripe account access shared

---

**END OF HANDOFF DOCUMENT**

---

**Next Steps for New Developer:**

1. Read this entire document
2. Set up local development environment
3. Run all migrations
4. Test OAuth integrations
5. Fix critical bugs (PDF logic mismatch)
6. Complete pending Priority 1 tasks
7. Review codebase structure
8. Ask questions early and often

**Questions?** Contact the previous developer or refer to this document.

---

**Document Maintenance:**

- Update this document as you make changes
- Add new bugs to Known Issues section
- Update Implementation Status as features are completed
- Keep Environment Variables section current
- Update Contacts section with new accounts/resources

