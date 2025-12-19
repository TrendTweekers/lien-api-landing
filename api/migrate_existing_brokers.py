"""
Migration script to generate short codes for existing brokers
Run this once after deploying the short link system
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.database import get_db, get_db_cursor, DB_TYPE
from api.short_link_system import ShortLinkGenerator

def migrate_existing_brokers():
    """Generate short codes for all brokers that don't have one"""
    print("=" * 80)
    print("🔄 MIGRATING EXISTING BROKERS TO SHORT CODES")
    print("=" * 80)
    
    updated_count = 0
    error_count = 0
    
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            # Ensure short_code column exists
            if DB_TYPE == 'postgresql':
                try:
                    cursor.execute("""
                        ALTER TABLE brokers ADD COLUMN IF NOT EXISTS short_code VARCHAR(10) UNIQUE
                    """)
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brokers_short_code ON brokers(short_code)")
                    conn.commit()
                    print("✅ Added short_code column and index")
                except Exception as e:
                    print(f"⚠️ Column might already exist: {e}")
            else:
                try:
                    cursor.execute("ALTER TABLE brokers ADD COLUMN short_code TEXT UNIQUE")
                    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brokers_short_code ON brokers(short_code)")
                    conn.commit()
                    print("✅ Added short_code column and index")
                except Exception:
                    print("⚠️ Column might already exist")
            
            # Get all brokers without short_code
            if DB_TYPE == 'postgresql':
                cursor.execute("""
                    SELECT id, email, name, referral_code 
                    FROM brokers 
                    WHERE short_code IS NULL OR short_code = ''
                """)
            else:
                cursor.execute("""
                    SELECT id, email, name, referral_code 
                    FROM brokers 
                    WHERE short_code IS NULL OR short_code = ''
                """)
            
            brokers = cursor.fetchall()
            print(f"\n📊 Found {len(brokers)} brokers without short codes\n")
            
            if len(brokers) == 0:
                print("✅ All brokers already have short codes!")
                return
            
            # Generate short codes for each broker
            for broker in brokers:
                try:
                    # Handle different row formats
                    if isinstance(broker, dict):
                        broker_id = broker.get('id')
                        broker_email = broker.get('email', '')
                        broker_name = broker.get('name', '')
                        referral_code = broker.get('referral_code', '')
                    else:
                        broker_id = broker[0]
                        broker_email = broker[1] if len(broker) > 1 else ''
                        broker_name = broker[2] if len(broker) > 2 else ''
                        referral_code = broker[3] if len(broker) > 3 else ''
                    
                    if not broker_email:
                        print(f"⚠️ Skipping broker {broker_id}: no email")
                        error_count += 1
                        continue
                    
                    # Generate short code
                    short_code = ShortLinkGenerator.generate_short_code(broker_email, length=4)
                    
                    # Check for collision
                    max_attempts = 10
                    attempt = 0
                    while attempt < max_attempts:
                        if DB_TYPE == 'postgresql':
                            cursor.execute("SELECT short_code FROM brokers WHERE short_code = %s", (short_code,))
                        else:
                            cursor.execute("SELECT short_code FROM brokers WHERE short_code = ?", (short_code,))
                        
                        if cursor.fetchone():
                            # Collision - generate random code
                            short_code = ShortLinkGenerator.generate_random_code(length=6)
                            attempt += 1
                        else:
                            break
                    
                    if attempt >= max_attempts:
                        print(f"❌ Failed to generate unique code for {broker_email} after {max_attempts} attempts")
                        error_count += 1
                        continue
                    
                    # Update referral_link to use short format
                    referral_link = f"https://liendeadline.com/r/{short_code}"
                    
                    # Update broker record
                    if DB_TYPE == 'postgresql':
                        cursor.execute("""
                            UPDATE brokers 
                            SET short_code = %s, 
                                referral_link = %s
                            WHERE id = %s
                        """, (short_code, referral_link, broker_id))
                    else:
                        cursor.execute("""
                            UPDATE brokers 
                            SET short_code = ?, 
                                referral_link = ?
                            WHERE id = ?
                        """, (short_code, referral_link, broker_id))
                    
                    conn.commit()
                    updated_count += 1
                    
                    print(f"✅ {broker_name} ({broker_email})")
                    print(f"   Short Code: {short_code}")
                    print(f"   Link: {referral_link}")
                    print()
                    
                except Exception as e:
                    print(f"❌ Error updating broker {broker_id}: {e}")
                    error_count += 1
                    import traceback
                    traceback.print_exc()
                    continue
            
            print("=" * 80)
            print(f"✅ Migration complete!")
            print(f"   Updated: {updated_count} brokers")
            print(f"   Errors: {error_count} brokers")
            print("=" * 80)
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    migrate_existing_brokers()

