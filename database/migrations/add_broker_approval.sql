-- Add approval columns to partner_applications if they don't exist
-- SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS, so we'll use a different approach
-- This will be handled in Python code

CREATE TABLE IF NOT EXISTS approved_brokers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_application_id INTEGER NOT NULL,
    email TEXT NOT NULL UNIQUE,
    referral_code TEXT UNIQUE NOT NULL,
    commission_type TEXT NOT NULL, -- 'bounty' or 'recurring'
    total_referrals INTEGER DEFAULT 0,
    total_earnings REAL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_approved_brokers_email ON approved_brokers(email);
CREATE INDEX IF NOT EXISTS idx_approved_brokers_referral_code ON approved_brokers(referral_code);

