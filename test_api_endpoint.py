import base64
from fastapi.testclient import TestClient
from api.main import app  # Assuming api/main.py has the app instance
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

client = TestClient(app, base_url="http://localhost")

def test_brokers_endpoint():
    username = "admin"
    password = "LienAPI2025"
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}"
    }
    
    print(f"Testing /api/admin/brokers with Basic Auth ({username}:***)...")
    
    try:
        response = client.get("/api/admin/brokers", headers=headers)
        
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            brokers = data.get("brokers", []) if isinstance(data, dict) else data
            print(f"Brokers found: {len(brokers)}")
            for b in brokers:
                print(f" - {b.get('email')} ({b.get('name')})")
                
            target = "polishlofihaven@gmail.com"
            found = any(b.get('email') == target for b in brokers)
            if found:
                print(f"✅ Target broker {target} returned by API.")
            else:
                print(f"❌ Target broker {target} NOT returned by API.")
        else:
            print(f"❌ Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_brokers_endpoint()
