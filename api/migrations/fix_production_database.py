"""
EMERGENCY FIX: Rebuild database schema and populate all 51 states

This script:
1. Creates customers table if missing
2. Creates api_keys table if missing  
3. Ensures lien_deadlines table exists
4. Populates all 51 states (50 US states + DC)

Usage:
    From project root:
        python api/migrations/fix_production_database.py
    
    Or from Railway:
        railway run python api/migrations/fix_production_database.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import from api module
script_dir = Path(__file__).resolve().parent
api_dir = script_dir.parent
project_root = api_dir.parent
sys.path.insert(0, str(project_root))

# Import database functions
from api.database import get_db, get_db_cursor, DB_TYPE

def populate_all_states(cursor):
    """Add all 51 states to lien_deadlines table if they don't exist"""
    
    # All 51 states with their codes
    all_states = [
        ('AL', 'Alabama'), ('AK', 'Alaska'), ('AZ', 'Arizona'), ('AR', 'Arkansas'),
        ('CA', 'California'), ('CO', 'Colorado'), ('CT', 'Connecticut'), ('DE', 'Delaware'),
        ('DC', 'District of Columbia'), ('FL', 'Florida'), ('GA', 'Georgia'), ('HI', 'Hawaii'),
        ('ID', 'Idaho'), ('IL', 'Illinois'), ('IN', 'Indiana'), ('IA', 'Iowa'),
        ('KS', 'Kansas'), ('KY', 'Kentucky'), ('LA', 'Louisiana'), ('ME', 'Maine'),
        ('MD', 'Maryland'), ('MA', 'Massachusetts'), ('MI', 'Michigan'), ('MN', 'Minnesota'),
        ('MS', 'Mississippi'), ('MO', 'Missouri'), ('MT', 'Montana'), ('NE', 'Nebraska'),
        ('NV', 'Nevada'), ('NH', 'New Hampshire'), ('NJ', 'New Jersey'), ('NM', 'New Mexico'),
        ('NY', 'New York'), ('NC', 'North Carolina'), ('ND', 'North Dakota'), ('OH', 'Ohio'),
        ('OK', 'Oklahoma'), ('OR', 'Oregon'), ('PA', 'Pennsylvania'), ('RI', 'Rhode Island'),
        ('SC', 'South Carolina'), ('SD', 'South Dakota'), ('TN', 'Tennessee'), ('TX', 'Texas'),
        ('UT', 'Utah'), ('VT', 'Vermont'), ('VA', 'Virginia'), ('WA', 'Washington'),
        ('WV', 'West Virginia'), ('WI', 'Wisconsin'), ('WY', 'Wyoming')
    ]
    
    states_added = 0
    for state_code, state_name in all_states:
        # Check if state exists
        if DB_TYPE == 'postgresql':
            cursor.execute("SELECT state_code FROM lien_deadlines WHERE state_code = %s", (state_code,))
        else:
            cursor.execute("SELECT state_code FROM lien_deadlines WHERE state_code = ?", (state_code,))
        
        existing = cursor.fetchone()
        if not existing:
            # Add state with default values (120 days for lien, no prelim for most states)
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        INSERT INTO lien_deadlines 
                        (state_code, state_name, preliminary_notice_required, preliminary_notice_days, lien_filing_days)
                        VALUES (%s, %s, false, NULL, 120)
                        ON CONFLICT (state_code) DO NOTHING
                    """, (state_code, state_name))
                else:
                    # SQLite doesn't support ON CONFLICT DO NOTHING in older versions, so check again
                    cursor.execute("""
                        INSERT INTO lien_deadlines 
                        (state_code, state_name, preliminary_notice_required, preliminary_notice_days, lien_filing_days)
                        VALUES (?, ?, 0, NULL, 120)
                    """, (state_code, state_name))
                print(f"   ✅ Added {state_name} ({state_code})")
                states_added += 1
            except Exception as e:
                # State might have been added by another process, skip it
                error_msg = str(e)[:50] if e else "Unknown"
                if "duplicate" in error_msg.lower() or "unique" in error_msg.lower():
                    # Expected error, state already exists
                    pass
                else:
                    # Unexpected error, log it but continue
                    print(f"   ⚠️ Error adding {state_code}: {error_msg}")
    
    if states_added > 0:
        print(f"   📊 Added {states_added} new states")
    else:
        print("   ✅ All 51 states already present")

def safe_fetch_value(cursor_result, index=0):
    """Safely extract value from cursor result (handles both dict and tuple)"""
    if cursor_result is None:
        return None
    if isinstance(cursor_result, dict):
        # Dict-like result (SQLAlchemy)
        keys = list(cursor_result.keys())
        if keys:
            return cursor_result[keys[index]]
        return None
    elif isinstance(cursor_result, (tuple, list)):
        # Tuple/list result
        return cursor_result[index] if len(cursor_result) > index else None
    else:
        # Try to access as index
        try:
            return cursor_result[index]
        except (KeyError, TypeError):
            return cursor_result

def main():
    print("=" * 60)
    print("🔧 EMERGENCY DATABASE FIX")
    print("=" * 60)
    print(f"Database Type: {DB_TYPE}")
    print()
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Step 1: Create customers table if missing
            print("1️⃣ Checking customers table...")
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'customers'
                        )
                    """)
                    result = cursor.fetchone()
                    table_exists = safe_fetch_value(result, 0) if result else False
                else:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customers'")
                    table_exists = cursor.fetchone() is not None
                
                if not table_exists:
                    print("   Creating customers table...")
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            CREATE TABLE customers (
                                id SERIAL PRIMARY KEY,
                                email VARCHAR(255) UNIQUE NOT NULL,
                                stripe_customer_id VARCHAR(255),
                                subscription_id VARCHAR(255),
                                status VARCHAR(50) DEFAULT 'active',
                                plan VARCHAR(50) DEFAULT 'unlimited',
                                amount REAL DEFAULT 299.00,
                                calls_used INTEGER DEFAULT 0,
                                api_key VARCHAR(255) UNIQUE,
                                created_at TIMESTAMP DEFAULT NOW()
                            )
                        """)
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_stripe ON customers(stripe_customer_id)")
                    else:
                        cursor.execute("""
                            CREATE TABLE customers (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                email TEXT UNIQUE NOT NULL,
                                stripe_customer_id TEXT,
                                subscription_id TEXT,
                                status TEXT DEFAULT 'active',
                                plan TEXT DEFAULT 'unlimited',
                                amount REAL DEFAULT 299.00,
                                calls_used INTEGER DEFAULT 0,
                                api_key TEXT UNIQUE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_stripe ON customers(stripe_customer_id)")
                    conn.commit()
                    print("   ✅ Customers table created")
                else:
                    print("   ✅ Customers table exists")
                    
                    # Check if api_key column exists
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name='customers' AND column_name='api_key'
                        """)
                        if not cursor.fetchone():
                            cursor.execute("ALTER TABLE customers ADD COLUMN api_key VARCHAR(255) UNIQUE")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)")
                            conn.commit()
                            print("   ✅ Added api_key column to customers table")
                    else:
                        cursor.execute("PRAGMA table_info(customers)")
                        columns = []
                        for row in cursor.fetchall():
                            col_name = row.get('name') if isinstance(row, dict) else (row[1] if isinstance(row, (tuple, list)) and len(row) > 1 else None)
                            if col_name:
                                columns.append(col_name)
                        if 'api_key' not in columns:
                            cursor.execute("ALTER TABLE customers ADD COLUMN api_key TEXT UNIQUE")
                            cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_api_key ON customers(api_key)")
                            conn.commit()
                            print("   ✅ Added api_key column to customers table")
            except Exception as e:
                print(f"   ⚠️ Customers table error: {e}")
                conn.rollback()
            
            # Step 2: Create api_keys table if missing
            print("\n2️⃣ Checking api_keys table...")
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'api_keys'
                        )
                    """)
                    result = cursor.fetchone()
                    table_exists = safe_fetch_value(result, 0) if result else False
                else:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'")
                    table_exists = cursor.fetchone() is not None
                
                if not table_exists:
                    print("   Creating api_keys table...")
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            CREATE TABLE api_keys (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER,
                                customer_email VARCHAR(255) NOT NULL,
                                api_key VARCHAR(255) UNIQUE NOT NULL,
                                created_at TIMESTAMP DEFAULT NOW(),
                                last_used_at TIMESTAMP,
                                is_active BOOLEAN DEFAULT TRUE,
                                calls_count INTEGER DEFAULT 0
                            )
                        """)
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(api_key)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_email ON api_keys(customer_email)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
                    else:
                        cursor.execute("""
                            CREATE TABLE api_keys (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER,
                                customer_email TEXT NOT NULL,
                                api_key TEXT UNIQUE NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                last_used_at TIMESTAMP,
                                is_active INTEGER DEFAULT 1,
                                calls_count INTEGER DEFAULT 0
                            )
                        """)
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(api_key)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_email ON api_keys(customer_email)")
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
                    conn.commit()
                    print("   ✅ API keys table created")
                else:
                    print("   ✅ API keys table exists")
            except Exception as e:
                print(f"   ⚠️ API keys table error: {e}")
                conn.rollback()
            
            # Step 3: Check lien_deadlines table
            print("\n3️⃣ Checking lien_deadlines table...")
            try:
                if DB_TYPE == 'postgresql':
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = 'lien_deadlines'
                        )
                    """)
                    result = cursor.fetchone()
                    table_exists = safe_fetch_value(result, 0) if result else False
                else:
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lien_deadlines'")
                    table_exists = cursor.fetchone() is not None
                
                if not table_exists:
                    print("   Creating lien_deadlines table...")
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            CREATE TABLE lien_deadlines (
                                id SERIAL PRIMARY KEY,
                                state_code VARCHAR(2) UNIQUE NOT NULL,
                                state_name VARCHAR(50) NOT NULL,
                                preliminary_notice_required BOOLEAN DEFAULT FALSE,
                                preliminary_notice_days INTEGER,
                                preliminary_notice_formula TEXT,
                                preliminary_notice_deadline_description TEXT,
                                preliminary_notice_statute TEXT,
                                lien_filing_days INTEGER,
                                lien_filing_formula TEXT,
                                lien_filing_deadline_description TEXT,
                                lien_filing_statute TEXT,
                                weekend_extension BOOLEAN DEFAULT FALSE,
                                holiday_extension BOOLEAN DEFAULT FALSE,
                                residential_vs_commercial BOOLEAN DEFAULT FALSE,
                                notice_of_completion_trigger BOOLEAN DEFAULT FALSE,
                                notes TEXT,
                                last_updated TIMESTAMP DEFAULT NOW()
                            )
                        """)
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lien_deadlines_state_code ON lien_deadlines(state_code)")
                    else:
                        cursor.execute("""
                            CREATE TABLE lien_deadlines (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                state_code TEXT UNIQUE NOT NULL,
                                state_name TEXT NOT NULL,
                                preliminary_notice_required INTEGER DEFAULT 0,
                                preliminary_notice_days INTEGER,
                                preliminary_notice_formula TEXT,
                                preliminary_notice_deadline_description TEXT,
                                preliminary_notice_statute TEXT,
                                lien_filing_days INTEGER,
                                lien_filing_formula TEXT,
                                lien_filing_deadline_description TEXT,
                                lien_filing_statute TEXT,
                                weekend_extension INTEGER DEFAULT 0,
                                holiday_extension INTEGER DEFAULT 0,
                                residential_vs_commercial INTEGER DEFAULT 0,
                                notice_of_completion_trigger INTEGER DEFAULT 0,
                                notes TEXT,
                                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lien_deadlines_state_code ON lien_deadlines(state_code)")
                    conn.commit()
                    print("   ✅ lien_deadlines table created")
                
                # Check current state count
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    result = cursor.fetchone()
                    current_count = safe_fetch_value(result, 0) if result else 0
                else:
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    result = cursor.fetchone()
                    current_count = safe_fetch_value(result, 0) if result else 0
                
                print(f"   📊 Current states in database: {current_count}")
                
                # Step 4: Ensure all 51 states exist (add missing ones)
                print("\n4️⃣ Ensuring all 51 states exist...")
                
                # Check current count first
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    result = cursor.fetchone()
                    check_count = safe_fetch_value(result, 0) if result else 0
                else:
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    result = cursor.fetchone()
                    check_count = safe_fetch_value(result, 0) if result else 0
                
                if check_count >= 51:
                    print(f"   ✅ All 51 states already present ({check_count} states found)")
                else:
                    print(f"   📊 Found {check_count} states, adding missing ones...")
                    try:
                        populate_all_states(cursor)
                        conn.commit()
                        
                        # Verify new count
                        if DB_TYPE == 'postgresql':
                            cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                            result = cursor.fetchone()
                            new_count = safe_fetch_value(result, 0) if result else 0
                        else:
                            cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                            result = cursor.fetchone()
                            new_count = safe_fetch_value(result, 0) if result else 0
                        print(f"   ✅ Now have {new_count} states")
                    except Exception as e:
                        # States likely already exist, this is fine
                        error_msg = str(e)[:100] if e else "Unknown error"
                        print(f"   ⚠️ Error adding states (might already exist): {error_msg}")
                        conn.rollback()
                        pass  # Continue with migration
                
                # Step 5: Repopulate all 51 states with full data
                # Check current count again (might have changed after Step 4)
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    result = cursor.fetchone()
                    final_count = safe_fetch_value(result, 0) if result else 0
                else:
                    cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                    result = cursor.fetchone()
                    final_count = safe_fetch_value(result, 0) if result else 0
                
                if final_count >= 51:
                    print("\n5️⃣ State data already complete, skipping repopulation")
                    print(f"   ✅ All 51 states present with data")
                else:
                    print(f"\n5️⃣ Repopulating all 51 states with full data...")
                    print(f"   📊 Current count: {final_count}, repopulating...")
                    
                    # Clear existing states
                    cursor.execute("DELETE FROM lien_deadlines")
                    conn.commit()
                    print("   🗑️ Cleared existing states")
                    
                    # Import state data from add_all_states.py
                    from api.migrations.add_all_states import STATE_DATA
                    
                    states_inserted = 0
                    for state_info in STATE_DATA["states"]:
                    prelim = state_info.get("preliminary_notice", {})
                    lien = state_info.get("lien_filing", {})
                    special = state_info.get("special_rules", {})
                    
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            INSERT INTO lien_deadlines (
                                state_code, state_name,
                                preliminary_notice_required,
                                preliminary_notice_days,
                                preliminary_notice_formula,
                                preliminary_notice_deadline_description,
                                preliminary_notice_statute,
                                lien_filing_days,
                                lien_filing_formula,
                                lien_filing_deadline_description,
                                lien_filing_statute,
                                weekend_extension,
                                holiday_extension,
                                residential_vs_commercial,
                                notice_of_completion_trigger,
                                notes
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                        """, (
                            state_info["state_code"],
                            state_info["state_name"],
                            prelim.get("required", False),
                            prelim.get("deadline_days"),
                            prelim.get("deadline_formula"),
                            prelim.get("deadline_description"),
                            prelim.get("statute"),
                            lien.get("deadline_days"),
                            lien.get("deadline_formula"),
                            lien.get("deadline_description"),
                            lien.get("statute"),
                            special.get("weekend_extension", False),
                            special.get("holiday_extension", False),
                            special.get("residential_vs_commercial", False),
                            special.get("notice_of_completion_trigger", False),
                            special.get("notes", "")
                        ))
                    else:
                        cursor.execute("""
                            INSERT INTO lien_deadlines (
                                state_code, state_name,
                                preliminary_notice_required,
                                preliminary_notice_days,
                                preliminary_notice_formula,
                                preliminary_notice_deadline_description,
                                preliminary_notice_statute,
                                lien_filing_days,
                                lien_filing_formula,
                                lien_filing_deadline_description,
                                lien_filing_statute,
                                weekend_extension,
                                holiday_extension,
                                residential_vs_commercial,
                                notice_of_completion_trigger,
                                notes
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                            )
                        """, (
                            state_info["state_code"],
                            state_info["state_name"],
                            1 if prelim.get("required", False) else 0,
                            prelim.get("deadline_days"),
                            prelim.get("deadline_formula"),
                            prelim.get("deadline_description"),
                            prelim.get("statute"),
                            lien.get("deadline_days"),
                            lien.get("deadline_formula"),
                            lien.get("deadline_description"),
                            lien.get("statute"),
                            1 if special.get("weekend_extension", False) else 0,
                            1 if special.get("holiday_extension", False) else 0,
                            1 if special.get("residential_vs_commercial", False) else 0,
                            1 if special.get("notice_of_completion_trigger", False) else 0,
                            special.get("notes", "")
                        ))
                        states_inserted += 1
                    
                    conn.commit()
                    print(f"   ✅ Inserted {states_inserted} states")
                    
                    # Verify count
                    if DB_TYPE == 'postgresql':
                        cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                        result = cursor.fetchone()
                        verify_count = safe_fetch_value(result, 0) if result else 0
                    else:
                        cursor.execute("SELECT COUNT(*) FROM lien_deadlines")
                        result = cursor.fetchone()
                        verify_count = safe_fetch_value(result, 0) if result else 0
                    
                    print(f"   📊 Final state count: {verify_count}")
                
                # Verify Hawaii specifically
                if DB_TYPE == 'postgresql':
                    cursor.execute("SELECT state_code, state_name, lien_filing_days FROM lien_deadlines WHERE state_code = 'HI'")
                else:
                    cursor.execute("SELECT state_code, state_name, lien_filing_days FROM lien_deadlines WHERE state_code = 'HI'")
                hawaii = cursor.fetchone()
                
                if hawaii:
                    if isinstance(hawaii, dict):
                        state_name = hawaii.get('state_name')
                        lien_days = hawaii.get('lien_filing_days')
                    elif isinstance(hawaii, (tuple, list)):
                        state_name = hawaii[1] if len(hawaii) > 1 else None
                        lien_days = hawaii[2] if len(hawaii) > 2 else None
                    else:
                        state_name = None
                        lien_days = None
                    print(f"   ✅ Hawaii verified: {state_name} - {lien_days} days")
                else:
                    print("   ❌ Hawaii not found!")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                conn.rollback()
                raise
        
        print("\n" + "=" * 60)
        print("🎉 DATABASE FIX COMPLETE!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

