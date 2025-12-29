import os
import re

def fix_webhook():
    file_path = 'api/main.py'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    in_webhook = False
    webhook_indent = ""
    
    # Track if we are inside the webhook function and after "db = get_db()"
    inside_db_context = False
    
    for i, line in enumerate(lines):
        # Detect start of webhook function
        if line.strip().startswith("async def stripe_webhook(request: Request):"):
            in_webhook = True
            new_lines.append(line)
            continue
            
        if in_webhook:
            # Check if we've exited the function (based on indentation)
            # Assuming function body is indented by at least 4 spaces
            if line.strip() and not line.startswith("    "):
                in_webhook = False
                inside_db_context = False
                new_lines.append(line)
                continue
            
            # Find and replace "db = get_db()"
            if "db = get_db()" in line:
                indent = line[:line.find("db = get_db()")]
                new_lines.append(f"{indent}with get_db() as db:\n")
                inside_db_context = True
                continue
                
            if inside_db_context:
                # Indent line by 4 spaces
                if line.strip():
                    line = "    " + line
                
                # Replace db.execute( with execute_query(db, 
                line = line.replace("db.execute(", "execute_query(db, ")
                
                # Replace cursor = db.cursor() with nothing (or pass)
                # We can just comment it out as execute_query creates cursors
                if "cursor = db.cursor()" in line:
                    line = line.replace("cursor = db.cursor()", "# cursor = db.cursor() - handled by execute_query")
                
                # Replace cursor.execute( with cursor = execute_query(db, 
                line = line.replace("cursor.execute(", "cursor = execute_query(db, ")
                
                # Replace sqlite3.IntegrityError with IntegrityError
                line = line.replace("sqlite3.IntegrityError", "IntegrityError")
                
                new_lines.append(line)
            else:
                # Before db = get_db(), keep as is (but apply other fixes if needed)
                # Though usually no db calls before get_db
                new_lines.append(line)
                
        else:
            new_lines.append(line)
            
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
        
    print(f"Fixed {file_path}")

if __name__ == "__main__":
    fix_webhook()
