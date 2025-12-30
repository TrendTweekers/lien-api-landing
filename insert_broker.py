import sqlite3
import uuid
import os

db_path = "liendeadline.db"

def insert_broker():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    email = "polishlofihaven@gmail.com"
    broker_id = str(uuid.uuid4())
    name = "Polish Lofi Haven" # Placeholder name
    model = "standard" # Placeholder model
    
    print(f"Inserting broker: {email}")
    
    try:
        cursor.execute("""
            INSERT INTO brokers (id, email, name, model, referrals, earned, stripe_account_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (broker_id, email, name, model, 0, 0.0, None))
        
        conn.commit()
        print("✅ Broker inserted successfully!")
    except Exception as e:
        print(f"❌ Error inserting broker: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    insert_broker()
