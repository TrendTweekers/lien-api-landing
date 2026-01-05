-- Migration: Create notification_settings table for project-level reminder configuration
-- Supports multiple reminders per project with configurable channels (email, slack, zapier)

-- PostgreSQL
DO $$
BEGIN
    CREATE TABLE IF NOT EXISTS notification_settings (
        id SERIAL PRIMARY KEY,
        project_id INTEGER NOT NULL,
        reminders JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE (project_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_notification_settings_project_id ON notification_settings(project_id);
    CREATE INDEX IF NOT EXISTS idx_notification_settings_updated_at ON notification_settings(updated_at);
    
    -- Add comment
    COMMENT ON TABLE notification_settings IS 'Per-project notification settings for deadline reminders';
    COMMENT ON COLUMN notification_settings.reminders IS 'JSON array of reminder configs: [{"offset_days": 7, "channels": {"email": true, "slack": false, "zapier": false}}]';
END $$;

-- SQLite
CREATE TABLE IF NOT EXISTS notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL UNIQUE,
    reminders TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notification_settings_project_id ON notification_settings(project_id);
CREATE INDEX IF NOT EXISTS idx_notification_settings_updated_at ON notification_settings(updated_at);

