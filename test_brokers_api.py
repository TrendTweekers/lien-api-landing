import base64
import json
from fastapi.testclient import TestClient
from api.main import app
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
            
            target = "polishlofihaven@gmail.com"
            for b in brokers:
                if b.get('email') == target:
                    print(f"\n✅ Target broker found: {b.get('name')}")
                    print("Full object dump:")
                    print(json.dumps(b, indent=4))
                    
                    # Verify fields that might cause frontend crashes
                    print("\nVerifying potential crash fields:")
                    print(f"name type: {type(b.get('name'))}")
                    print(f"email type: {type(b.get('email'))}")
                    print(f"payment_method type: {type(b.get('payment_method'))}")
                    print(f"id type: {type(b.get('id'))}")
        else:
            print(f"❌ Error: {response.text}")
        
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_brokers_endpoint()
