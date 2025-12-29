import os
import xml.etree.ElementTree as ET
from datetime import datetime

# Configuration
PUBLIC_DIR = os.path.join("public", "state-lien-guides")
SITEMAP_FILE = os.path.join("public", "sitemap.xml")
BASE_URL = "https://liendeadline.com/state-lien-guides/"

def get_state_dirs():
    """Get all state directories in the public/state-lien-guides folder."""
    if not os.path.exists(PUBLIC_DIR):
        print(f"Directory not found: {PUBLIC_DIR}")
        return []
    
    dirs = []
    for d in os.listdir(PUBLIC_DIR):
        path = os.path.join(PUBLIC_DIR, d)
        if os.path.isdir(path) and not d.startswith('.'):
            dirs.append(d)
    return sorted(dirs)

def check_sitemap():
    """Check sitemap for missing state URLs."""
    if not os.path.exists(SITEMAP_FILE):
        print(f"Sitemap not found: {SITEMAP_FILE}")
        return

    tree = ET.parse(SITEMAP_FILE)
    root = tree.getroot()
    
    # Namespace handling
    ns = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    
    existing_urls = set()
    for url in root.findall('sitemap:url', ns):
        loc = url.find('sitemap:loc', ns).text
        existing_urls.add(loc)
        
    state_dirs = get_state_dirs()
    print(f"Checking {len(state_dirs)} state directories against sitemap...")
    missing_states = []
    
    for state in state_dirs:
        expected_url = f"{BASE_URL}{state}"
        if expected_url not in existing_urls:
            missing_states.append(state)
            
    if missing_states:
        print(f"Found {len(missing_states)} missing states in sitemap:")
        for state in missing_states:
            print(f" - {state}")
            
        # Add missing states
        print("Adding missing states to sitemap...")
        today = datetime.now().strftime("%Y-%m-%d")
        
        for state in missing_states:
            url_elem = ET.SubElement(root, "url")
            
            loc_elem = ET.SubElement(url_elem, "loc")
            loc_elem.text = f"{BASE_URL}{state}"
            
            lastmod_elem = ET.SubElement(url_elem, "lastmod")
            lastmod_elem.text = today
            
            changefreq_elem = ET.SubElement(url_elem, "changefreq")
            changefreq_elem.text = "monthly"
            
            priority_elem = ET.SubElement(url_elem, "priority")
            priority_elem.text = "0.8"
            
        # Write back to file (register namespace to avoid ns0: prefixes)
        ET.register_namespace('', "http://www.sitemaps.org/schemas/sitemap/0.9")
        tree.write(SITEMAP_FILE, encoding='UTF-8', xml_declaration=True)
        print("Sitemap updated successfully.")
        
    else:
        print("All states are present in the sitemap.")

if __name__ == "__main__":
    check_sitemap()
