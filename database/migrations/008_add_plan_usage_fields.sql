-- Migration: Add plan and usage tracking fields to users table

-- PostgreSQL
DO $$
BEGIN
    -- Add plan column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'users' 
        AND column_name = 'plan'
    ) THEN
        ALTER TABLE users ADD COLUMN plan VARCHAR(20) DEFAULT 'free' CHECK (plan IN ('free', 'basic', 'automated', 'enterprise'));
    END IF;
    
    -- Add usage_month column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'users' 
        AND column_name = 'usage_month'
    ) THEN
        ALTER TABLE users ADD COLUMN usage_month DATE DEFAULT DATE_TRUNC('month', CURRENT_DATE);
    END IF;
    
    -- Add manual_calc_count column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'users' 
        AND column_name = 'manual_calc_count'
    ) THEN
        ALTER TABLE users ADD COLUMN manual_calc_count INTEGER DEFAULT 0;
    END IF;
    
    -- Add api_call_count column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'users' 
        AND column_name = 'api_call_count'
    ) THEN
        ALTER TABLE users ADD COLUMN api_call_count INTEGER DEFAULT 0;
    END IF;
    
    -- Add zapier_webhook_count column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'users' 
        AND column_name = 'zapier_webhook_count'
    ) THEN
        ALTER TABLE users ADD COLUMN zapier_webhook_count INTEGER DEFAULT 0;
    END IF;
    
    -- Update existing users to have current month as usage_month
    UPDATE users SET usage_month = DATE_TRUNC('month', CURRENT_DATE) WHERE usage_month IS NULL;
    
    RAISE NOTICE 'Added plan and usage tracking fields to users table';
END $$;

-- SQLite
-- Note: SQLite doesn't support CHECK constraints in ALTER TABLE, so we'll add columns without them
-- The application logic will enforce the enum values

-- Check if columns exist before adding (SQLite doesn't have IF NOT EXISTS for ALTER TABLE)
-- We'll use a pragma check or just try to add and catch errors
-- For SQLite, we'll add columns one by one and handle errors

-- Add plan column
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we check first
-- This is a simplified version - in practice, you'd check programmatically

-- Note: SQLite migration should be handled programmatically in Python
-- This SQL file is primarily for PostgreSQL

