-- Migration: Create referrals table for broker referral tracking
-- PostgreSQL compatible (uses SERIAL, not AUTOINCREMENT)

-- Create referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    broker_id VARCHAR(255) NOT NULL,
    broker_email VARCHAR(255) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    customer_stripe_id VARCHAR(255),
    amount DECIMAL(10,2) NOT NULL DEFAULT 299.00,
    payout DECIMAL(10,2) NOT NULL,
    payout_type VARCHAR(50) NOT NULL,  -- 'bounty' or 'recurring'
    status VARCHAR(50) DEFAULT 'on_hold',  -- 'on_hold', 'pending', 'paid', 'flagged_for_review'
    fraud_flags TEXT,  -- JSON string with fraud detection results
    hold_until DATE,  -- 30-day anti-churn protection
    clawback_until DATE,  -- 90-day fraud protection
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

-- Add comment to table
COMMENT ON TABLE referrals IS 'Tracks broker referrals and commissions with fraud protection';
COMMENT ON COLUMN referrals.status IS 'on_hold (30-day churn protection) → pending → paid';
COMMENT ON COLUMN referrals.payout_type IS 'bounty ($500 one-time) or recurring ($50/month)';
COMMENT ON COLUMN referrals.hold_until IS 'Date when 30-day churn protection expires';
COMMENT ON COLUMN referrals.clawback_until IS 'Date when 90-day fraud protection expires';

