-- Migration: Add Zapier API token fields to users table
-- This migration is idempotent and safe to run multiple times

-- For PostgreSQL
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'zapier_token_hash'
    ) THEN
        ALTER TABLE users ADD COLUMN zapier_token_hash TEXT;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'zapier_token_last4'
    ) THEN
        ALTER TABLE users ADD COLUMN zapier_token_last4 TEXT;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'zapier_token_created_at'
    ) THEN
        ALTER TABLE users ADD COLUMN zapier_token_created_at TIMESTAMP;
    END IF;
    
    -- Create index on zapier_token_hash for faster lookups
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_indexes 
        WHERE tablename = 'users' 
        AND indexname = 'idx_users_zapier_token_hash'
    ) THEN
        CREATE INDEX idx_users_zapier_token_hash ON users(zapier_token_hash);
    END IF;
END $$;

-- For SQLite (handled in application code with try/except)
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN
-- The application will handle this gracefully
-- Index creation for SQLite (CREATE INDEX IF NOT EXISTS is supported)
CREATE INDEX IF NOT EXISTS idx_users_zapier_token_hash ON users(zapier_token_hash);

