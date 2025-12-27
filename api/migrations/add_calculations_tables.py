import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def run_migration():
    """Create calculations and email_reminders tables"""
    try:
        # Try PostgreSQL first
        DATABASE_URL = os.getenv('DATABASE_URL')
        if DATABASE_URL:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            conn = psycopg2.connect(DATABASE_URL)
            cursor = conn.cursor()
            
            print("Dropping old tables and creating new calculations structure (PostgreSQL)...")
            
            # Drop old tables if they exist (CASCADE removes dependencies)
            cursor.execute("DROP TABLE IF EXISTS email_reminders CASCADE")
            cursor.execute("DROP TABLE IF EXISTS calculations CASCADE")
            print("  Dropped old tables")
            
            # Create calculations table with NEW correct structure
            cursor.execute("""
                CREATE TABLE calculations (
                    id SERIAL PRIMARY KEY,
                    user_email VARCHAR(255) NOT NULL,
                    project_name VARCHAR(255) NOT NULL,
                    client_name VARCHAR(255) NOT NULL,
                    invoice_amount DECIMAL(12,2),
                    notes TEXT,
                    state VARCHAR(100) NOT NULL,
                    state_code VARCHAR(2) NOT NULL,
                    invoice_date DATE NOT NULL,
                    prelim_deadline DATE,
                    prelim_deadline_days INTEGER,
                    lien_deadline DATE NOT NULL,
                    lien_deadline_days INTEGER NOT NULL,
                    quickbooks_invoice_id VARCHAR(255),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP
                )
            """)
            print("  Created calculations table")
            
            # Create email_reminders table
            cursor.execute("""
                CREATE TABLE email_reminders (
                    id SERIAL PRIMARY KEY,
                    calculation_id INTEGER NOT NULL,
                    user_email VARCHAR(255) NOT NULL,
                    project_name VARCHAR(255) NOT NULL,
                    client_name VARCHAR(255) NOT NULL,
                    invoice_amount DECIMAL(12,2),
                    state VARCHAR(100) NOT NULL,
                    notes TEXT,
                    deadline_type VARCHAR(20) NOT NULL,
                    deadline_date DATE NOT NULL,
                    days_before INTEGER NOT NULL,
                    send_date DATE NOT NULL,
                    alert_sent BOOLEAN DEFAULT FALSE,
                    sent_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            print("  Created email_reminders table")
            
            # Create indexes separately to avoid multi-statement errors
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calculations_user_email ON calculations(user_email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_calculations_created_at ON calculations(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminders_send_date ON email_reminders(send_date, alert_sent)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user_email ON email_reminders(user_email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_reminders_calculation_id ON email_reminders(calculation_id)")
            print("  Created indexes")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("✅ Calculations tables created successfully with correct structure")
            return True
            
    except Exception as e:
        print(f"⚠️ PostgreSQL migration failed: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - allow server to continue starting
        # Try SQLite as fallback
        try:
            import sqlite3
            from api.database import BASE_DIR
            
            db_path = BASE_DIR / "lien_deadline.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            print("Creating calculations and email_reminders tables (SQLite)...")
            
            # Create calculations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_email TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    invoice_amount REAL,
                    notes TEXT,
                    state TEXT NOT NULL,
                    state_code TEXT NOT NULL,
                    invoice_date TEXT NOT NULL,
                    prelim_deadline TEXT,
                    prelim_deadline_days INTEGER,
                    lien_deadline TEXT NOT NULL,
                    lien_deadline_days INTEGER NOT NULL,
                    quickbooks_invoice_id TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
            """)
            
            # Create email_reminders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS email_reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    calculation_id INTEGER NOT NULL,
                    user_email TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    invoice_amount REAL,
                    state TEXT NOT NULL,
                    notes TEXT,
                    deadline_type TEXT NOT NULL,
                    deadline_date TEXT NOT NULL,
                    days_before INTEGER NOT NULL,
                    send_date TEXT NOT NULL,
                    alert_sent INTEGER DEFAULT 0,
                    sent_at TIMESTAMP,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    -- REMOVED: FOREIGN KEY constraint to avoid dependency issues
                );
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_calculations_user_email ON calculations(user_email);
                CREATE INDEX IF NOT EXISTS idx_calculations_created_at ON calculations(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_reminders_send_date ON email_reminders(send_date, alert_sent);
                CREATE INDEX IF NOT EXISTS idx_reminders_user_email ON email_reminders(user_email);
            """)
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print("✅ Migration completed successfully (SQLite)")
            return True
            
        except Exception as e2:
            print(f"❌ SQLite migration also failed: {e2}")
            import traceback
            traceback.print_exc()
            return False
    
    return False

if __name__ == "__main__":
    run_migration()

