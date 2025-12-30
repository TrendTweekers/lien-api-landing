import os
import sys
import logging

# Add project root to path
sys.path.append(os.getcwd())

try:
    from api.database import get_db, DB_TYPE, get_db_cursor
except ImportError:
    # Fallback if run from different directory structure
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from api.database import get_db, DB_TYPE, get_db_cursor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_schema():
    print(f"🚀 Starting schema fix migration on {DB_TYPE.upper()} database...")
    
    with get_db() as conn:
        cursor = get_db_cursor(conn)
        
        # 1. Fix Brokers Table
        print("\n🔧 Checking BROKERS table...")
        brokers_columns = [
            ("created_at", "TIMESTAMP DEFAULT NOW()"),
            ("total_referrals", "INTEGER DEFAULT 0"),
            ("total_earned", "DECIMAL(10,2) DEFAULT 0.00"),
            ("short_code", "VARCHAR(10)"),
            ("referral_link", "VARCHAR(500)"),
            ("password_hash", "VARCHAR(500)"),
            ("payment_method", "VARCHAR(50)"),
            ("payment_email", "VARCHAR(255)"),
            ("iban", "VARCHAR(255)"),
            ("swift_code", "VARCHAR(255)"),
            ("bank_name", "VARCHAR(255)"),
            ("bank_address", "TEXT"),
            ("account_holder_name", "VARCHAR(255)"),
            ("crypto_wallet", "VARCHAR(255)"),
            ("crypto_currency", "VARCHAR(50)"),
            ("tax_id", "VARCHAR(255)"),
            ("stripe_customer_id", "VARCHAR(255)"),
            ("ip_address", "VARCHAR(50)")
        ]
        
        for col_name, col_def in brokers_columns:
            add_column(cursor, "brokers", col_name, col_def)

        # 2. Fix Customers Table
        print("\n🔧 Checking CUSTOMERS table...")
        customers_columns = [
            ("api_calls", "INTEGER DEFAULT 0")
        ]
        for col_name, col_def in customers_columns:
            add_column(cursor, "customers", col_name, col_def)

        # 3. Fix Calculations Table
        print("\n🔧 Checking CALCULATIONS table...")
        calculations_columns = [
            ("calculation_date", "DATE DEFAULT CURRENT_DATE")
        ]
        for col_name, col_def in calculations_columns:
            add_column(cursor, "calculations", col_name, col_def)
            
        conn.commit()
        print("\n✅ Schema fix completed successfully!")

def add_column(cursor, table, col_name, col_def):
    try:
        if DB_TYPE == 'postgresql':
            # PostgreSQL supports IF NOT EXISTS
            sql = f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_def}"
            cursor.execute(sql)
            print(f"   ✅ Checked/Added column {table}.{col_name}")
            
        else:
            # SQLite manual check
            # Handle sqlite3.Row or dict or tuple
            cursor.execute(f"PRAGMA table_info({table})")
            rows = cursor.fetchall()
            
            # Extract column names safely
            columns = []
            for row in rows:
                if isinstance(row, dict):
                    columns.append(row['name'])
                elif hasattr(row, 'keys'): # sqlite3.Row
                    columns.append(row['name'])
                elif isinstance(row, tuple):
                    columns.append(row[1]) # name is usually index 1 in PRAGMA table_info
                else:
                    # Fallback
                    try:
                        columns.append(row.name)
                    except:
                        pass
            
            if col_name not in columns:
                # SQLite doesn't support IF NOT EXISTS in ADD COLUMN in older versions
                # Also need to map types/defaults for SQLite compatibility if needed
                
                # Simple type mapping
                sqlite_def = col_def
                if "NOW()" in col_def:
                    sqlite_def = col_def.replace("NOW()", "CURRENT_TIMESTAMP")
                if "CURRENT_DATE" in col_def:
                     sqlite_def = col_def.replace("CURRENT_DATE", "DATE('now')")
                
                # SQLite specific fix: remove DEFAULT if it's dynamic and causing issues (like NOW())
                # Actually, CURRENT_TIMESTAMP is allowed. The error "Cannot add a column with non-constant default"
                # usually happens with expression defaults in older SQLite versions or specific constraints.
                # Let's try to be safer for SQLite:
                if "DEFAULT NOW()" in col_def:
                     sqlite_def = col_def.replace("DEFAULT NOW()", "DEFAULT CURRENT_TIMESTAMP")
                
                sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {sqlite_def}"
                cursor.execute(sql)
                print(f"   ✅ Added column {table}.{col_name} (SQLite)")
            else:
                print(f"   ℹ️  Column {table}.{col_name} already exists (SQLite)")
                
    except Exception as e:
        # Ignore "duplicate column" errors if they slip through logic
        if "already exists" in str(e):
            print(f"   ℹ️  Column {table}.{col_name} already exists")
        else:
            print(f"   ❌ Error adding {table}.{col_name}: {e}")

if __name__ == "__main__":
    try:
        fix_schema()
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
