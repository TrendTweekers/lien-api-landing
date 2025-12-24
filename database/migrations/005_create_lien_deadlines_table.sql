-- Create lien_deadlines table for all 50 US states + DC
-- PostgreSQL version
CREATE TABLE IF NOT EXISTS lien_deadlines (
    id SERIAL PRIMARY KEY,
    state_code VARCHAR(2) UNIQUE NOT NULL,
    state_name VARCHAR(50) NOT NULL,
    
    -- Preliminary Notice
    preliminary_notice_required BOOLEAN DEFAULT FALSE,
    preliminary_notice_days INTEGER,
    preliminary_notice_formula TEXT,
    preliminary_notice_deadline_description TEXT,
    preliminary_notice_statute TEXT,
    
    -- Lien Filing
    lien_filing_days INTEGER,
    lien_filing_formula TEXT,
    lien_filing_deadline_description TEXT,
    lien_filing_statute TEXT,
    
    -- Special Rules
    weekend_extension BOOLEAN DEFAULT FALSE,
    holiday_extension BOOLEAN DEFAULT FALSE,
    residential_vs_commercial BOOLEAN DEFAULT FALSE,
    notice_of_completion_trigger BOOLEAN DEFAULT FALSE,
    notes TEXT,
    
    -- Metadata
    last_updated TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_state_code UNIQUE (state_code)
);

CREATE INDEX IF NOT EXISTS idx_lien_deadlines_state_code ON lien_deadlines(state_code);
CREATE INDEX IF NOT EXISTS idx_lien_deadlines_state_name ON lien_deadlines(state_name);

