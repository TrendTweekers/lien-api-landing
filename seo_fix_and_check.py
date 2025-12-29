import os
import re
from pathlib import Path
from datetime import datetime

# Configuration
ROOT_DIR = os.getcwd()
PUBLIC_DIR = os.path.join(ROOT_DIR, 'public')
SITEMAP_PATH = os.path.join(PUBLIC_DIR, 'sitemap.xml')
INDEX_PATH = os.path.join(ROOT_DIR, 'index.html')
PRICING_PATH = os.path.join(PUBLIC_DIR, 'pricing.html')
STATE_GUIDES_DIR = os.path.join(PUBLIC_DIR, 'state-lien-guides')

# File size limits
JS_LIMIT = 200 * 1024 # 200KB
IMG_LIMIT = 500 * 1024 # 500KB
CSS_LIMIT = 100 * 1024 # 100KB

def check_structured_data(file_path):
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return '<script type="application/ld+json">' in content
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

def get_state_urls():
    urls = []
    if not os.path.exists(STATE_GUIDES_DIR):
        return urls
    
    for item in os.listdir(STATE_GUIDES_DIR):
        state_dir = os.path.join(STATE_GUIDES_DIR, item)
        if os.path.isdir(state_dir):
            urls.append(f"https://liendeadline.com/state-lien-guides/{item}")
    return sorted(urls)

def check_file_sizes():
    large_files = []
    for root, dirs, files in os.walk(PUBLIC_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            size = os.path.getsize(file_path)
            ext = os.path.splitext(file)[1].lower()
            
            if ext == '.js' and size > JS_LIMIT:
                large_files.append((file_path, size, 'JS'))
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'] and size > IMG_LIMIT:
                large_files.append((file_path, size, 'Image'))
            elif ext == '.css' and size > CSS_LIMIT:
                large_files.append((file_path, size, 'CSS'))
    return large_files

def update_sitemap():
    if not os.path.exists(SITEMAP_PATH):
        print(f"Sitemap not found at {SITEMAP_PATH}")
        return

    with open(SITEMAP_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # URLs to ensure exist
    required_urls = [
        "https://liendeadline.com/",
        "https://liendeadline.com/pricing.html",
        "https://liendeadline.com/partners.html",
        "https://liendeadline.com/state-lien-guides.html",
        "https://liendeadline.com/login.html"
    ]
    
    # Add state URLs
    state_urls = get_state_urls()
    required_urls.extend(state_urls)
    
    missing_urls = []
    for url in required_urls:
        if url not in content:
            missing_urls.append(url)
    
    if missing_urls:
        print(f"Adding {len(missing_urls)} missing URLs to sitemap...")
        
        # Prepare new entries
        new_entries = ""
        today = datetime.now().strftime("%Y-%m-%d")
        
        for url in missing_urls:
            priority = "0.8"
            if url == "https://liendeadline.com/": priority = "1.0"
            elif "pricing" in url: priority = "0.9"
            
            entry = f"""
    <url>
        <loc>{url}</loc>
        <lastmod>{today}</lastmod>
        <changefreq>monthly</changefreq>
        <priority>{priority}</priority>
    </url>"""
            new_entries += entry
            
        # Insert before </urlset>
        if "</urlset>" in content:
            new_content = content.replace("</urlset>", new_entries + "\n</urlset>")
            with open(SITEMAP_PATH, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("Sitemap updated successfully.")
        else:
            print("Error: Could not find </urlset> tag in sitemap.")
    else:
        print("Sitemap is already up to date.")

def main():
    print("--- SEO Fix and Check ---")
    
    # 1. Check Structured Data
    print("\n1. Checking Structured Data...")
    has_sd_index = check_structured_data(INDEX_PATH)
    has_sd_pricing = check_structured_data(PRICING_PATH)
    
    if not has_sd_index:
        print(f"MISSING: Structured Data in {INDEX_PATH}")
    else:
        print(f"PASS: Structured Data found in {INDEX_PATH}")
        
    if not has_sd_pricing:
        print(f"MISSING: Structured Data in {PRICING_PATH}")
    else:
        print(f"PASS: Structured Data found in {PRICING_PATH}")

    # 2. Update Sitemap
    print("\n2. Checking and Updating Sitemap...")
    update_sitemap()
    
    # 3. Check File Sizes
    print("\n3. Checking File Sizes...")
    large_files = check_file_sizes()
    if large_files:
        print("Large files found:")
        for path, size, type_ in large_files:
            rel_path = os.path.relpath(path, ROOT_DIR)
            print(f"- {rel_path}: {size/1024:.2f} KB ({type_})")
    else:
        print("No large files found.")

if __name__ == "__main__":
    main()
