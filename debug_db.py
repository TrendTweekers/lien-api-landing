import sqlite3
import os

db_path = "liendeadline.db"
if not os.path.exists(db_path):
    print(f"Database {db_path} not found!")
else:
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check brokers table
        print("--- Brokers Table Check ---")
        cursor.execute("SELECT * FROM brokers WHERE email='polishlofihaven@gmail.com'")
        rows = cursor.fetchall()
        if not rows:
            print("Broker NOT found in 'brokers' table.")
        else:
            for row in rows:
                print(dict(row))
                
        # Check partner_applications table
        print("\n--- Partner Applications Table Check ---")
        cursor.execute("SELECT * FROM partner_applications WHERE email='polishlofihaven@gmail.com'")
        rows = cursor.fetchall()
        if not rows:
            print("Broker NOT found in 'partner_applications' table.")
        else:
            for row in rows:
                print(dict(row))
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
