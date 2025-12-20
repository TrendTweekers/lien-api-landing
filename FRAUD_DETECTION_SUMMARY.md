# Fraud Detection System Summary

## Overview

LienDeadline has implemented a **multi-layer fraud detection system** to prevent brokers from referring themselves and gaming the referral program. The system runs automatically when a customer signs up via a referral link.

---

## How It Works

### When Fraud Detection Runs

The fraud check happens automatically in the **Stripe webhook handler** (`/webhooks/stripe`) when:
1. A customer completes checkout via Stripe
2. The webhook receives `checkout.session.completed` event
3. A referral code is detected in the checkout metadata

### Detection Process

```python
# Located in api/main.py, line ~2347
fraud_flags, risk_score, should_flag = check_fraud_signals(
    referral_code,      # Broker's referral code
    customer_email,     # Customer's email
    customer_stripe_id, # Stripe customer ID
    session_data        # Stripe session data
)
```

---

## 8-Layer Fraud Detection System

### **LAYER 1: Payment Method Check** ⭐⭐⭐ (Strongest)

**What it checks:**
- Compares broker's Stripe customer ID with customer's Stripe customer ID
- Catches shared payment methods (same credit card, PayPal account, etc.)

**Risk Score:** +50 points (Critical flag)

**Flag:** `SAME_STRIPE_CUSTOMER`

**Example:**
- Broker: `john@email.com` (Stripe ID: `cus_ABC123`)
- Customer: `jane@email.com` (Stripe ID: `cus_ABC123`)
- **Result:** Flagged immediately (same payment method)

---

### **LAYER 2: Email Similarity Check** ⭐⭐

**What it checks:**
1. **Similar usernames** - Uses sequence matching algorithm
   - `john@email.com` vs `johnny@email.com` = 80%+ similarity
   - Risk Score: +30 points
   - Flag: `SIMILAR_EMAIL`

2. **Sequential numbers** - Detects pattern like `john1@` vs `john2@`
   - Risk Score: +25 points
   - Flag: `SEQUENTIAL_EMAIL`

3. **Same company domain** - Same domain (except common providers)
   - `john@company.com` vs `jane@company.com`
   - Risk Score: +20 points
   - Flag: `SAME_COMPANY_DOMAIN`

**Example:**
- Broker: `john.smith@gmail.com`
- Customer: `john.smith2@gmail.com`
- **Result:** Flagged (similar email + sequential number)

---

### **LAYER 3: Timing Analysis** ⭐⭐

**What it checks:**
- Time between broker account creation and customer signup

**Risk Scores:**
- Signup within **1 hour** of broker approval: +35 points
  - Flag: `IMMEDIATE_SIGNUP`
- Signup within **24 hours**: +15 points
  - Flag: `FAST_SIGNUP`

**Example:**
- Broker approved: `2025-01-15 10:00 AM`
- Customer signs up: `2025-01-15 10:30 AM`
- **Result:** Flagged (immediate signup = suspicious)

---

### **LAYER 4: IP Address Check** ⭐⭐

**What it checks:**
- Compares broker's IP address with customer's IP address
- Same IP = likely same person/device

**Risk Score:** +40 points

**Flag:** `SAME_IP`

**Example:**
- Broker IP: `192.168.1.100`
- Customer IP: `192.168.1.100`
- **Result:** Flagged (same IP address)

---

### **LAYER 5: Stripe Risk Evaluation** ⭐⭐

**What it checks:**
- Uses Stripe's built-in fraud detection
- Checks payment risk level from Stripe

**Risk Scores:**
- `elevated` risk: +30 points
- `highest` risk: +50 points

**Flags:** `STRIPE_RISK_ELEVATED` or `STRIPE_RISK_HIGHEST`

**Example:**
- Stripe flags payment as "elevated risk"
- **Result:** Additional risk score added

---

### **LAYER 6: Referral Pattern Analysis**

**What it checks:**
- First referral from a broker gets extra scrutiny
- New brokers are more likely to test the system

**Risk Score:** +10 points (if first referral)

**Flag:** `FIRST_REFERRAL`

---

### **LAYER 7: Email Age Check** (Planned)

**Status:** Not yet implemented (requires external API)

**Planned:** Check if email account is new (suspicious)

---

### **LAYER 8: Device Fingerprint** (Planned)

**Status:** Not yet implemented (requires frontend)

**Planned:** Compare device fingerprints between broker and customer

---

## Risk Scoring System

### How Risk Score Works

Each layer adds points to a **risk score**. The system flags referrals for manual review if:

1. **Risk score ≥ 50 points**, OR
2. **`SAME_STRIPE_CUSTOMER` flag** is present (automatic flag, regardless of score)

### Risk Score Examples

**Example 1: Same Payment Method (Auto-Flag)**
```
SAME_STRIPE_CUSTOMER: +50 points
Total: 50 points → FLAGGED
```

**Example 2: Suspicious Pattern**
```
SIMILAR_EMAIL: +30 points
IMMEDIATE_SIGNUP: +35 points
FIRST_REFERRAL: +10 points
Total: 75 points → FLAGGED
```

**Example 3: Legitimate Referral**
```
FIRST_REFERRAL: +10 points
Total: 10 points → NOT FLAGGED (goes to 30-day hold)
```

---

## Referral Status Flow

### Status Values

1. **`on_hold`** - Normal referral, 30-day churn protection
   - Risk score < 50
   - No critical flags
   - Automatically moves to `pending` after 30 days

2. **`flagged_for_review`** - Suspicious referral
   - Risk score ≥ 50 OR `SAME_STRIPE_CUSTOMER` flag
   - Requires manual admin review
   - Admin can approve or deny

3. **`pending`** - Ready for payout
   - 30-day hold period expired
   - No fraud detected
   - Ready to pay broker

4. **`paid`** - Commission paid
   - Broker received payment
   - Still has 90-day clawback protection

### Protection Periods

- **30-day hold:** Prevents churn fraud (customer cancels after getting commission)
- **90-day clawback:** Allows reversing payment if fraud discovered later

---

## What Happens When Fraud is Detected

### Automatic Actions

1. **Referral is flagged** with status `flagged_for_review`
2. **Admin alert is sent** (currently logs to console, can be extended to email/Slack)
3. **Referral is stored** with all fraud flags and risk score
4. **Broker dashboard** shows referral as "Under Review"

### Admin Review Process

Admins can:
- View flagged referrals in admin dashboard
- See all fraud flags and risk score
- Approve or deny the referral
- Manually move status from `flagged_for_review` → `pending` or `denied`

---

## Database Storage

### Fraud Data Stored

```sql
-- referrals table includes:
fraud_flags TEXT  -- JSON: {"flags": [...], "risk_score": 50}
status TEXT        -- 'on_hold', 'flagged_for_review', 'pending', 'paid'
hold_until DATE    -- 30-day churn protection
clawback_until DATE -- 90-day fraud protection
```

### Example Fraud Flags JSON

```json
{
  "flags": [
    "SIMILAR_EMAIL",
    "IMMEDIATE_SIGNUP",
    "FIRST_REFERRAL"
  ],
  "risk_score": 75
}
```

---

## Code Location

**Main Function:** `api/main.py` line ~2054
- Function: `check_fraud_signals()`
- Called from: Stripe webhook handler (line ~2348)

**Alert Function:** `api/main.py` line ~2176
- Function: `send_admin_fraud_alert()`
- Currently logs to console (can be extended)

---

## Testing Fraud Detection

### Test Scenarios

1. **Same Stripe Customer:**
   - Use same payment method for broker and customer
   - Should flag immediately

2. **Similar Emails:**
   - `john@email.com` → `johnny@email.com`
   - Should flag if similarity > 80%

3. **Immediate Signup:**
   - Approve broker, then signup within 1 hour
   - Should flag

4. **Same IP:**
   - Use same IP address for both
   - Should flag

---

## Limitations & Future Improvements

### Current Limitations

1. **Email age check** - Not implemented (requires external API)
2. **Device fingerprinting** - Not implemented (requires frontend)
3. **Admin alerts** - Currently console-only (should add email/Slack)

### Future Enhancements

1. **Machine learning** - Pattern recognition for fraud
2. **Behavioral analysis** - Track user behavior patterns
3. **Real-time alerts** - Email/Slack notifications for admins
4. **Auto-deny** - Automatically deny obvious fraud cases

---

## Summary

The fraud detection system uses **8 layers** of checks to prevent self-referrals:

1. ✅ **Payment method** (Stripe customer ID)
2. ✅ **Email similarity** (username patterns)
3. ✅ **Timing analysis** (signup speed)
4. ✅ **IP address** (same device/network)
5. ✅ **Stripe risk** (payment fraud signals)
6. ✅ **Referral patterns** (first referral scrutiny)
7. ⏳ **Email age** (planned)
8. ⏳ **Device fingerprint** (planned)

**Result:** Referrals with risk score ≥ 50 or same payment method are flagged for manual review, preventing brokers from gaming the system.

