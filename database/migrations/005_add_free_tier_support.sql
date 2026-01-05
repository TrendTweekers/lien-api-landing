-- Migration: Add free tier support to users table
-- Adds calculations_used column to track free tier usage

-- PostgreSQL
DO $$ 
BEGIN
    -- Add calculations_used column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'calculations_used'
    ) THEN
        ALTER TABLE users ADD COLUMN calculations_used INTEGER DEFAULT 0;
    END IF;
END $$;

-- SQLite (run separately if using SQLite)
-- ALTER TABLE users ADD COLUMN calculations_used INTEGER DEFAULT 0;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_subscription_status ON users(subscription_status);
CREATE INDEX IF NOT EXISTS idx_users_calculations_used ON users(calculations_used);

