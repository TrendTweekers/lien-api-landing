# setup_db.py - One-time database setup
import sqlite3
import os

# Get the database path (works in both local and Railway environments)
db_path = os.getenv("DATABASE_PATH", "liendeadline.db")

# Create database and tables
con = sqlite3.connect(db_path)

# Test keys table (with dual limits: 50 calls OR 7 days)
con.execute("""
    CREATE TABLE IF NOT EXISTS test_keys(
        key TEXT PRIMARY KEY,
        email TEXT,
        expiry_date TEXT,
        max_calls INTEGER DEFAULT 50,
        calls_used INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

# Brokers table
con.execute("""
    CREATE TABLE IF NOT EXISTS brokers(
        id TEXT PRIMARY KEY,
        email TEXT,
        name TEXT,
        model TEXT,
        referrals INTEGER DEFAULT 0,
        earned REAL DEFAULT 0
    )
""")

# Customers table
con.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        email TEXT PRIMARY KEY,
        api_calls INTEGER DEFAULT 0,
        status TEXT DEFAULT 'active',
        broker_ref TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")

# Referrals table (for tracking broker referrals and payouts)
con.execute("""
    CREATE TABLE IF NOT EXISTS referrals(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        broker_ref TEXT,
        customer_email TEXT,
        customer_id TEXT,
        amount REAL,
        status TEXT DEFAULT 'pending',
        date TEXT DEFAULT CURRENT_TIMESTAMP,
        paid_at TEXT,
        stripe_transfer_id TEXT,
        days_active INTEGER,
        FOREIGN KEY (broker_ref) REFERENCES brokers(id)
    )
""")

# Add stripe_account_id to brokers table if it doesn't exist
con.execute("""
    CREATE TABLE IF NOT EXISTS brokers_new(
        id TEXT PRIMARY KEY,
        email TEXT,
        name TEXT,
        model TEXT,
        referrals INTEGER DEFAULT 0,
        earned REAL DEFAULT 0,
        stripe_account_id TEXT
    )
""")

# Migrate existing brokers data if table exists
try:
    con.execute("""
        INSERT INTO brokers_new(id, email, name, model, referrals, earned, stripe_account_id)
        SELECT id, email, name, model, referrals, earned, NULL FROM brokers
    """)
    con.execute("DROP TABLE brokers")
    con.execute("ALTER TABLE brokers_new RENAME TO brokers")
except:
    pass

con.commit()
con.close()

print("✅ Database setup complete!")
print("Tables created: test_keys, brokers, customers, referrals")

