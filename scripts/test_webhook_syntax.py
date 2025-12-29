import re

def check_webhook_syntax():
    with open('api/main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract stripe_webhook function
    match = re.search(r'async def stripe_webhook\(.*?\):(.*?)(?=\nasync def|\Z)', content, re.DOTALL)
    if not match:
        print("Could not find stripe_webhook function")
        return
    
    webhook_body = match.group(1)
    
    # Check for db.execute
    if 'db.execute(' in webhook_body:
        print("FAIL: Found db.execute() in stripe_webhook")
        # Print context
        lines = webhook_body.splitlines()
        for i, line in enumerate(lines):
            if 'db.execute(' in line:
                print(f"Line {i}: {line.strip()}")
    else:
        print("PASS: No db.execute() found in stripe_webhook")
        
    # Check for sqlite3.IntegrityError
    if 'sqlite3.IntegrityError' in webhook_body:
        print("FAIL: Found sqlite3.IntegrityError in stripe_webhook")
    else:
        print("PASS: No sqlite3.IntegrityError found in stripe_webhook")
        
    # Check for with get_db() as db
    if 'with get_db() as db:' in webhook_body:
        print("PASS: Found 'with get_db() as db:' in stripe_webhook")
    else:
        print("FAIL: 'with get_db() as db:' NOT found in stripe_webhook")

if __name__ == "__main__":
    check_webhook_syntax()
