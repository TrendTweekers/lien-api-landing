# Broker Payout Rules & Ledger System

## Overview

This document describes the canonical payout ledger system that calculates accurate "Due / Hold / Paid" amounts for brokers based on their commission model and customer payment events.

## Commission Models

Brokers choose ONE commission model at signup:

### (A) One-Time Bounty: $500 per referred customer
- **Earning Event**: Created once when customer makes their first successful payment
- **Eligibility**: Becomes payable 60 days after payment date
- **Status Check**: Only payable if customer is still ACTIVE (not canceled/refunded/chargeback)
- **Rule**: Never pay twice for the same customer (duplicate prevention)

### (B) Recurring Monthly: $50/month per referred customer
- **Earning Event**: Created for each successful monthly charge
- **Eligibility**: Each event becomes payable 60 days after its specific charge date
- **Status Check**: Only payable if that specific charge is not refunded/chargeback
- **Rule**: Each monthly payment creates a separate earning event

## Hold Period

- **60-Day Hold**: All earning events are held for 60 days after payment date
- **Purpose**: Catches fraud, chargebacks, disputes, and cancellations
- **Calculation**: `eligible_at = payment_date + 60 days`

## Status Mapping

Referral statuses map to earning event statuses:

- `on_hold` → ACTIVE (eligible after 60 days)
- `ready_to_pay` → ACTIVE (eligible now)
- `paid` → Paid (already processed)
- `CANCELED` → Customer subscription canceled
- `REFUNDED` → Payment refunded
- `CHARGEBACK` → Payment disputed
- `PAST_DUE` → Customer payment failed
- `clawed_back` → Payment clawed back (within 90 days)

## Ledger Calculation

For each broker, the ledger computes:

### Totals
- **total_earned**: Sum of all earning events (lifetime)
- **total_paid**: Sum of paid earning events (lifetime)
- **total_due_now**: Sum of eligible unpaid events (ready to pay)
- **total_on_hold**: Sum of events not yet eligible (still in 60-day hold)

### Per-Customer Breakdown
- **customer_email**: Customer identifier
- **customer_stripe_id**: Stripe customer ID
- **commission_model**: bounty or recurring
- **last_payment_date**: Most recent payment date
- **amount_earned**: Total earned from this customer
- **amount_paid**: Total paid for this customer
- **amount_due_now**: Currently due for this customer
- **amount_on_hold**: Currently on hold for this customer
- **status**: Current customer status (ACTIVE/CANCELED/etc.)

### Per-Event Breakdown
Each earning event includes:
- **referral_id**: Unique referral ID
- **payment_date**: When the payment occurred
- **amount_earned**: Commission amount ($500 or $50)
- **eligible_at**: When this event becomes payable
- **is_eligible**: Whether 60-day hold has passed
- **is_paid**: Whether this event has been paid
- **paid_at**: When this event was paid (if paid)
- **paid_batch_id**: Batch ID if paid in batch

## Eligibility Rules

### One-Time Bounty Eligibility
```
IF commission_model == 'bounty' AND
   payment_date + 60 days <= today AND
   status == 'ACTIVE' AND
   is_paid == false
THEN amount_due_now = $500
ELSE amount_on_hold = $500
```

### Recurring Monthly Eligibility
```
FOR EACH monthly_payment:
  IF payment_date + 60 days <= today AND
     status == 'ACTIVE' AND
     is_paid == false
  THEN amount_due_now += $50
  ELSE amount_on_hold += $50
```

## Webhook Events

### `checkout.session.completed`
- **Action**: Create initial earning event
- **One-Time**: Create $500 bounty event (if first payment for customer)
- **Recurring**: Create $50 event for first payment
- **Sets**: `payment_date = now()`, `status = 'on_hold'`

### `invoice.payment_succeeded`
- **Action**: Create recurring earning event (only for recurring commission model)
- **Creates**: New $50 earning event for this monthly charge
- **Sets**: `payment_date = now()`, `status = 'on_hold'`

### `customer.subscription.deleted`
- **Action**: Mark all earning events as CANCELED
- **Updates**: All referrals for this customer to `status = 'CANCELED'`
- **Clawback**: If paid within 90 days, mark as `clawed_back`

### `invoice.payment_failed`
- **Action**: Mark pending events as PAST_DUE
- **Updates**: Referrals with `status = 'on_hold'` to `status = 'PAST_DUE'`

### `charge.refunded`
- **Action**: Mark events as REFUNDED
- **Updates**: Referrals to `status = 'REFUNDED'`

### `charge.dispute.created`
- **Action**: Mark events as CHARGEBACK
- **Updates**: Referrals to `status = 'CHARGEBACK'`

## Admin Actions

### Mark as Paid
When admin marks a payment as paid:

1. **Input**: `broker_id`, `amount`, `payment_method`, `transaction_id`, `notes`
2. **Process**:
   - Find eligible unpaid earning events for broker (sorted by `eligible_at`)
   - Mark referrals as paid up to the amount
   - Set `paid_at = now()`, `status = 'paid'`, `paid_batch_id = transaction_id`
   - Store referral IDs in `broker_payments.paid_referral_ids`
3. **Output**: List of referral IDs marked as paid

### Export CSV
CSV export includes:
- Date paid
- Broker name/email
- Amount
- Payment method
- Transaction ID
- Status
- Notes
- Referral IDs (from `paid_referral_ids`)

## Examples

### Example 1: One-Time Bounty Broker

**Broker**: John (bounty model)
**Customer**: customer@example.com
**Timeline**:
- Jan 1: Customer signs up → Earning event created ($500, on_hold)
- Mar 2: 60 days passed → Event becomes eligible ($500 due_now)
- Mar 5: Admin marks paid → Event marked paid ($500 paid)

**Ledger**:
- total_earned: $500
- total_paid: $500
- total_due_now: $0
- total_on_hold: $0

### Example 2: Recurring Monthly Broker

**Broker**: Sarah (recurring model)
**Customer**: client@example.com
**Timeline**:
- Jan 1: First payment → Event 1 created ($50, on_hold)
- Feb 1: Second payment → Event 2 created ($50, on_hold)
- Mar 1: Third payment → Event 3 created ($50, on_hold)
- Mar 2: Event 1 eligible → $50 due_now
- Mar 5: Admin marks $50 paid → Event 1 paid
- Apr 2: Event 2 eligible → $50 due_now
- May 2: Event 3 eligible → $50 due_now

**Ledger** (as of May 2):
- total_earned: $150
- total_paid: $50
- total_due_now: $100
- total_on_hold: $0

### Example 3: Customer Cancellation

**Broker**: Mike (recurring model)
**Customer**: user@example.com
**Timeline**:
- Jan 1: First payment → Event 1 created ($50, on_hold)
- Feb 1: Second payment → Event 2 created ($50, on_hold)
- Mar 2: Event 1 eligible → $50 due_now
- Mar 5: Admin marks $50 paid → Event 1 paid
- Mar 10: Customer cancels → Event 2 marked CANCELED

**Ledger** (as of Mar 10):
- total_earned: $100
- total_paid: $50
- total_due_now: $0 (Event 2 canceled, not eligible)
- total_on_hold: $0

### Example 4: Refund After Payment

**Broker**: Lisa (bounty model)
**Customer**: buyer@example.com
**Timeline**:
- Jan 1: Customer signs up → Event created ($500, on_hold)
- Mar 2: Event eligible → $500 due_now
- Mar 5: Admin marks $50 paid → Event paid
- Mar 15: Customer refunded → Event marked REFUNDED

**Ledger** (as of Mar 15):
- total_earned: $500
- total_paid: $500 (but should be clawed back)
- total_due_now: $0
- total_on_hold: $0
- **Note**: Admin should manually reverse payment or mark as clawed_back

## Database Schema

### referrals table (extended)
```sql
- id (primary key)
- broker_id (referral_code, foreign key)
- customer_email
- customer_stripe_id
- amount (customer payment amount)
- payout (commission amount: $500 or $50)
- payout_type ('bounty' or 'recurring')
- status ('on_hold', 'ready_to_pay', 'paid', 'CANCELED', 'REFUNDED', 'CHARGEBACK', 'PAST_DUE', 'clawed_back')
- payment_date (when payment succeeded) -- NEW
- hold_until (payment_date + 60 days)
- clawback_until (payment_date + 90 days)
- created_at (when referral created)
- paid_at (when marked as paid) -- NEW
- paid_batch_id (transaction ID) -- NEW
```

### broker_payments table (extended)
```sql
- id (primary key)
- broker_id
- broker_name
- broker_email
- amount
- payment_method
- transaction_id
- notes
- status
- payment_date
- paid_at
- created_at
- paid_referral_ids (JSON array of referral IDs) -- NEW
```

## API Endpoints

### `GET /api/admin/brokers-ready-to-pay`
Uses `compute_all_brokers_ledgers()` to return brokers with `total_due_now > 0`.

**Response**:
```json
{
  "brokers": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "commission_owed": 500.00,
      "total_earned": 500.00,
      "total_paid": 0.00,
      "total_on_hold": 0.00,
      "next_payment_due": "2024-03-02T00:00:00",
      "days_overdue": 0,
      "is_first_payment": true
    }
  ],
  "summary": {
    "total_commission_owed": 500.00,
    "brokers_ready_to_pay": 1,
    "brokers_overdue": 0
  }
}
```

### `GET /api/admin/broker-ledger/{broker_id}`
Returns full ledger for a broker.

**Response**:
```json
{
  "broker_id": 1,
  "broker_name": "John Doe",
  "broker_email": "john@example.com",
  "commission_model": "bounty",
  "total_earned": 500.00,
  "total_paid": 0.00,
  "total_due_now": 500.00,
  "total_on_hold": 0.00,
  "next_payout_date": "2024-03-02T00:00:00",
  "customer_breakdown": {
    "customer@example.com": {
      "customer_email": "customer@example.com",
      "commission_model": "bounty",
      "last_payment_date": "2024-01-01T00:00:00",
      "amount_earned": 500.00,
      "amount_paid": 0.00,
      "amount_due_now": 500.00,
      "amount_on_hold": 0.00,
      "status": "ACTIVE"
    }
  },
  "earning_events": [...]
}
```

### `POST /api/admin/mark-paid`
Marks specific referral IDs as paid.

**Request**:
```json
{
  "broker_id": 1,
  "amount": 500.00,
  "payment_method": "wise",
  "transaction_id": "WS-123456",
  "notes": "Paid via Wise"
}
```

**Response**:
```json
{
  "status": "success",
  "paid_referral_ids": [123],
  "referrals_marked": 1
}
```

## Migration

Run `/api/admin/migrate-payout-ledger` to:
1. Add `payment_date` column to `referrals` table
2. Add `paid_batch_id` column to `referrals` table
3. Add `paid_referral_ids` column to `broker_payments` table
4. Set `payment_date = created_at` for existing referrals

Safe and idempotent - can be run multiple times.

## Testing

See `test_payout_ledger.py` for simulation script that creates:
- 2 brokers (one bounty, one recurring)
- 3 customers
- Multiple payment events
- Shows due/hold/paid calculations

Run: `python test_payout_ledger.py`

