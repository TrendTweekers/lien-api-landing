import os
import re

# Define the files to check
FILES_TO_CHECK = [
    "index.html",
    "public/pricing.html",
    "partners.html",
    "public/state-lien-guides.html",
    "public/login.html"
]

def check_file_existence(file_path):
    return os.path.exists(file_path)

def get_tag_content(content, tag_name):
    # Simple regex to find content within a tag
    pattern = f"<{tag_name}[^>]*>(.*?)</{tag_name}>"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else None

def get_meta_content(content, meta_name):
    # Simple regex to find meta tag content
    pattern = f'<meta[^>]*name=["\']{meta_name}["\'][^>]*content=["\']([^"\']*)["\'][^>]*>'
    match = re.search(pattern, content, re.IGNORECASE)
    if not match:
        # Try alternate order (content first)
        pattern = f'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']{meta_name}["\'][^>]*>'
        match = re.search(pattern, content, re.IGNORECASE)
    return match.group(1) if match else None

def check_h1_tags(content):
    # Find all h1 tags
    h1_matches = re.findall(r"<h1[^>]*>(.*?)</h1>", content, re.IGNORECASE | re.DOTALL)
    return len(h1_matches)

def audit_file(file_path):
    print(f"\n--- Checking {file_path} ---")
    
    if not check_file_existence(file_path):
        print(f"ERROR: File {file_path} does not exist!")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"ERROR: Could not read file: {e}")
        return

    # 1. Meta Tags
    title = get_tag_content(content, "title")
    description = get_meta_content(content, "description")
    viewport = get_meta_content(content, "viewport")

    if title:
        print(f"PASS: <title> found ({len(title)} chars): {title}")
        if len(title) < 50 or len(title) > 60:
            print(f"WARNING: <title> length is {len(title)} chars (recommended: 50-60)")
    else:
        print("FAIL: <title> tag MISSING")

    if description:
        print(f"PASS: Meta description found ({len(description)} chars)")
        if len(description) < 155 or len(description) > 160:
            print(f"WARNING: Meta description length is {len(description)} chars (recommended: 155-160)")
    else:
        print("FAIL: Meta description MISSING")

    if viewport:
        print("PASS: Meta viewport found")
    else:
        print("FAIL: Meta viewport MISSING")

    # 2. Heading Structure
    h1_count = check_h1_tags(content)
    if h1_count == 1:
        print("PASS: Exactly one <h1> tag found")
    elif h1_count == 0:
        print("FAIL: No <h1> tag found")
    else:
        print(f"FAIL: Multiple ({h1_count}) <h1> tags found")

    # 3. Special Check for state-lien-guides.html
    if "state-lien-guides.html" in file_path:
        check_state_links(content)

def check_state_links(content):
    print("\n--- Verifying State Guides Links ---")
    # Find all links to state guides
    links = re.findall(r'href="/state-lien-guides/([^"]+)"', content)
    
    # Filter out non-state links if any (though regex is specific to state-lien-guides path)
    # The user asked to count "total state links"
    
    unique_links = []
    seen = set()
    for link in links:
        if link not in seen:
            unique_links.append(link)
            seen.add(link)
            
    # Assuming the grid links are the ones we care about and they appear in order
    # Let's try to extract them from the grid section specifically if possible, 
    # but the previous script just updated the grid.
    # The regex finds all occurrences. The grid usually has one link per state.
    
    print(f"Total state links found: {len(unique_links)}")
    
    if len(unique_links) != 51:
         print(f"FAIL: Expected 51 state links, found {len(unique_links)}")
    else:
         print("PASS: Count is 51")

    if unique_links:
        print(f"First link: {unique_links[0]}")
        if unique_links[0] == "alabama":
             print("PASS: First link is Alabama")
        else:
             print(f"FAIL: First link is {unique_links[0]}, expected alabama")

        print(f"Last link: {unique_links[-1]}")
        if unique_links[-1] == "wyoming":
             print("PASS: Last link is Wyoming")
        else:
             print(f"FAIL: Last link is {unique_links[-1]}, expected wyoming")
        
        if "district-of-columbia" in unique_links:
             print("PASS: DC is included")
        else:
             print("FAIL: DC is NOT included")

def check_robots_sitemap():
    print("\n--- Checking robots.txt and sitemap.xml ---")
    robots_path = "public/robots.txt"
    sitemap_path = "public/sitemap.xml"
    
    if os.path.exists(robots_path):
        print(f"PASS: {robots_path} exists")
    else:
        print(f"FAIL: {robots_path} MISSING")
        
    if os.path.exists(sitemap_path):
        print(f"PASS: {sitemap_path} exists")
    else:
        print(f"FAIL: {sitemap_path} MISSING")

if __name__ == "__main__":
    for file in FILES_TO_CHECK:
        audit_file(file)
    
    check_robots_sitemap()
