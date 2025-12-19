-- Migration: Add short_code column to brokers table
-- Run this in Railway PostgreSQL console or via migration script

-- Add short_code column
ALTER TABLE brokers ADD COLUMN IF NOT EXISTS short_code VARCHAR(10) UNIQUE;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_brokers_short_code ON brokers(short_code);

-- Create clicks tracking table (optional but recommended)
CREATE TABLE IF NOT EXISTS referral_clicks (
    id SERIAL PRIMARY KEY,
    short_code VARCHAR(10) NOT NULL,
    broker_id INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    referrer_url TEXT,
    clicked_at TIMESTAMP DEFAULT NOW(),
    converted BOOLEAN DEFAULT FALSE,
    conversion_date TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON referral_clicks(short_code);
CREATE INDEX IF NOT EXISTS idx_clicks_broker ON referral_clicks(broker_id);

-- Generate short codes for existing brokers (run after Python code generates them)
-- This will be done programmatically via the admin approval process

