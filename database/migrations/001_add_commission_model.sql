-- Migration: Add commission_model column to partner_applications if it doesn't exist
-- This migration is idempotent and safe to run multiple times

-- For SQLite
-- Check if column exists (SQLite doesn't support IF NOT EXISTS for ALTER TABLE ADD COLUMN)
-- We'll use a try-catch approach in the application code

-- For PostgreSQL
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'partner_applications' 
        AND column_name = 'commission_model'
    ) THEN
        ALTER TABLE partner_applications ADD COLUMN commission_model TEXT DEFAULT 'bounty';
    END IF;
END $$;

-- Update existing records to have default value
UPDATE partner_applications SET commission_model = 'bounty' WHERE commission_model IS NULL;

