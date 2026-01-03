# LienDeadline Affiliate/Partner System - Complete Summary

## 📋 Table of Contents
1. [System Overview](#system-overview)
2. [Database Structure](#database-structure)
3. [Commission Models](#commission-models)
4. [Referral Flow](#referral-flow)
5. [API Endpoints](#api-endpoints)
6. [Dashboard Components](#dashboard-components)
7. [Payment Processing](#payment-processing)
8. [Fraud Detection](#fraud-detection)
9. [Current Status & Issues](#current-status--issues)

---

## 🎯 System Overview

**Purpose:** Track broker/partner referrals and calculate commissions for customer signups.

**Key Components:**
- **Brokers/Partners:** Affiliates who refer customers
- **Referrals:** Customer signups linked to brokers
- **Commissions:** Payments to brokers ($500 bounty or $50/month recurring)
- **Fraud Protection:** 60-day hold period + fraud detection
- **Dashboards:** Admin and broker-facing interfaces

---

## 🗄️ Database Structure

### 1. `brokers` Table

**Purpose:** Stores broker/partner information

**Key Columns:**
```sql
CREATE TABLE brokers (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    email VARCHAR UNIQUE NOT NULL,
    company VARCHAR,
    commission_model VARCHAR DEFAULT 'bounty',  -- 'bounty' or 'recurring'
    referral_code VARCHAR UNIQUE,              -- e.g., 'broker_abc123'
    short_code VARCHAR(10),                    -- e.g., 'EhaB' (for /r/EhaB links)
    referral_link VARCHAR,                     -- Full URL: https://liendeadline.com/r/EhaB
    status VARCHAR DEFAULT 'active',            -- 'pending', 'approved', 'active'
    approved_at TIMESTAMP,
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
    stripe_customer_id VARCHAR,
    ip_address VARCHAR,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Important Notes:**
- `referral_code`: Long code like `broker_abc123` (used in Stripe metadata)
- `short_code`: Short code like `EhaB` (used in `/r/EhaB` URLs)
- `commission_model`: `'bounty'` ($500 one-time) or `'recurring'` ($50/month)

---

### 2. `referrals` Table

**Purpose:** Tracks customer signups and commissions

**Key Columns:**
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
    hold_until DATE,                           -- 60-day anti-churn protection (payment_date + 60 days)
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

**Important Notes:**
- `broker_id` stores the `referral_code` (text), NOT the numeric `brokers.id`
- `hold_until` = payment_date + 60 days (anti-churn protection)
- `clawback_until` = payment_date + 90 days (fraud protection)

---

### 3. `referral_clicks` Table

**Purpose:** Analytics - tracks referral link clicks

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

## 💰 Commission Models

### Model A: One-Time Bounty ($500)

**How It Works:**
- Broker earns $500 **one-time** per referred customer
- Triggered on **first successful payment**
- Never pay twice for the same customer
- Status: `on_hold` → `pending` → `paid`

**Eligibility:**
- Becomes payable 60 days after payment date
- Only if customer is still ACTIVE (not canceled/refunded/chargeback)

---

### Model B: Recurring Monthly ($50/month)

**How It Works:**
- Broker earns $50 **per month** per referred customer
- Triggered on **each successful monthly charge**
- Each monthly payment creates a separate earning event
- Status: `on_hold` → `pending` → `paid`

**Eligibility:**
- Each event becomes payable 60 days after its specific charge date
- Only if that specific charge is not refunded/chargeback

**⚠️ CURRENT ISSUE:** No automated system to create recurring commissions. Only creates commission on first payment.

---

## 🔄 Referral Flow

### Step 1: User Clicks Referral Link

**URL Format:** `https://liendeadline.com/r/{short_code}`

**Example:** `https://liendeadline.com/r/EhaB`

**Backend Handler:** `api/main.py` - `/r/{short_code}` route (lines 1195-1344)

**What Happens:**
1. Backend looks up broker by `short_code`:
   ```sql
   SELECT id, name, email, referral_code 
   FROM brokers 
   WHERE short_code = 'EhaB' AND status = 'approved'
   ```
2. Tracks the click in `referral_clicks` table (IP, user agent, referrer)
3. Sets **3 cookies** (30-day expiry):
   - `ref_code`: The full referral code (e.g., `broker_abc123`)
   - `ref_short`: The short code (e.g., `EhaB`)
   - `ref_broker`: The broker's numeric ID
4. Redirects to homepage (`/`)

**Cookie Storage:**
- Cookies are `httponly=True` and `samesite="lax"`
- Expires in 30 days

---

### Step 2: Customer Signs Up & Pays

**Frontend:** `index.html` - `buildStripeUrl()` function

**⚠️ CURRENT ISSUE:** Frontend checks `localStorage`/`sessionStorage` for referral code, but backend sets **cookies**. There's a mismatch.

**Backend:** `api/main.py` - `/api/create-checkout-session` endpoint

**⚠️ CRITICAL ISSUE:** The checkout session creation does NOT include `client_reference_id` to pass the referral code!

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

**Should Be:**
```python
referral_code = request.cookies.get('ref_code') or 'direct'
checkout_session = stripe.checkout.Session.create(
    payment_method_types=['card'],
    line_items=[{'price': price_id, 'quantity': 1}],
    mode='subscription',
    client_reference_id=referral_code,  # ← MISSING!
    success_url='...',
    cancel_url='...',
)
```

---

### Step 3: Stripe Webhook Processes Payment

**Handler:** `api/routers/webhooks.py` - `stripe_webhook()` function

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

---

### Step 4: Commission Status Transitions

**Current Flow:**
```
on_hold (60 days) → pending → paid
         ↓
flagged_for_review (manual review)
```

**⚠️ MISSING:** No automated cron job to:
- Move `'on_hold'` → `'pending'` after 60 days
- Process recurring $50/month commissions for active subscriptions

**Manual Process:**
- Admin dashboard can mark referrals as `'paid'`
- Admin can approve/deny flagged referrals

---

## 🔌 API Endpoints

### Broker Endpoints

**Base Path:** `/api/v1/broker/`

#### 1. Apply to Partner Program
- **Endpoint:** `POST /api/v1/apply-partner`
- **Location:** `api/routers/brokers.py` lines 108-250
- **Request Body:**
  ```json
  {
    "name": "John Smith",
    "email": "john@example.com",
    "company": "ABC Corp",
    "client_count": "11-50",
    "commission_model": "bounty",  // or "recurring"
    "message": "Optional message",
    "works_with_suppliers": true
  }
  ```
- **Response:** Auto-approval if `works_with_suppliers = true`
- **Creates:** Broker record with `referral_code`, `short_code`, `referral_link`

#### 2. Broker Login
- **Endpoint:** `POST /api/v1/broker/login`
- **Location:** `api/routers/brokers.py` lines 252-285
- **Request Body:**
  ```json
  {
    "email": "john@example.com",
    "password": "password"
  }
  ```
- **Response:** Session token + broker info

#### 3. Get Dashboard Data
- **Endpoint:** `GET /api/v1/broker/dashboard`
- **Location:** `api/routers/brokers.py` lines 287-451
- **Query:** 
  ```sql
  SELECT customer_email, amount, payout, payout_type, status, created_at
  FROM referrals
  WHERE broker_id = ?
  ORDER BY created_at DESC
  ```
- **Returns:** Broker's referral list with totals

#### 4. Get Payment Info
- **Endpoint:** `GET /api/v1/broker/payment-info`
- **Location:** `api/routers/brokers.py` lines 568-662
- **Returns:** Broker's payment information (masked for security)

#### 5. Update Payment Info
- **Endpoint:** `POST /api/v1/broker/payment-info`
- **Location:** `api/routers/brokers.py` lines 453-566
- **Action:** Updates broker's payment information (encrypted)

---

### Admin Endpoints

**Base Path:** `/api/admin/`

#### 1. Get All Brokers
- **Endpoint:** `GET /api/admin/brokers`
- **Location:** `api/routers/admin.py` lines 345-412
- **Returns:** List of all brokers with stats

#### 2. Get Pending Payouts
- **Endpoint:** `GET /api/admin/payouts/pending`
- **Location:** `api/routers/admin.py` lines 1703-1802
- **Query:** 
  ```sql
  SELECT r.id, r.broker_id, r.customer_email, r.amount, r.payout, r.status, b.name as broker_name
  FROM referrals r
  LEFT JOIN brokers b ON r.broker_id = b.referral_code
  WHERE r.status = 'pending'
  ORDER BY r.created_at DESC
  ```
- **Returns:** List of pending payouts

#### 3. Get Broker Ledger
- **Endpoint:** `GET /api/admin/broker-ledger/{broker_id}`
- **Location:** `api/routers/admin.py` lines 1490-1499
- **Uses:** `compute_broker_ledger()` from `payout_ledger.py`
- **Returns:** Full payout ledger for a broker (Due / Hold / Paid breakdown)

#### 4. Get Brokers Ready to Pay
- **Endpoint:** `GET /api/admin/brokers-ready-to-pay`
- **Location:** `api/routers/admin.py` lines 1441-1455
- **Uses:** `compute_all_brokers_ledgers()` from `payout_ledger.py`
- **Returns:** List of brokers with `total_due_now > 0`

#### 5. Mark Referral as Paid
- **Endpoint:** `POST /api/admin/mark-paid`
- **Location:** `api/routers/admin.py` lines 1501-1534
- **Action:** Inserts into `broker_payments` table + updates `referrals.paid_at`

#### 6. Get Flagged Referrals
- **Endpoint:** `GET /api/v1/admin/flagged-referrals`
- **Location:** `api/main.py` lines 3632-3685
- **Returns:** Referrals with `status = 'flagged_for_review'`

#### 7. Approve/Deny Flagged Referral
- **Endpoints:** 
  - `POST /api/v1/admin/approve-referral/{referral_id}`
  - `POST /api/v1/admin/deny-referral/{referral_id}`
- **Location:** `api/main.py` lines 3686-3722

---

## 📊 Dashboard Components

### Admin Dashboard V2

**File:** `admin-dashboard-v2.html`

**Features:**
- View all brokers
- View pending payouts
- View broker ledgers (Due / Hold / Paid breakdown)
- Approve/deny flagged referrals
- Mark referrals as paid
- Export data to CSV

**API Calls:**
- `GET /api/admin/brokers`
- `GET /api/admin/payouts/pending`
- `GET /api/admin/broker-ledger/{broker_id}`
- `GET /api/admin/brokers-ready-to-pay`
- `POST /api/admin/mark-paid`

---

### Broker Dashboard V2

**File:** `broker-dashboard.html` (or `dashboard-v2/broker-dashboard/`)

**Features:**
- View referral list
- View earnings breakdown (Due / Hold / Paid)
- Update payment information
- View referral link
- View analytics (clicks, conversions)

**API Calls:**
- `GET /api/v1/broker/dashboard`
- `GET /api/v1/broker/payment-info`
- `POST /api/v1/broker/payment-info`

---

## 💳 Payment Processing

### Payout Ledger Service

**File:** `api/services/payout_ledger.py`

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

## 🛡️ Fraud Detection

**Location:** `api/routers/webhooks.py` - `check_fraud_signals()` function

**Checks Performed:**
1. **Same Stripe Customer ID:** Broker and customer share same Stripe ID
2. **Email Similarity:** Broker and customer emails are similar
3. **Timing:** Signup within 1 hour of broker creation
4. **IP Address Match:** Broker and customer share same IP
5. **Stripe Risk Level:** High risk score from Stripe
6. **Referral Velocity:** 5+ referrals in 24 hours

**Risk Scoring:**
- Each check adds points to risk score
- Risk score >= 60: Flagged for review (`status = 'flagged_for_review'`)
- Risk score >= 80: Auto-reject (but still reviewable)
- `SAME_STRIPE_CUSTOMER`: Automatic flag regardless of score

**Fraud Flags Stored:**
- Stored as JSON in `referrals.fraud_flags` column
- Includes risk score and specific flags

---

## ⚠️ Current Status & Issues

### ✅ What's Working

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

### ❌ What's Broken/Missing

#### Priority 1: Referral Code Not Passed to Stripe

**Issue:** `create_checkout_session` endpoint doesn't include `client_reference_id`

**Location:** `api/main.py` lines 5192-5222

**Fix Needed:**
```python
referral_code = request.cookies.get('ref_code') or 'direct'
checkout_session = stripe.checkout.Session.create(
    # ... existing params ...
    client_reference_id=referral_code,  # ← ADD THIS
)
```

---

#### Priority 2: Frontend Cookie Reading

**Issue:** Frontend checks `localStorage`/`sessionStorage` for referral code, but backend sets cookies

**Location:** `index.html` lines 2350-2372

**Fix Needed:** Frontend should read cookies, not localStorage

---

#### Priority 3: Status Transitions

**Issue:** No automated cron job to move `'on_hold'` → `'pending'` after 60 days

**Fix Needed:** Create `api/cron_update_referral_status.py`:
```python
# Run daily to move 'on_hold' → 'pending' after 60 days
UPDATE referrals 
SET status = 'pending' 
WHERE status = 'on_hold' 
AND hold_until <= CURRENT_DATE;
```

---

#### Priority 4: Recurring Commissions

**Issue:** No automated system to create $50/month commissions for recurring model

**Fix Needed:** Add webhook handler for `invoice.payment_succeeded`:
```python
if event['type'] == 'invoice.payment_succeeded':
    invoice = event['data']['object']
    customer_id = invoice['customer']
    
    # Find referral for this customer
    # If broker has 'recurring' model, create $50 commission
    # Only if customer is still active
```

---

#### Priority 5: Database Schema Mismatch

**Issue:** `referrals.broker_id` stores `referral_code` (text), not `brokers.id` (integer)

**Impact:** Some queries may JOIN incorrectly

**Note:** `payout_ledger.py` handles this correctly by looking up `referral_code` first

---

## 📈 System Statistics

**Current Capabilities:**
- ✅ Short referral links (`/r/{code}`)
- ✅ Click tracking & analytics
- ✅ Fraud detection (6 layers)
- ✅ 60-day hold period
- ✅ 90-day clawback protection
- ✅ Admin & broker dashboards
- ✅ Payment info encryption
- ✅ Payout ledger calculation

**Missing Features:**
- ❌ Automated status transitions
- ❌ Recurring commission tracking
- ❌ Stripe referral code passing
- ❌ Frontend cookie reading

---

## 🔧 Recommended Fixes Priority

1. **CRITICAL:** Fix Stripe checkout referral code passing
2. **HIGH:** Fix frontend cookie reading
3. **HIGH:** Add cron job for status transitions
4. **MEDIUM:** Add recurring commission webhook handler
5. **LOW:** Standardize database schema (broker_id vs referral_code)

---

## 📝 Summary

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

