# LienDeadline Project Summary

**Last Updated:** December 2024  
**Site URL:** https://liendeadline.com  
**Status:** Production (Live)

---

## 📋 Project Overview

**LienDeadline** is a SaaS application that helps construction material suppliers and contractors calculate mechanics lien filing deadlines across all 50 US states + DC. The application prevents missed deadlines that can result in losing $75K+ in unpaid receivables.

### What It Does
- **Free Tier:** 6 free calculations (3 before email capture, 3 after)
- **Paid Tier:** Unlimited calculations for $299/month or $2,390/year (33% discount)
- **Partner Program:** Brokers earn commissions ($500 one-time bounty OR $50/month recurring per client)
- **State Coverage:** All 50 states + DC with state-specific calculation logic

### Tech Stack
- **Backend:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL (production on Railway) / SQLite (local development)
- **Payment Processing:** Stripe (test mode currently)
- **Email Service:** Resend API
- **Hosting:** Railway.app
- **Frontend:** Static HTML/CSS/JavaScript (Tailwind CSS CDN)
- **Analytics:** Google Analytics (GA4), Umami Analytics

---

## 🏗️ Architecture

### File Structure

```
lien-api-landing/
├── api/
│   ├── main.py                 # Main FastAPI application (11,000+ lines)
│   ├── admin.py                # Admin API endpoints
│   ├── analytics.py            # Analytics endpoints
│   ├── database.py             # Database connection utilities (PostgreSQL/SQLite)
│   ├── calculators.py          # State-specific calculation logic
│   ├── rate_limiter.py         # API rate limiting
│   ├── short_link_system.py    # Short referral link generation
│   └── requirements.txt       # Python dependencies
├── public/
│   ├── index.html              # Landing page
│   ├── pricing.html            # Pricing page (direct Stripe test link)
│   ├── login.html              # Customer login page
│   ├── customer-dashboard.html # Customer dashboard
│   ├── broker-dashboard.html   # Broker/partner dashboard
│   ├── partners.html           # Partner program landing page
│   └── state-lien-guides/     # 50 state-specific guide pages
├── database/
│   ├── schema.sql             # Database schema (SQLite format)
│   └── migrations/            # SQL migration files
├── railway.json               # Railway deployment config
├── Procfile                   # Process file for Railway
└── PROJECT_SUMMARY.md         # This file
```

### Database Schema

**Primary Database:** PostgreSQL (production) / SQLite (local dev)

**Key Tables:**

1. **`users`** - Paying customers
   - `id` SERIAL PRIMARY KEY (PostgreSQL) / INTEGER PRIMARY KEY AUTOINCREMENT (SQLite)
   - `email` VARCHAR UNIQUE NOT NULL
   - `password_hash` VARCHAR NOT NULL
   - `stripe_customer_id` VARCHAR
   - `subscription_status` VARCHAR DEFAULT 'active'
   - `subscription_id` VARCHAR
   - `session_token` VARCHAR
   - `created_at` TIMESTAMPTZ / TIMESTAMP
   - `updated_at` TIMESTAMPTZ / TIMESTAMP
   - `last_login_at` TIMESTAMPTZ / TIMESTAMP

2. **`customers`** - Admin tracking table
   - `id` SERIAL / INTEGER PRIMARY KEY
   - `email` VARCHAR UNIQUE NOT NULL
   - `stripe_customer_id` VARCHAR UNIQUE
   - `subscription_id` VARCHAR
   - `status` VARCHAR DEFAULT 'active'
   - `plan` VARCHAR DEFAULT 'unlimited'
   - `amount` DECIMAL DEFAULT 299.00
   - `calls_used` INTEGER DEFAULT 0
   - `created_at` TIMESTAMPTZ / TIMESTAMP

3. **`brokers`** - Partner/broker accounts
   - `id` VARCHAR PRIMARY KEY (referral_code)
   - `name` VARCHAR NOT NULL
   - `email` VARCHAR UNIQUE NOT NULL
   - `referral_code` VARCHAR UNIQUE
   - `commission_model` VARCHAR ('bounty' or 'recurring')
   - `referrals` INTEGER DEFAULT 0
   - `earned` DECIMAL DEFAULT 0.00
   - `pending_commissions` INTEGER DEFAULT 0
   - `status` VARCHAR DEFAULT 'pending' ('pending', 'approved', 'denied')
   - `stripe_account_id` VARCHAR (for payouts)
   - `created_at` TIMESTAMPTZ / TIMESTAMP
   - `approved_at` TIMESTAMPTZ / TIMESTAMP

4. **`referrals`** - Referral tracking and commissions
   - `id` SERIAL / INTEGER PRIMARY KEY
   - `broker_id` VARCHAR NOT NULL (references brokers.referral_code)
   - `broker_email` VARCHAR NOT NULL
   - `customer_email` VARCHAR NOT NULL
   - `customer_stripe_id` VARCHAR
   - `amount` DECIMAL(10,2) NOT NULL (customer payment: $299)
   - `payout` DECIMAL(10,2) NOT NULL ($500 bounty OR $50 recurring)
   - `payout_type` VARCHAR NOT NULL ('bounty' or 'recurring')
   - `status` VARCHAR DEFAULT 'on_hold' ('on_hold', 'ready_to_pay', 'paid', 'flagged_for_review', 'CANCELED', 'PAST_DUE', 'REFUNDED', 'CHARGEBACK', 'clawed_back')
   - `fraud_flags` TEXT (JSON string with fraud detection results)
   - `hold_until` DATE (60-day hold period)
   - `clawback_until` DATE (90-day clawback period)
   - `created_at` TIMESTAMPTZ / TIMESTAMP
   - `paid_at` TIMESTAMPTZ / TIMESTAMP
   - `payment_date` TIMESTAMPTZ / TIMESTAMP

5. **`partner_applications`** - Broker application queue
   - `id` SERIAL / INTEGER PRIMARY KEY
   - `name` VARCHAR NOT NULL
   - `email` VARCHAR UNIQUE NOT NULL
   - `company` VARCHAR
   - `commission_model` VARCHAR ('bounty' or 'recurring')
   - `status` VARCHAR DEFAULT 'pending'
   - `created_at` TIMESTAMPTZ / TIMESTAMP

6. **`stripe_events`** - Webhook idempotency tracking
   - `id` SERIAL / INTEGER PRIMARY KEY
   - `event_id` VARCHAR UNIQUE NOT NULL
   - `event_type` VARCHAR NOT NULL
   - `processed_at` TIMESTAMPTZ / TIMESTAMP
   - `created_at` TIMESTAMPTZ / TIMESTAMP

7. **`email_gate_tracking`** - Free trial tracking
   - `id` SERIAL / INTEGER PRIMARY KEY
   - `email` VARCHAR NOT NULL
   - `calculation_count` INTEGER DEFAULT 0
   - `email_captured_at` TIMESTAMPTZ / TIMESTAMP
   - `created_at` TIMESTAMPTZ / TIMESTAMP

8. **`calculations`** - API usage logs
   - `id` SERIAL / INTEGER PRIMARY KEY
   - `email` VARCHAR
   - `state_code` VARCHAR
   - `created_at` TIMESTAMPTZ / TIMESTAMP

9. **`failed_emails`** - Failed email tracking
   - `id` SERIAL / INTEGER PRIMARY KEY
   - `email` VARCHAR NOT NULL
   - `password` VARCHAR NOT NULL (temp password)
   - `reason` TEXT
   - `created_at` TIMESTAMPTZ / TIMESTAMP

### API Endpoints

#### Public Endpoints
- `GET /` - Landing page
- `GET /pricing.html` - Pricing page
- `GET /login.html` - Login page
- `GET /partners.html` - Partner program page
- `GET /customer-dashboard` - Customer dashboard (requires auth)
- `GET /broker-dashboard` - Broker dashboard (requires auth)
- `GET /admin-dashboard-v2` - Admin dashboard (HTTP Basic Auth)
- `GET /r/{short_code}` - Short referral link redirect

#### Calculation Endpoints
- `POST /v1/calculate` - Calculate lien deadline (legacy)
- `POST /api/v1/calculate-deadline` - Calculate lien deadline (new)
- `GET /v1/states` - List supported states
- `POST /api/v1/track-calculation` - Track calculation usage

#### Authentication Endpoints
- `POST /api/login` - Customer login (rate limited: 5/minute)
- `POST /api/logout` - Logout (invalidates session token)
- `GET /api/verify-session` - Verify session token
- `POST /api/v1/broker/login` - Broker login
- `POST /api/v1/broker/logout` - Broker logout

#### Stripe Webhooks
- `POST /webhooks/stripe` - Stripe webhook handler
  - Handles: `checkout.session.completed`, `invoice.payment_succeeded`, `customer.subscription.deleted`, `invoice.payment_failed`, `charge.dispute.created`, `charge.refunded`
  - **NOTE:** Signature verification is currently DISABLED for testing

#### Admin Endpoints (`/api/admin/*`)
- `GET /api/admin/stats` - Dashboard statistics
- `GET /api/admin/partner-applications` - List broker applications
- `POST /api/admin/approve-partner/{id}` - Approve broker
- `POST /api/admin/deny-partner/{id}` - Deny broker
- `GET /api/admin/broker-ledger/{broker_id}` - Broker payment ledger
- `POST /api/admin/mark-paid` - Mark commission as paid
- `POST /api/admin/update-user-email` - Update user email & reset password

#### Broker Endpoints (`/api/v1/broker/*`)
- `GET /api/v1/broker/dashboard` - Broker dashboard data (requires Authorization header)
- `GET /api/v1/broker/payment-info` - Payment info (requires Authorization header)
- `POST /api/v1/broker/update-payment-info` - Update payment info (requires Authorization header)

#### Other Endpoints
- `POST /api/contact` - Contact form submission
- `POST /api/v1/apply-partner` - Partner application submission
- `GET /api/v1/guide/{state_code}/pdf` - Generate state guide PDF
- `GET /health` - Health check endpoint

### External Integrations

#### Stripe
- **Current Mode:** TEST MODE
- **Test Payment Link:** `https://buy.stripe.com/test_3cIcN5gBL8pr6MVgrP9fW00`
- **Webhook Endpoint:** `/webhooks/stripe`
- **Webhook Secret:** `STRIPE_WEBHOOK_SECRET` (currently not verified)
- **Events Handled:**
  - `checkout.session.completed` - Creates user account, sends welcome email, creates referral commission
  - `invoice.payment_succeeded` - Creates recurring commission events (for recurring model brokers)
  - `customer.subscription.deleted` - Cancels subscription, marks referrals as CANCELED
  - `invoice.payment_failed` - Marks subscription as past_due
  - `charge.dispute.created` / `charge.refunded` - Marks referrals as CHARGEBACK/REFUNDED

#### Resend (Email Service)
- **API Key:** `RESEND_API_KEY` environment variable
- **From Email:** `SMTP_FROM_EMAIL` (defaults to "onboarding@resend.dev")
- **Emails Sent:**
  - Welcome email (with temp password)
  - Broker welcome email (with referral link)
  - Password reset emails
  - Admin fraud alerts
  - Broker notifications

---

## ✅ Current Implementation Status

### What's Working

1. **Payment Flow** ✅
   - Stripe checkout redirects to test payment link
   - Webhook creates user accounts automatically
   - Welcome emails sent with temp passwords
   - User can login with email/password

2. **Webhooks** ✅
   - Stripe webhooks received and processed
   - Idempotency checking (prevents duplicate processing)
   - User account creation
   - Referral commission tracking
   - **NOTE:** Signature verification DISABLED for testing

3. **User Creation** ✅
   - Automatic account creation on payment
   - Password hashing with bcrypt
   - Session token generation
   - Database: PostgreSQL (production) / SQLite (local)

4. **Emails** ✅
   - Welcome emails via Resend
   - Password reset emails
   - Broker notifications
   - Failed email tracking in `failed_emails` table

5. **Dashboards** ✅
   - Customer dashboard (unlimited calculations)
   - Broker dashboard (referral tracking, earnings)
   - Admin dashboard (broker approval, payment management)

6. **Calculation Engine** ✅
   - All 50 states + DC supported
   - State-specific logic (TX, CA, WA, OH, OR, HI, etc.)
   - Free tier: 6 calculations total
   - Paid tier: Unlimited calculations

7. **Partner Program** ✅
   - Broker applications
   - Auto-approve functionality (instant approval)
   - Commission tracking (bounty vs recurring)
   - Fraud detection system
   - 60-day hold period
   - 90-day clawback period

### What's in TEST Mode

- **Stripe:** Using test keys (`STRIPE_SECRET_KEY` test key)
- **Stripe Webhook:** Signature verification disabled
- **Payment Link:** Direct Stripe test payment link (not API-based checkout)

### What's in LIVE Mode

- **Database:** PostgreSQL on Railway (production)
- **Email:** Resend API (production)
- **Site:** https://liendeadline.com (live)

### Recent Changes & Fixes

1. **Database Context Manager** (Latest)
   - Fixed `stripe_webhook` to use `with get_db() as db:` pattern
   - Proper connection management and error handling

2. **Syntax Fixes** (Latest)
   - Fixed indentation errors in `stripe_webhook` function
   - Added `except` block to close `try` block properly

3. **Broker Authentication** (Recent)
   - Added broker logout endpoint
   - Added token validation to broker API calls
   - Updated broker dashboard to include Authorization headers

4. **Customer Login Flow** (Recent)
   - Created standalone `/login.html` page
   - Updated welcome email to link to login page
   - Added success banner on homepage after Stripe redirect

5. **Partner Program** (Recent)
   - Added commission model selector to application form
   - Updated webhook to handle bounty vs recurring commissions
   - Fixed auto-approve messaging ("instantly" vs "in 1 hour")

---

## 📝 Code Conventions

### Database Operations

**ALWAYS use context manager pattern:**

```python
from api.database import get_db

with get_db() as db:
    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    # Connection automatically commits on success, rolls back on error
```

**PostgreSQL Syntax:**
- Use `%s` placeholders (NOT `?`)
- Use `SERIAL` for auto-increment (NOT `AUTOINCREMENT`)
- Use `TIMESTAMPTZ` for timestamps
- Use `VARCHAR` for text fields
- Use `DECIMAL(10,2)` for money amounts

**SQLite Syntax (local dev):**
- Use `?` placeholders
- Use `INTEGER PRIMARY KEY AUTOINCREMENT`
- Use `TIMESTAMP` for timestamps
- Use `TEXT` for text fields
- Use `REAL` for money amounts

**Database Type Detection:**
```python
from api.database import DB_TYPE

if DB_TYPE == 'postgresql':
    # PostgreSQL code
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
else:
    # SQLite code
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
```

### Error Handling Patterns

**Always wrap database operations in try/except:**

```python
try:
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute("...")
        result = cursor.fetchone()
except Exception as e:
    logger.error(f"Database error: {e}")
    raise HTTPException(status_code=500, detail="Database error")
```

**Webhook Error Handling:**

```python
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"Webhook error: {str(e)}")
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "Internal server error"}
    )
```

### PostgreSQL vs SQLite Compatibility

The `database.py` module handles compatibility automatically:
- Detects database type from `DATABASE_URL`
- Provides `get_db()` context manager
- Provides `get_db_cursor()` helper
- Provides `execute_query()` helper for placeholder conversion

---

## 🔐 Environment Variables

### Railway Environment Variables

**Required:**
- `DATABASE_URL` - PostgreSQL connection string (Railway provides this automatically)
- `STRIPE_SECRET_KEY` - Stripe API secret key (test or live)
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret (optional, currently not used)

**Email:**
- `RESEND_API_KEY` - Resend API key for sending emails
- `SMTP_FROM_EMAIL` - From email address (defaults to "onboarding@resend.dev")

**Optional:**
- `DATABASE_PATH` - SQLite database path (for local dev, defaults to `liendeadline.db`)
- `SMTP_EMAIL` - SMTP email (fallback if Resend not available)
- `SMTP_PASSWORD` - SMTP password (fallback if Resend not available)
- `SMTP_SERVER` - SMTP server (defaults to "smtp.gmail.com")
- `SMTP_PORT` - SMTP port (defaults to 587)

**Admin:**
- `ADMIN_USER` - Admin dashboard username (HTTP Basic Auth)
- `ADMIN_PASS` - Admin dashboard password (HTTP Basic Auth)

**Third-Party Integrations (Optional):**
- `SAGE_CLIENT_ID` - Sage integration (not currently used)
- `SAGE_CLIENT_SECRET` - Sage integration (not currently used)
- `PROCORE_CLIENT_ID` - Procore integration (not currently used)
- `PROCORE_CLIENT_SECRET` - Procore integration (not currently used)

### Test vs Live Mode

**Current Status:** TEST MODE

**To Switch to LIVE Mode:**

1. **Stripe:**
   - Update `STRIPE_SECRET_KEY` to live key in Railway
   - Update `STRIPE_WEBHOOK_SECRET` to live webhook secret
   - Update `pricing.html` to use live Stripe checkout link
   - Re-enable webhook signature verification in `api/main.py`

2. **Re-enable Webhook Signature Verification:**
   ```python
   # In api/main.py, stripe_webhook function:
   # Remove the "TEMPORARILY DISABLED" section
   # Uncomment the signature verification code:
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
   ```

---

## ⚠️ Known Issues & Technical Debt

### Current Issues

1. **Stripe Webhook Signature Verification Disabled**
   - **Status:** Temporarily disabled for testing
   - **Location:** `api/main.py` line ~5042
   - **Impact:** Webhooks are not verified (security risk)
   - **Fix:** Re-enable signature verification before going live

2. **PostgreSQL Schema Mismatch**
   - Some code uses SQLite syntax (`AUTOINCREMENT`, `?` placeholders)
   - Database module handles conversion, but should be standardized
   - **Impact:** Low (works but inconsistent)

3. **Direct Stripe Payment Link**
   - `pricing.html` uses direct Stripe test link instead of API-based checkout
   - **Impact:** Cannot customize checkout experience
   - **Fix:** Re-implement `/api/create-checkout-session` endpoint

### Technical Debt

1. **Large `main.py` File**
   - Over 11,000 lines in single file
   - Should be split into modules (webhooks, auth, calculations, etc.)

2. **Mixed Database Syntax**
   - Some queries use SQLite syntax, some use PostgreSQL
   - Should standardize on PostgreSQL syntax with compatibility layer

3. **Error Handling**
   - Inconsistent error handling patterns
   - Some endpoints return JSON, some raise HTTPException
   - Should standardize error response format

4. **Session Management**
   - Customer sessions use `session_token` in database
   - Broker sessions stored client-side only (no server-side validation)
   - Should implement proper session management for brokers

5. **Fraud Detection**
   - Fraud detection system exists but needs review
   - Risk scoring algorithm may need tuning

### Security Considerations

1. **Webhook Security**
   - ⚠️ Signature verification disabled (CRITICAL - fix before production)
   - Idempotency checking implemented ✅

2. **Authentication**
   - Customer auth: bcrypt password hashing ✅
   - Session tokens stored in database ✅
   - Broker auth: Basic token validation (needs improvement)

3. **Admin Dashboard**
   - HTTP Basic Auth (should consider upgrading to session-based)

4. **SQL Injection**
   - All queries use parameterized statements ✅
   - Database module handles placeholder conversion ✅

---

## 🚀 Development Workflow

### Deployment Process

1. **Make Changes Locally**
   ```bash
   # Edit files
   # Test locally (if possible)
   ```

2. **Commit & Push**
   ```bash
   git add .
   git commit -m "Description of changes"
   git push origin main
   ```

3. **Railway Auto-Deploys**
   - Railway automatically detects push to `main` branch
   - Builds and deploys automatically
   - No manual deployment needed

4. **Manual Restart (if needed)**
   - Go to Railway dashboard
   - Click "Restart" button
   - Wait for deployment to complete

### Testing Procedures

**Local Testing:**
- Uses SQLite database (`liendeadline.db`)
- Stripe webhooks can be tested with Stripe CLI:
  ```bash
  stripe listen --forward-to localhost:8000/webhooks/stripe
  ```

**Production Testing:**
- Use Stripe test mode
- Test payment flow end-to-end
- Verify webhook processing
- Check email delivery

### Railway Manual Restart Requirement

**When to Restart:**
- After environment variable changes
- After code changes that don't auto-deploy
- If application becomes unresponsive

**How to Restart:**
1. Go to Railway dashboard
2. Select the service
3. Click "Restart" button
4. Wait ~30 seconds for restart

---

## 📚 Common Tasks Guide

### How to Add a New Webhook Event Handler

1. **Find the webhook handler** (`api/main.py` line ~5036):
   ```python
   @app.post("/webhooks/stripe")
   async def stripe_webhook(request: Request):
       # ... existing code ...
   ```

2. **Add new event type** inside the `try:` block:
   ```python
   elif event['type'] == 'new.event.type':
       # Handle the event
       data = event['data']['object']
       # ... your logic ...
   ```

3. **Use database context manager:**
   ```python
   with get_db() as db:
       cursor = db.cursor()
       cursor.execute("...", (...))
       # Auto-commits on success
   ```

4. **Test with Stripe CLI:**
   ```bash
   stripe trigger new.event.type
   ```

### How to Modify the Pricing Page

**File:** `public/pricing.html`

**Current Implementation:**
- Uses direct Stripe test link: `https://buy.stripe.com/test_3cIcN5gBL8pr6MVgrP9fW00`
- JavaScript function `createCheckoutSession()` redirects to this link

**To Change Pricing:**
1. Update prices in HTML (monthly/annual amounts)
2. Update Stripe payment link if needed
3. Update webhook handler if pricing logic changes

**To Switch to API-Based Checkout:**
1. Re-implement `/api/create-checkout-session` endpoint
2. Update `pricing.html` JavaScript to call API
3. Handle checkout session creation in backend

### How to Debug Webhook Issues

1. **Check Railway Logs:**
   - Go to Railway dashboard
   - Click "Deployments" → Latest deployment → "View Logs"
   - Look for webhook-related errors

2. **Check Stripe Dashboard:**
   - Go to Stripe Dashboard → Webhooks
   - View webhook event logs
   - Check for failed deliveries

3. **Add Debug Logging:**
   ```python
   print(f"✅ Received webhook: {event['type']}")
   print(f"   Event ID: {event['id']}")
   print(f"   Data: {json.dumps(event['data'], indent=2)}")
   ```

4. **Check Database:**
   ```sql
   -- Check if event was processed
   SELECT * FROM stripe_events WHERE event_id = 'evt_...';
   
   -- Check user creation
   SELECT * FROM users WHERE email = 'test@example.com';
   
   -- Check referral creation
   SELECT * FROM referrals WHERE customer_email = 'test@example.com';
   ```

5. **Common Issues:**
   - **Signature verification failed:** Check `STRIPE_WEBHOOK_SECRET` is correct
   - **Duplicate event:** Check `stripe_events` table for idempotency
   - **User not created:** Check webhook logs for errors
   - **Email not sent:** Check `failed_emails` table

### How to Switch Between Test/Live Mode

**Switch to LIVE Mode:**

1. **Update Stripe Keys:**
   - Railway Dashboard → Variables
   - Update `STRIPE_SECRET_KEY` to live key (starts with `sk_live_`)
   - Update `STRIPE_WEBHOOK_SECRET` to live webhook secret (starts with `whsec_`)

2. **Update Payment Link:**
   - Edit `public/pricing.html`
   - Replace test link with live Stripe checkout link
   - Or re-implement API-based checkout

3. **Re-enable Signature Verification:**
   - Edit `api/main.py` line ~5042
   - Remove "TEMPORARILY DISABLED" section
   - Uncomment signature verification code

4. **Restart Railway:**
   - Railway Dashboard → Restart service

**Switch Back to TEST Mode:**
- Reverse the above steps
- Use test keys (start with `sk_test_` and `whsec_test_`)

### How to Add a New State Calculation

1. **Add calculation function** in `api/calculators.py`:
   ```python
   def calculate_newstate(invoice_date, **kwargs):
       # State-specific logic
       return {
           "preliminary_deadline": ...,
           "lien_deadline": ...,
           ...
       }
   ```

2. **Import in `api/main.py`:**
   ```python
   from .calculators import calculate_newstate
   ```

3. **Add to `calculate_state_deadline()` function:**
   ```python
   elif state_code == "NS":
       return calculate_newstate(invoice_date, ...)
   ```

4. **Test:**
   ```bash
   curl -X POST "http://localhost:8000/v1/calculate" \
     -H "Content-Type: application/json" \
     -d '{"invoice_date": "2024-01-01", "state": "NS"}'
   ```

### How to Update User Email/Password (Admin)

**Via Admin Dashboard:**
1. Go to `/admin-dashboard-v2`
2. Login with HTTP Basic Auth
3. Use "User Management" section
4. Enter old email, new email, new password
5. Click "Update User"

**Via API:**
```bash
curl -X POST "https://liendeadline.com/api/admin/update-user-email?old_email=old@example.com&new_email=new@example.com&new_password=NewPass123!" \
  -H "Authorization: Basic $(echo -n 'admin:password' | base64)"
```

---

## 🔍 Key Code Locations

### Authentication
- Customer login: `api/main.py` line ~3865
- Broker login: `api/main.py` line ~7370
- Session verification: `api/main.py` line ~4032

### Webhooks
- Stripe webhook handler: `api/main.py` line ~5036
- Event processing: `api/main.py` line ~5101-5514

### Database
- Connection management: `api/database.py`
- Context manager: `get_db()` function

### Calculations
- State calculations: `api/calculators.py`
- Unified calculation: `api/main.py` line ~45

### Email
- Welcome email: `api/main.py` line ~5516 (`send_welcome_email()`)
- Broker welcome: `api/main.py` line ~5674 (`send_broker_welcome_email()`)

### Admin
- Admin endpoints: `api/admin.py`
- Broker approval: `api/admin.py` line ~6433

---

## 📞 Support & Resources

**Site:** https://liendeadline.com  
**Admin Dashboard:** https://liendeadline.com/admin-dashboard-v2  
**Stripe Dashboard:** https://dashboard.stripe.com  
**Railway Dashboard:** https://railway.app  
**Resend Dashboard:** https://resend.com  

**Key Files to Read:**
- `api/main.py` - Main application logic
- `api/database.py` - Database connection patterns
- `api/admin.py` - Admin endpoints
- `public/index.html` - Landing page structure
- `public/pricing.html` - Pricing page structure

---

## 🎯 Quick Reference

### Database Connection Pattern
```python
from api.database import get_db, DB_TYPE

with get_db() as db:
    cursor = db.cursor()
    if DB_TYPE == 'postgresql':
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    else:
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
```

### Stripe Webhook Pattern
```python
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    event = json.loads(payload)  # Signature verification disabled
    
    with get_db() as db:
        try:
            if event['type'] == 'checkout.session.completed':
                # Handle event
                pass
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return JSONResponse(status_code=500, content={"status": "error"})
```

### API Response Pattern
```python
return JSONResponse(
    status_code=200,
    content={"status": "success", "data": {...}}
)
```

---

**End of Document**
