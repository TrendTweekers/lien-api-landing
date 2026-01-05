"""
Database migration helpers for plan and usage tracking
"""
from api.database import get_db, get_db_cursor, DB_TYPE
from datetime import date
import logging

logger = logging.getLogger(__name__)

def migrate_add_plan_usage_fields():
    """Add plan and usage tracking fields to users table"""
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                # PostgreSQL: Use DO block from SQL migration
                # But we can also do it programmatically here
                columns_to_add = [
                    ('plan', "VARCHAR(20) DEFAULT 'free' CHECK (plan IN ('free', 'basic', 'automated', 'enterprise'))"),
                    ('usage_month', 'DATE DEFAULT DATE_TRUNC(\'month\', CURRENT_DATE)'),
                    ('manual_calc_count', 'INTEGER DEFAULT 0'),
                    ('api_call_count', 'INTEGER DEFAULT 0'),
                    ('zapier_webhook_count', 'INTEGER DEFAULT 0'),
                ]
                
                for col_name, col_def in columns_to_add:
                    try:
                        cursor.execute(f"""
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_schema = 'public' 
                            AND table_name = 'users' 
                            AND column_name = '{col_name}'
                        """)
                        exists = cursor.fetchone()
                        if not exists:
                            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                            logger.info(f"Added column {col_name} to users table")
                    except Exception as e:
                        logger.warning(f"Could not add column {col_name}: {e}")
                
                # Update existing users
                current_month = date.today().replace(day=1)
                cursor.execute("""
                    UPDATE users 
                    SET usage_month = %s 
                    WHERE usage_month IS NULL
                """, (current_month,))
                
            else:
                # SQLite: Check and add columns
                # SQLite doesn't support IF NOT EXISTS for ALTER TABLE
                # So we check pragma first
                cursor.execute("PRAGMA table_info(users)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                
                columns_to_add = [
                    ('plan', "TEXT DEFAULT 'free'"),
                    ('usage_month', 'TEXT'),
                    ('manual_calc_count', 'INTEGER DEFAULT 0'),
                    ('api_call_count', 'INTEGER DEFAULT 0'),
                    ('zapier_webhook_count', 'INTEGER DEFAULT 0'),
                ]
                
                for col_name, col_def in columns_to_add:
                    if col_name not in existing_columns:
                        try:
                            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                            logger.info(f"Added column {col_name} to users table")
                        except Exception as e:
                            logger.warning(f"Could not add column {col_name}: {e}")
                
                # Update existing users with current month
                current_month = date.today().replace(day=1).isoformat()
                cursor.execute("""
                    UPDATE users 
                    SET usage_month = ? 
                    WHERE usage_month IS NULL OR usage_month = ''
                """, (current_month,))
            
            conn.commit()
            logger.info("✅ Migration completed: Added plan and usage tracking fields")
            return True
            
    except Exception as e:
        logger.error(f"Error in migration: {e}")
        import traceback
        traceback.print_exc()
        return False

