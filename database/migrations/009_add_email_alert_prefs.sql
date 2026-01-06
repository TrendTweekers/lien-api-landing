-- Migration: Add email alert preferences to users table
-- Adds alert_email and email_alerts_enabled columns
-- Creates email_alert_sends table for tracking sent reminders

-- PostgreSQL
DO $$
BEGIN
    -- Add alert_email column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'users' 
        AND column_name = 'alert_email'
    ) THEN
        ALTER TABLE users ADD COLUMN alert_email TEXT;
    END IF;
    
    -- Add email_alerts_enabled column if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'users' 
        AND column_name = 'email_alerts_enabled'
    ) THEN
        ALTER TABLE users ADD COLUMN email_alerts_enabled BOOLEAN NOT NULL DEFAULT TRUE;
    END IF;
    
    -- Create email_alert_sends table if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'email_alert_sends'
    ) THEN
        CREATE TABLE email_alert_sends (
            id BIGSERIAL PRIMARY KEY,
            user_id UUID NOT NULL,
            project_id UUID NOT NULL,
            deadline_type TEXT NOT NULL,     -- 'prelim' | 'lien'
            days_before INTEGER NOT NULL,    -- 7 | 3 | 1
            deadline_date DATE NOT NULL,
            sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (user_id, project_id, deadline_type, days_before, deadline_date)
        );
        
        -- Add index for faster lookups
        CREATE INDEX IF NOT EXISTS idx_email_alert_sends_user_project 
            ON email_alert_sends(user_id, project_id);
    END IF;
    
    RAISE NOTICE 'Added email alert preferences to users table';
END $$;

-- SQLite
-- Note: SQLite migration should be handled programmatically in Python
-- This SQL file is primarily for PostgreSQL

