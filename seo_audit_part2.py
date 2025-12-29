import os
import re

# Directory to scan for images
PUBLIC_DIR = "public"

# Files to check for OG tags, canonical URLs
FILES_TO_CHECK = [
    "index.html", # This is in root
    "public/pricing.html",
    "public/login.html",
    "partners.html", # This is in root
    "public/state-lien-guides.html"
]

# Required OG Properties
REQUIRED_OG = [
    "og:title",
    "og:description",
    "og:image",
    "og:url"
]

def check_file_existence(file_path):
    return os.path.exists(file_path)

def audit_images():
    print("\n--- 1. Checking Image Alt Text ---")
    
    # We will walk through public directory
    image_issues = []
    
    for root, dirs, files in os.walk(PUBLIC_DIR):
        for file in files:
            if file.endswith(".html"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Find all img tags
                    # Pattern captures the whole tag
                    img_tags = re.findall(r'<img[^>]*>', content, re.IGNORECASE)
                    
                    for img_tag in img_tags:
                        # Extract src for identification
                        src_match = re.search(r'src=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
                        src = src_match.group(1) if src_match else "unknown"
                        
                        # Extract alt
                        alt_match = re.search(r'alt=["\']([^"\']*)["\']', img_tag, re.IGNORECASE)
                        
                        issue = None
                        alt_text = None
                        
                        if not alt_match:
                            issue = "Missing alt attribute"
                        else:
                            alt_text = alt_match.group(1)
                            if not alt_text:
                                issue = "Empty alt text"
                            elif alt_text.lower() in ["image", "logo", "icon"]:
                                issue = f"Generic alt text: '{alt_text}'"
                        
                        if issue:
                            image_issues.append({
                                "file": file_path,
                                "src": src,
                                "issue": issue,
                                "current_alt": alt_text
                            })
                            
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    if not image_issues:
        print("PASS: No image alt text issues found.")
    else:
        print(f"FAIL: Found {len(image_issues)} image issues:")
        for issue in image_issues:
            print(f"  - File: {issue['file']}")
            print(f"    Image: {issue['src']}")
            print(f"    Issue: {issue['issue']}")
            print("-" * 30)

def audit_og_tags(file_path):
    if not check_file_existence(file_path):
        print(f"ERROR: File {file_path} does not exist!")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Could not read file: {e}")
        return

    missing_og = []
    for prop in REQUIRED_OG:
        # Check for <meta property="og:..." ...> or <meta ... property="og:...">
        pattern = f'<meta[^>]*property=["\']{prop}["\'][^>]*>'
        if not re.search(pattern, content, re.IGNORECASE):
            missing_og.append(prop)
            
    if missing_og:
        print(f"FAIL: {file_path} is MISSING OG tags: {', '.join(missing_og)}")
    else:
        print(f"PASS: {file_path} has all required OG tags")

def audit_canonical(file_path):
    if not check_file_existence(file_path):
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return

    pattern = r'<link[^>]*rel=["\']canonical["\'][^>]*>'
    if re.search(pattern, content, re.IGNORECASE):
        print(f"PASS: {file_path} has canonical tag")
    else:
        print(f"FAIL: {file_path} is MISSING canonical tag")

def audit_internal_linking():
    print("\n--- 4. Checking Internal Linking (Homepage) ---")
    file_path = "index.html"
    
    if not check_file_existence(file_path):
        print(f"ERROR: {file_path} does not exist!")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Could not read file: {e}")
        return

    # Check for links
    checks = {
        "Pricing": r'href=["\']/?pricing\.html["\']',
        "Partners": r'href=["\']/?partners\.html["\']',
        "Login": r'href=["\']/?login\.html["\']',
        "State Guides": r'href=["\']/?state-lien-guides\.html["\']',
        "Calculator": r'href=["\']/?#calculator["\']|id=["\']calculator["\']' # Link to it or the section itself
    }
    
    for name, pattern in checks.items():
        if re.search(pattern, content, re.IGNORECASE):
            print(f"PASS: Homepage links to {name}")
        else:
            print(f"FAIL: Homepage MISSING link to {name}")

if __name__ == "__main__":
    audit_images()
    
    print("\n--- 2. Checking Open Graph Tags ---")
    # Only check specific files requested for OG
    og_files = ["index.html", "public/pricing.html", "public/login.html"]
    for file in og_files:
        audit_og_tags(file)
        
    print("\n--- 3. Checking Canonical URLs ---")
    for file in FILES_TO_CHECK:
        audit_canonical(file)
        
    audit_internal_linking()
