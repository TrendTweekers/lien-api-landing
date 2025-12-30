import os
import sys
import json
from api.database import get_db, get_db_cursor, DB_TYPE

def check_broker(email):
    print(f"Checking for broker: {email}")
    try:
        with get_db() as conn:
            cursor = get_db_cursor(conn)
            
            if DB_TYPE == 'postgresql':
                query = "SELECT * FROM brokers WHERE email = %s"
                cursor.execute(query, (email,))
            else:
                query = "SELECT * FROM brokers WHERE email = ?"
                cursor.execute(query, (email,))
            
            broker = cursor.fetchone()
            
            if broker:
                print("\n✅ Broker FOUND in database:")
                # Handle both dict (RealDictCursor) and tuple results
                if isinstance(broker, dict):
                    for key, value in broker.items():
                        print(f"  {key}: {value}")
                else:
                    # If it's a tuple, we might not have column names easily, but let's print it
                    print(f"  Data: {broker}")
                    
                    # Try to get column names if possible
                    if hasattr(cursor, 'description') and cursor.description:
                        col_names = [desc[0] for desc in cursor.description]
                        print("\n  Column mapping:")
                        for i, col in enumerate(col_names):
                            val = broker[i] if i < len(broker) else "N/A"
                            print(f"  {col}: {val}")
            else:
                print("\n❌ Broker NOT FOUND in database.")
                
    except Exception as e:
        print(f"\n❌ Error querying database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    email = "polishlofihaven@gmail.com"
    check_broker(email)
