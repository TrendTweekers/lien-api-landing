CREATE TABLE IF NOT EXISTS email_gate_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address TEXT NOT NULL,
    email TEXT,
    calculation_count INTEGER DEFAULT 1,
    first_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_calculation_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    email_captured_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_email_gate_ip ON email_gate_tracking(ip_address);
CREATE INDEX idx_email_gate_email ON email_gate_tracking(email);

