-- Migration: Add zapier_notification_events table for reminder deduplication
-- Prevents duplicate Slack/email notifications for the same deadline reminder

-- PostgreSQL
DO $$ 
BEGIN
    -- Create table if it doesn't exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'zapier_notification_events'
    ) THEN
        CREATE TABLE zapier_notification_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            reminder_type TEXT NOT NULL CHECK (reminder_type IN ('prelim','lien')),
            reminder_days INTEGER NOT NULL,
            deadline_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id, project_id, reminder_type, reminder_days, deadline_date)
        );
        
        -- Create indexes for faster lookups
        CREATE INDEX idx_zapier_notif_user_created ON zapier_notification_events(user_id, created_at DESC);
        CREATE INDEX idx_zapier_notif_user_deadline ON zapier_notification_events(user_id, deadline_date);
        
        RAISE NOTICE 'Created zapier_notification_events table';
    ELSE
        RAISE NOTICE 'Table zapier_notification_events already exists';
    END IF;
END $$;

-- SQLite (run separately if using SQLite)
-- CREATE TABLE IF NOT EXISTS zapier_notification_events (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     user_id INTEGER NOT NULL,
--     project_id INTEGER NOT NULL,
--     reminder_type TEXT NOT NULL CHECK (reminder_type IN ('prelim','lien')),
--     reminder_days INTEGER NOT NULL,
--     deadline_date DATE NOT NULL,
--     created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(user_id, project_id, reminder_type, reminder_days, deadline_date)
-- );
-- 
-- CREATE INDEX IF NOT EXISTS idx_zapier_notif_user_created ON zapier_notification_events(user_id, created_at DESC);
-- CREATE INDEX IF NOT EXISTS idx_zapier_notif_user_deadline ON zapier_notification_events(user_id, deadline_date);

