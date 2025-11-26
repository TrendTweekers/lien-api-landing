-- Users table (paying customers)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    stripe_customer_id TEXT UNIQUE,
    subscription_status TEXT DEFAULT 'active',
    subscription_id TEXT,
    session_token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Customers table (for admin tracking)
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    stripe_customer_id TEXT UNIQUE,
    subscription_id TEXT,
    status TEXT DEFAULT 'active',
    plan TEXT DEFAULT 'unlimited',
    amount REAL DEFAULT 299.00,
    calls_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Brokers table
CREATE TABLE IF NOT EXISTS brokers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    commission REAL DEFAULT 500.00,
    referrals INTEGER DEFAULT 0,
    earned REAL DEFAULT 0.00,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker_id TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_id TEXT,
    amount REAL,
    payout REAL,
    status TEXT DEFAULT 'pending',
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (broker_id) REFERENCES brokers(id)
);

-- Test keys table
CREATE TABLE IF NOT EXISTS test_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    api_key TEXT UNIQUE NOT NULL,
    calls_used INTEGER DEFAULT 0,
    calls_limit INTEGER DEFAULT 10,
    expires TIMESTAMP NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- API usage logs
CREATE TABLE IF NOT EXISTS api_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT,
    api_key TEXT,
    endpoint TEXT,
    state TEXT,
    notice_date TEXT,
    response_code INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

