# Referral System - Complete Overview

## 1. DATABASE SCHEMA

### brokers Table
**PostgreSQL Schema:**
```sql
CREATE TABLE brokers (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    company VARCHAR,
    commission_model VARCHAR DEFAULT 'bounty',  -- 'bounty' or 'recurring'
    referral_code VARCHAR UNIQUE,              -- e.g., 'broker_abc123'
    short_code VARCHAR(10),                    -- e.g., 'EhaB' (for /r/EhaB links)
    referral_link VARCHAR,                     -- Full URL: https://liendeadline.com/r/EhaB
    status VARCHAR DEFAULT 'active',            -- 'pending', 'approved', 'active'
    approved_at TIMESTAMP DEFAULT NOW(),
    total_referrals INTEGER DEFAULT 0,
    total_earned DECIMAL(10, 2) DEFAULT 0,
    password_hash VARCHAR,                      -- For broker login
    payment_method VARCHAR,                     -- 'paypal', 'bank', 'crypto', etc.
    payment_email VARCHAR,
    iban VARCHAR,                               -- Encrypted
    swift_code VARCHAR,                         -- Encrypted
    bank_name VARCHAR,
    bank_address VARCHAR,
    account_holder_name VARCHAR,
    crypto_wallet VARCHAR,                      -- Encrypted
    crypto_currency VARCHAR,
    tax_id VARCHAR,                             -- Encrypted
    stripe_customer_id VARCHAR,                 -- For fraud detection
    ip_address VARCHAR,                          -- For fraud detection
    created_at TIMESTAMP DEFAULT NOW()
);
```

**SQLite Schema:** Same structure, but uses `INTEGER PRIMARY KEY AUTOINCREMENT` and `TEXT` instead of `SERIAL` and `VARCHAR`.

**Key Columns:**
- `referral_code`: Long code like `broker_abc123` (used in Stripe metadata)
- `short_code`: Short code like `EhaB` (used in `/r/EhaB` URLs)
- `commission_model`: `'bounty'` ($500 one-time) or `'recurring'` ($50/month)

---

### referrals Table
**PostgreSQL Schema (from migration `004_create_referrals_table.sql`):**
```sql
CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL,            -- References brokers.referral_code (NOT brokers.id!)
    broker_email VARCHAR(255) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    customer_stripe_id VARCHAR(255),            -- Stripe customer ID
    amount DECIMAL(10,2) NOT NULL DEFAULT 299.00,  -- Customer payment amount
    payout DECIMAL(10,2) NOT NULL,             -- Commission: $500 or $50
    payout_type VARCHAR(50) NOT NULL,           -- 'bounty' or 'recurring'
    status VARCHAR(50) DEFAULT 'on_hold',      -- 'on_hold', 'pending', 'paid', 'flagged_for_review'
    fraud_flags TEXT,                          -- JSON string with fraud detection results
    hold_until DATE,                           -- 30-day anti-churn protection (payment_date + 60 days)
    clawback_until DATE,                       -- 90-day fraud protection (payment_date + 90 days)
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP,
    FOREIGN KEY (broker_id) REFERENCES brokers(referral_code)
);
```

**Status Flow:**
```
on_hold (60 days) → pending → paid
         ↓
flagged_for_review (manual review)
```

**Key Points:**
- `broker_id` stores the `referral_code` (text), NOT the numeric `brokers.id`
- `hold_until` = payment_date + 60 days (anti-churn protection)
- `clawback_until` = payment_date + 90 days (fraud protection)

---

### users/customers Tables
**users Table:**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    stripe_customer_id TEXT UNIQUE,
    subscription_status TEXT DEFAULT 'active',
    subscription_id TEXT,
    session_token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

**customers Table:**
```sql
CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    stripe_customer_id TEXT UNIQUE,
    subscription_id TEXT,
    status TEXT DEFAULT 'active',
    plan TEXT DEFAULT 'unlimited',
    amount REAL DEFAULT 299.00,
    calls_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Note:** No `referred_by` column exists in users/customers tables. Referral tracking is done via the `referrals` table.

---

### referral_clicks Table (Analytics)
**Created automatically by `/r/{code}` route:**
```sql
CREATE TABLE referral_clicks (
    id SERIAL PRIMARY KEY,
    short_code VARCHAR(10) NOT NULL,
    broker_id INTEGER,                         -- References brokers.id (numeric)
    ip_address VARCHAR(45),
    user_agent TEXT,
    referrer_url TEXT,
    clicked_at TIMESTAMP DEFAULT NOW(),
    converted BOOLEAN DEFAULT FALSE,           -- Set to TRUE when customer pays
    conversion_date TIMESTAMP
);
```

---

## 2. REFERRAL LINK TRACKING

### Route Handler: `/r/{short_code}`

**Location:** `api/main.py` lines 1195-1344

**What Happens:**
1. User visits `https://liendeadline.com/r/EhaB`
2. Backend looks up broker by `short_code`:
   ```python
   SELECT id, name, email, referral_code 
   FROM brokers 
   WHERE short_code = 'EhaB' AND status = 'approved'
   ```
3. Tracks the click in `referral_clicks` table (IP, user agent, referrer)
4. Sets **3 cookies** (30-day expiry):
   - `ref_code`: The full referral code (e.g., `broker_abc123`)
   - `ref_short`: The short code (e.g., `EhaB`)
   - `ref_broker`: The broker's numeric ID
5. Redirects to homepage (`/`)

**Cookie Storage:**
- Cookies are `httponly=True` and `samesite="lax"`
- Expires in 30 days
- Frontend JavaScript can read these cookies

---

### Frontend Referral Code Detection

**Location:** `index.html` lines 2350-2372

**How Frontend Gets Referral Code:**
```javascript
window.getReferralCode = function() {
    return localStorage.getItem('referral_code') || 
           sessionStorage.getItem('referral_code') || 
           'direct';
};
```

**Note:** The frontend checks `localStorage`/`sessionStorage`, but the backend sets **cookies**. There may be a mismatch here - the frontend should also check cookies.

---

## 3. CUSTOMER SIGNUP & PAYMENT

### Stripe Checkout Session Creation

**Location:** `api/main.py` lines 5192-5222

**Current Implementation:**
```python
@app.post("/api/create-checkout-session")
async def create_checkout_session(request: CheckoutRequest):
    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{'price': price_id, 'quantity': 1}],
        mode='subscription',
        success_url='https://liendeadline.com/success.html?session_id={CHECKOUT_SESSION_ID}',
        cancel_url='https://liendeadline.com/pricing.html',
    )
    return {"url": checkout_session.url}
```

**⚠️ ISSUE:** The checkout session creation does NOT include `client_reference_id` to pass the referral code!

**Frontend Attempts to Add It:**
**Location:** `index.html` line 2364
```javascript
params.append('client_reference_id', referralCode);
```

But this only works if using Stripe Payment Links with URL parameters. For `stripe.checkout.Session.create()`, the referral code must be passed in the API call.

---

### Stripe Webhook Handler

**Location:** `api/routers/webhooks.py` lines 194-467

**Event:** `checkout.session.completed`

**What Happens:**
1. Webhook receives `checkout.session.completed` event
2. Extracts referral code from `session.client_reference_id`:
   ```python
   referral_code = session.get('client_reference_id', 'direct')
   ```
3. If referral code starts with `'broker_'`:
   - Looks up broker: `SELECT * FROM brokers WHERE referral_code = ?`
   - Determines payout amount:
     - `commission_model == 'recurring'` → $50
     - `commission_model == 'bounty'` → $500
4. **Runs Fraud Detection** (`check_fraud_signals` function):
   - Checks same Stripe customer ID
   - Checks email similarity
   - Checks timing (signup within 1 hour = suspicious)
   - Checks IP address match
   - Checks Stripe risk level
   - Checks referral velocity (5+ in 24h = suspicious)
5. Creates referral record:
   ```python
   INSERT INTO referrals (
       broker_id, broker_email, customer_email, customer_stripe_id,
       amount, payout, payout_type, status,
       fraud_flags, hold_until, clawback_until, created_at
   ) VALUES (...)
   ```
6. Sets status:
   - `'flagged_for_review'` if fraud detected (risk_score >= 60)
   - `'on_hold'` if normal (60-day hold period)

**Fraud Detection Thresholds:**
- Risk score >= 60: Flagged for review
- Risk score >= 80: Auto-reject (but still reviewable)
- `SAME_STRIPE_CUSTOMER`: Automatic flag regardless of score

---

## 4. COMMISSION CALCULATION

### Commission Amounts

**Location:** `api/routers/webhooks.py` lines 381-388

```python
commission_model = broker.get('commission_model', 'bounty')
if commission_model == 'recurring':
    payout_amount = 50.00
    payout_type = 'recurring'
else:
    payout_amount = 500.00
    payout_type = 'bounty'
```

**Rules:**
- **Bounty Model:** $500 one-time per customer (only first payment)
- **Recurring Model:** $50 per month per customer (each successful charge)

---

### Payout Ledger Service

**Location:** `api/services/payout_ledger.py`

**Purpose:** Canonical calculation of broker payouts (Due / Hold / Paid)

**Key Functions:**
- `compute_broker_ledger(cursor, broker_id, db_type)`: Computes ledger for one broker
- `compute_all_brokers_ledgers(cursor, db_type)`: Computes ledgers for all brokers

**EarningEvent Class:**
- Represents a single earning event (one-time or recurring payment)
- Calculates eligibility: `eligible_at = payment_date + 60 days`
- Determines amounts:
  - `amount_paid`: If `paid_at` is set
  - `amount_due_now`: If eligible and status is ACTIVE
  - `amount_on_hold`: Otherwise

**Status Constants:**
- `STATUS_ACTIVE`: Customer is active
- `STATUS_CANCELED`: Customer canceled
- `STATUS_REFUNDED`: Payment refunded
- `STATUS_CHARGEBACK`: Chargeback occurred
- `STATUS_PAST_DUE`: Payment failed

**Hold Period:** 60 days (anti-churn protection)

---

### Commission Triggers

**Automated:**
- Stripe webhook (`checkout.session.completed`) creates referral record
- Status starts as `'on_hold'` (60-day protection)
- After 60 days, status should change to `'pending'` (but this requires a cron job or manual update)

**Manual:**
- Admin dashboard can mark referrals as `'paid'`
- Admin can approve/deny flagged referrals

**⚠️ MISSING:** No automated cron job to:
- Move `'on_hold'` → `'pending'` after 60 days
- Process recurring $50/month commissions for active subscriptions

---

## 5. ADMIN & BROKER DASHBOARDS

### Admin Dashboard V2

**Location:** `admin-dashboard-v2.html`

**API Endpoints Used:**

1. **`GET /api/admin/brokers`**
   - **Location:** `api/routers/admin.py` lines 345-412
   - **Query:** `SELECT id, name, email, referrals, earned, status, payment_method, commission_model, referral_code, payment_status, last_payment_date, total_paid FROM brokers ORDER BY created_at DESC`
   - **Returns:** List of all brokers with stats

2. **`GET /api/admin/payouts/pending`**
   - **Location:** `api/routers/admin.py` lines 1703-1802
   - **Query:** `SELECT r.id, r.broker_id, r.customer_email, r.amount, r.payout, r.status, b.name as broker_name FROM referrals r LEFT JOIN brokers b ON r.broker_id = b.id WHERE r.status = 'pending' ORDER BY r.created_at DESC`
   - **Returns:** List of pending payouts

3. **`GET /api/admin/broker-ledger/{broker_id}`**
   - **Location:** `api/routers/admin.py` lines 1490-1499
   - **Uses:** `compute_broker_ledger()` from `payout_ledger.py`
   - **Returns:** Full payout ledger for a broker (Due / Hold / Paid breakdown)

4. **`GET /api/admin/brokers-ready-to-pay`**
   - **Location:** `api/routers/admin.py` lines 1441-1455
   - **Uses:** `compute_all_brokers_ledgers()` from `payout_ledger.py`
   - **Returns:** List of brokers with `total_due_now > 0`

5. **`POST /api/admin/mark-paid`**
   - **Location:** `api/routers/admin.py` lines 1501-1534
   - **Action:** Inserts into `broker_payments` table
   - **Note:** This is separate from updating `referrals.paid_at`

---

### Broker Dashboard V2

**Location:** `broker-dashboard.html`

**API Endpoints Used:**

1. **`GET /api/v1/broker/dashboard`**
   - **Location:** `api/routers/brokers.py` lines 287-451
   - **Query:** 
     ```sql
     SELECT customer_email, amount, payout, payout_type, status, created_at
     FROM referrals
     WHERE broker_id = ?
     ORDER BY created_at DESC
     ```
   - **Returns:** Broker's referral list with totals

2. **`GET /api/v1/broker/payment-info`**
   - **Location:** `api/routers/brokers.py` lines 568-662
   - **Returns:** Broker's payment information (masked for security)

3. **`POST /api/v1/broker/payment-info`**
   - **Location:** `api/routers/brokers.py` lines 453-566
   - **Action:** Updates broker's payment information (encrypted)

---

## 6. CURRENT STATE AUDIT

### What's Working ✅

1. **Referral Link Tracking:**
   - `/r/{short_code}` route works
   - Cookies are set correctly
   - Clicks are tracked in `referral_clicks` table

2. **Broker Management:**
   - Brokers can apply via `/api/v1/apply-partner`
   - Auto-approval works if `works_with_suppliers = true`
   - Broker login works (`/api/v1/broker/login`)

3. **Fraud Detection:**
   - Multi-layer fraud detection is implemented
   - Flags suspicious referrals automatically
   - Sends admin alerts

4. **Payout Ledger:**
   - `compute_broker_ledger()` calculates Due/Hold/Paid correctly
   - Admin dashboard can view broker ledgers

---

### What's Broken/Missing ❌

1. **Referral Code Not Passed to Stripe:**
   - `create_checkout_session` endpoint doesn't include `client_reference_id`
   - Frontend tries to add it via URL params, but this only works for Payment Links
   - **Fix Needed:** Add `client_reference_id` to `stripe.checkout.Session.create()` call

2. **Frontend Cookie Reading:**
   - Frontend checks `localStorage`/`sessionStorage` for referral code
   - Backend sets cookies (`ref_code`, `ref_short`, `ref_broker`)
   - **Fix Needed:** Frontend should read cookies, not localStorage

3. **Status Transitions:**
   - No automated cron job to move `'on_hold'` → `'pending'` after 60 days
   - Status changes require manual admin action

4. **Recurring Commissions:**
   - No automated system to create $50/month commissions for recurring model
   - Only creates commission on first payment
   - **Fix Needed:** Stripe webhook for `invoice.payment_succeeded` to create recurring commissions

5. **Database Schema Mismatch:**
   - `referrals.broker_id` stores `referral_code` (text), not `brokers.id` (integer)
   - Some queries may JOIN incorrectly
   - `payout_ledger.py` handles this correctly by looking up `referral_code` first

6. **Missing Columns:**
   - `brokers` table may be missing `short_code`, `referral_link`, `password_hash` columns in production
   - These are added by migrations, but migrations may not have run

---

## 7. FLOW DIAGRAM

```
User clicks referral link: https://liendeadline.com/r/EhaB
↓
[BACKEND: api/main.py /r/{short_code}]
  - Lookup broker: SELECT * FROM brokers WHERE short_code = 'EhaB'
  - Track click: INSERT INTO referral_clicks (short_code, broker_id, ip_address, ...)
  - Set cookies: ref_code='broker_abc123', ref_short='EhaB', ref_broker='123'
  - Redirect to: /
↓
User browses site (cookies persist for 30 days)
↓
User clicks "Get API Key" / "Upgrade"
↓
[FRONTEND: index.html buildStripeUrl()]
  - Reads referral code: localStorage.getItem('referral_code') OR cookie
  - Builds Stripe URL: ?client_reference_id=broker_abc123
  ⚠️ ISSUE: This only works for Payment Links, not Session.create()
↓
User completes Stripe checkout
↓
[STRIPE WEBHOOK: api/routers/webhooks.py stripe_webhook()]
  Event: checkout.session.completed
  - Extract referral_code: session.get('client_reference_id', 'direct')
  - If referral_code.startswith('broker_'):
    - Lookup broker: SELECT * FROM brokers WHERE referral_code = 'broker_abc123'
    - Determine payout: $500 (bounty) or $50 (recurring)
    - Run fraud detection: check_fraud_signals()
    - Calculate hold dates: hold_until = payment_date + 60 days
    - Create referral: INSERT INTO referrals (broker_id, customer_email, payout, status='on_hold', ...)
↓
Commission Recorded
  - Status: 'on_hold' (60-day protection)
  - After 60 days: Should become 'pending' (but no cron job)
  - Admin can mark as 'paid': UPDATE referrals SET paid_at = NOW(), status = 'paid'
↓
Shows in Dashboards
  - Admin Dashboard: GET /api/admin/payouts/pending
  - Broker Dashboard: GET /api/v1/broker/dashboard
  - Both query: SELECT * FROM referrals WHERE broker_id = 'broker_abc123'
```

---

## 8. CRITICAL FIXES NEEDED

### Priority 1: Fix Stripe Checkout Referral Code

**File:** `api/main.py` lines 5192-5222

**Current Code:**
```python
checkout_session = stripe.checkout.Session.create(
    payment_method_types=['card'],
    line_items=[{'price': price_id, 'quantity': 1}],
    mode='subscription',
    success_url='...',
    cancel_url='...',
)
```

**Fixed Code:**
```python
# Get referral code from cookies or request
referral_code = request.cookies.get('ref_code') or 'direct'

checkout_session = stripe.checkout.Session.create(
    payment_method_types=['card'],
    line_items=[{'price': price_id, 'quantity': 1}],
    mode='subscription',
    client_reference_id=referral_code,  # ← ADD THIS
    success_url='...',
    cancel_url='...',
)
```

---

### Priority 2: Fix Frontend Cookie Reading

**File:** `index.html` lines 2350-2372

**Current Code:**
```javascript
window.getReferralCode = function() {
    return localStorage.getItem('referral_code') || 
           sessionStorage.getItem('referral_code') || 
           'direct';
};
```

**Fixed Code:**
```javascript
window.getReferralCode = function() {
    // Check cookies first (set by /r/{code} route)
    const cookies = document.cookie.split(';').reduce((acc, cookie) => {
        const [key, value] = cookie.trim().split('=');
        acc[key] = value;
        return acc;
    }, {});
    
    return cookies.ref_code || 
           localStorage.getItem('referral_code') || 
           sessionStorage.getItem('referral_code') || 
           'direct';
};
```

---

### Priority 3: Add Cron Job for Status Transitions

**Create:** `api/cron_update_referral_status.py`

```python
# Run daily to move 'on_hold' → 'pending' after 60 days
UPDATE referrals 
SET status = 'pending' 
WHERE status = 'on_hold' 
AND hold_until <= CURRENT_DATE;
```

---

### Priority 4: Add Recurring Commission Webhook

**File:** `api/routers/webhooks.py`

**Add handler for:** `invoice.payment_succeeded`

```python
if event['type'] == 'invoice.payment_succeeded':
    invoice = event['data']['object']
    customer_id = invoice['customer']
    
    # Find referral for this customer
    # If broker has 'recurring' model, create $50 commission
    # Only if customer is still active
```

---

## 9. DATABASE QUERIES FOR TESTING

### Check if referrals exist:
```sql
SELECT COUNT(*) FROM referrals;
```

### Check brokers:
```sql
SELECT id, name, email, referral_code, short_code, commission_model, status 
FROM brokers 
ORDER BY created_at DESC;
```

### Check referral clicks:
```sql
SELECT short_code, COUNT(*) as clicks, COUNT(CASE WHEN converted THEN 1 END) as conversions
FROM referral_clicks
GROUP BY short_code
ORDER BY clicks DESC;
```

### Check pending payouts:
```sql
SELECT r.id, r.broker_id, r.customer_email, r.payout, r.status, r.hold_until,
       b.name as broker_name
FROM referrals r
LEFT JOIN brokers b ON r.broker_id = b.referral_code
WHERE r.status IN ('on_hold', 'pending')
ORDER BY r.created_at DESC;
```

---

## SUMMARY

**Current State:**
- ✅ Referral link tracking works (`/r/{code}`)
- ✅ Cookies are set correctly
- ✅ Fraud detection works
- ✅ Webhook creates referral records
- ❌ Referral code NOT passed to Stripe checkout
- ❌ Frontend doesn't read cookies
- ❌ No automated status transitions
- ❌ No recurring commission tracking

**Critical Path to Fix:**
1. Add `client_reference_id` to Stripe checkout session creation
2. Fix frontend to read cookies instead of localStorage
3. Add cron job for status transitions
4. Add webhook handler for recurring commissions



