# Railway SQL Commands - Create Referrals Table

## Quick Copy-Paste SQL for Railway

Run this SQL in Railway PostgreSQL console to create the referrals table:

```sql
-- Create referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL,
    broker_email VARCHAR(255) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    customer_stripe_id VARCHAR(255),
    amount DECIMAL(10,2) NOT NULL DEFAULT 299.00,
    payout DECIMAL(10,2) NOT NULL,
    payout_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'on_hold',
    fraud_flags TEXT,
    hold_until DATE,
    clawback_until DATE,
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP,
    FOREIGN KEY (broker_id) REFERENCES brokers(referral_code)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_referrals_broker_id ON referrals(broker_id);
CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status);
CREATE INDEX IF NOT EXISTS idx_referrals_customer_email ON referrals(customer_email);
CREATE INDEX IF NOT EXISTS idx_referrals_created_at ON referrals(created_at);
CREATE INDEX IF NOT EXISTS idx_referrals_hold_until ON referrals(hold_until);
```

---

## How to Run in Railway

### Option 1: Railway Web Console

1. Go to Railway dashboard
2. Select your project
3. Click on PostgreSQL database
4. Click "Query" tab
5. Paste the SQL above
6. Click "Run"

### Option 2: Railway CLI

```bash
# Install Railway CLI (if not already installed)
npm install -g @railway/cli

# Login and link project
railway login
cd lien-api-landing
railway link

# Connect to PostgreSQL
railway run psql $DATABASE_URL
```

Then paste the SQL commands above.

### Option 3: Direct psql Connection

```bash
# Get database URL from Railway dashboard
# Then connect:
psql $DATABASE_URL

# Or if you have the connection string:
psql postgresql://user:password@host:port/database
```

---

## Table Structure Explanation

### Columns:

- **id**: Auto-incrementing primary key (SERIAL)
- **broker_id**: References `brokers.referral_code` (the broker's referral code)
- **broker_email**: Broker's email address
- **customer_email**: Customer who signed up via referral
- **customer_stripe_id**: Stripe customer ID
- **amount**: Customer payment amount ($299.00)
- **payout**: Broker commission amount ($500 or $50)
- **payout_type**: 'bounty' ($500 one-time) or 'recurring' ($50/month)
- **status**: 
  - `on_hold` - 30-day churn protection
  - `pending` - Ready for payout
  - `paid` - Commission paid
  - `flagged_for_review` - Fraud detected
- **fraud_flags**: JSON string with fraud detection results
- **hold_until**: Date when 30-day hold expires
- **clawback_until**: Date when 90-day clawback period expires
- **created_at**: When referral was created
- **paid_at**: When commission was paid

### Status Flow:

```
on_hold (30 days) → pending → paid
         ↓
flagged_for_review (manual review)
```

---

## Verification

After running the migration, verify with:

```sql
-- Check table exists
SELECT table_name FROM information_schema.tables 
WHERE table_name = 'referrals';

-- Check columns
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'referrals'
ORDER BY ordinal_position;

-- Check indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'referrals';

-- Check foreign key
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = 'referrals';
```

---

## Troubleshooting

**Error: "relation brokers does not exist"**
- Run the brokers table migration first
- Check that brokers table exists: `SELECT * FROM brokers LIMIT 1;`

**Error: "column referral_code does not exist in brokers"**
- Ensure brokers table has referral_code column
- May need to run earlier migrations

**Error: "duplicate key value violates unique constraint"**
- Table might already exist
- Check with: `SELECT * FROM referrals LIMIT 1;`
- If exists, migration is already applied

---

## Next Steps

After creating the table:

1. ✅ Test broker approval flow
2. ✅ Test customer signup with referral
3. ✅ Verify referrals are tracked in database
4. ✅ Check dashboard shows referrals correctly

