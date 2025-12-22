# Payout Batches System

## Overview

The payout batches system allows admins to select multiple DUE earning events for a broker, create a batch, export CSV, and mark them as paid in one atomic action.

## Database Schema

### `broker_payout_batches` Table

```sql
CREATE TABLE broker_payout_batches (
    id SERIAL PRIMARY KEY,
    broker_id INTEGER NOT NULL,
    broker_name VARCHAR(255) NOT NULL,
    broker_email VARCHAR(255) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    payment_method VARCHAR(50) NOT NULL,
    transaction_id VARCHAR(255),
    notes TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    referral_ids TEXT NOT NULL,  -- JSON array of referral IDs
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP,
    created_by_admin VARCHAR(255)
)
```

**Indexes:**
- `idx_batch_broker` on `broker_id`
- `idx_batch_status` on `status`

## API Endpoints

### `POST /api/admin/payout-batches/create`

Create a payout batch and mark referrals as paid atomically.

**Request:**
```json
{
  "broker_id": 1,
  "referral_ids": [123, 124, 125],
  "payment_method": "wise",
  "transaction_id": "WS-12345678",
  "notes": "Batch payment for Q1 commissions"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Payout batch created and referrals marked as paid",
  "batch_id": 42,
  "transaction_id": "WS-12345678",
  "total_amount": 150.00,
  "referrals_marked": 3,
  "referral_ids": [123, 124, 125]
}
```

**Validation:**
- `broker_id` required
- `referral_ids` must be non-empty array
- `payment_method` required
- `transaction_id` optional (auto-generated if not provided)
- Only unpaid referrals can be included

**Atomic Operations:**
1. Create batch record
2. Mark referrals as paid (`paid_at`, `status='paid'`, `paid_batch_id`)
3. Create `broker_payment` record linking to batch
4. Update batch status to `completed`

### `GET /api/admin/payout-batches/{broker_id}`

Get all payout batches for a broker.

**Response:**
```json
{
  "batches": [
    {
      "id": 42,
      "broker_id": 1,
      "broker_name": "John Doe",
      "broker_email": "john@example.com",
      "total_amount": 150.00,
      "currency": "USD",
      "payment_method": "wise",
      "transaction_id": "WS-12345678",
      "notes": "Batch payment for Q1",
      "status": "completed",
      "referral_ids": [123, 124, 125],
      "referral_count": 3,
      "created_at": "2024-01-15T10:30:00",
      "paid_at": "2024-01-15T10:30:00",
      "created_by_admin": "admin"
    }
  ]
}
```

### `GET /api/admin/payout-batches/export/{batch_id}`

Export a payout batch as CSV.

**Response:** CSV file with:
- Batch header row (ID, transaction ID, broker info, total, status)
- Referral details rows (ID, customer email, amount, type, payment date)

**Filename:** `batch-{batch_id}-{date}.csv`

## V2 Dashboard UI

### Ledger Breakdown Modal

**Location:** Click "View Breakdown" button on any broker in "Due to Pay" tab.

**Features:**
- Checkboxes for each DUE earning event (only eligible unpaid events)
- "Select All DUE" button
- "Clear" button
- Selection summary showing count and total
- "Create Batch + Mark Paid" button

**Workflow:**
1. Click "View Breakdown" on a broker
2. Check boxes for DUE events you want to batch
3. Click "Create Batch + Mark Paid"
4. Enter payment method, transaction ID (optional), notes (optional)
5. Batch is created and referrals marked as paid atomically
6. Modal closes, tabs refresh

### Batches Tab

**Location:** "Batches" tab in Broker Payouts section.

**Features:**
- View all batches created
- Shows batch ID, broker, total amount, referral count, payment method, transaction ID, created date, status
- Export CSV button (future enhancement)

## Batch Creation Rules

### Eligibility
- Only DUE events can be selected (`is_eligible = true`, `is_paid = false`, `status = 'ACTIVE'`)
- HELD events (not yet eligible) cannot be selected
- Already PAID events cannot be selected
- CANCELED, REFUNDED, CHARGEBACK events cannot be selected

### Atomicity
- All operations happen in a single database transaction
- If any step fails, entire batch creation is rolled back
- Referrals are only marked as paid if batch creation succeeds

### Linking
- `broker_payments.paid_referral_ids` stores JSON array of referral IDs
- `broker_payments.transaction_id` matches `broker_payout_batches.transaction_id`
- `referrals.paid_batch_id` stores the transaction ID for traceability

## Testing

### Test Scenario 1: Create Batch with Multiple Referrals

1. **Setup:**
   - Broker has 3 DUE earning events ($50 each = $150 total)
   - All events are eligible and unpaid

2. **Action:**
   - Open broker ledger breakdown modal
   - Select all 3 events
   - Click "Create Batch + Mark Paid"
   - Enter payment method: "wise"
   - Enter transaction ID: "WS-TEST-001"
   - Enter notes: "Test batch"

3. **Verify:**
   - Batch created with ID
   - All 3 referrals marked as paid
   - `broker_payment` record created with `paid_referral_ids = [id1, id2, id3]`
   - Broker disappears from "Due to Pay" tab
   - Broker appears in "Paid" tab
   - Batch appears in batches list

### Test Scenario 2: Partial Selection

1. **Setup:**
   - Broker has 5 DUE events ($50 each)
   - Select only 2 events

2. **Action:**
   - Create batch with 2 selected events

3. **Verify:**
   - Only 2 referrals marked as paid
   - Broker still appears in "Due to Pay" with remaining $150
   - Batch shows 2 referrals

### Test Scenario 3: Export CSV

1. **Action:**
   - Create a batch
   - Call `GET /api/admin/payout-batches/export/{batch_id}`

2. **Verify:**
   - CSV downloads with correct filename
   - Contains batch header row
   - Contains all referral detail rows
   - All amounts match

### Test Scenario 4: Error Handling

1. **Test Invalid Referral IDs:**
   - Try to create batch with non-existent referral IDs
   - Verify error message

2. **Test Already Paid Referrals:**
   - Try to include already paid referral in batch
   - Verify error message

3. **Test Empty Selection:**
   - Try to create batch with no referrals selected
   - Verify error message

## Migration

Run `/api/admin/migrate-payout-batches` to create the `broker_payout_batches` table.

Safe and idempotent - can be run multiple times.

## Integration with Existing System

### Compatibility
- Existing `/api/admin/mark-paid` endpoint unchanged
- Existing `/api/admin/payment-history` endpoint unchanged
- V1 dashboard continues to work as before
- Batch creation uses same `broker_payments` table structure

### Data Flow
1. Admin selects referrals in V2 ledger modal
2. Batch created via `/api/admin/payout-batches/create`
3. Referrals marked as paid (same as individual mark-paid)
4. `broker_payment` record created (same structure)
5. Batch record created for tracking
6. All tabs refresh to show updated state

## Examples

### Example 1: Single Broker, Multiple Events

**Broker:** Sarah (recurring model)
**Events:** 3 monthly payments, all DUE
- Event 1: $50 (Jan payment)
- Event 2: $50 (Feb payment)
- Event 3: $50 (Mar payment)

**Batch:**
- Select all 3 events
- Create batch: $150 total
- Transaction ID: WS-20240115-001
- All 3 referrals marked as paid

### Example 2: Mixed Selection

**Broker:** John (bounty model)
**Events:** 5 customers, 3 DUE, 2 HELD
- Customer 1: $500 DUE
- Customer 2: $500 DUE
- Customer 3: $500 DUE
- Customer 4: $500 HELD (not eligible yet)
- Customer 5: $500 HELD (not eligible yet)

**Batch:**
- Select only the 3 DUE events
- Create batch: $1,500 total
- Remaining 2 events stay in "On Hold"

## Security

- All endpoints require admin authentication (`verify_admin`)
- Batch creation is atomic (all-or-nothing)
- Only eligible unpaid referrals can be included
- Transaction IDs are validated
- Admin username is logged in `created_by_admin`

## Future Enhancements

- Bulk batch creation (select multiple brokers)
- Batch templates (save common selections)
- Batch approval workflow
- Email notifications for batch creation
- Batch status tracking (pending → processing → completed)
- Batch cancellation/reversal

