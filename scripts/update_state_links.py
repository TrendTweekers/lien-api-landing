import os
import re

# Configuration
PUBLIC_DIR = os.path.join("public", "state-lien-guides")
HTML_FILE = os.path.join("public", "state-lien-guides.html")

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

def format_state_name(dirname):
    """Convert directory name to Display Name (e.g., 'new-york' -> 'New York')."""
    return dirname.replace('-', ' ').title()

def generate_html_grid(states):
    """Generate the HTML grid items for the states."""
    html_parts = []
    
    for state_slug in states:
        state_name = format_state_name(state_slug)
        
        # Custom descriptions based on state (optional, can be expanded)
        description = f"{state_name} material supplier lien deadlines"
        
        # Specific overrides for known high-risk states (copied from existing HTML)
        if state_slug == 'arizona':
            description = "20-day notice required • High supplier risk"
        elif state_slug == 'california':
            description = "Preliminary notice required • High risk for suppliers"
        elif state_slug == 'florida':
            description = "45-day notice deadline • High risk for suppliers"
        elif state_slug == 'georgia':
            description = "30-day notice required • High supplier risk"
        elif state_slug == 'texas':
            description = "15th day of the 3rd month rule • Complex"
            
        item_html = f'''            <a href="/state-lien-guides/{state_slug}" style="text-decoration: none; color: inherit; display: block; padding: 20px; border: 1px solid #E5E7EB; border-radius: 8px; background: white; transition: all 0.2s ease;" onmouseover="this.style.borderColor='#F97316'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'" onmouseout="this.style.borderColor='#E5E7EB'; this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                <h4 style="color: #F97316; margin-bottom: 6px; font-size: 18px; font-weight: 600;">{state_name}</h4>
                <p style="font-size: 14px; color: #6B7280;">{description}</p>
            </a>'''
        html_parts.append(item_html)
        
    return "\n\n".join(html_parts)

def update_html_file():
    """Update the HTML file with the new grid."""
    if not os.path.exists(HTML_FILE):
        print(f"HTML file not found: {HTML_FILE}")
        return

    with open(HTML_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    states = get_state_dirs()
    print(f"Found {len(states)} state directories.")
    
    new_grid_content = generate_html_grid(states)
    
    # Regex to find the grid container
    # Looking for the div inside <section id="states">
    # The container has specific style: display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    
    pattern = r'(<div style="display: grid; grid-template-columns: repeat\(auto-fit, minmax\(250px, 1fr\)\); gap: 16px; margin: 24px 0;">)(.*?)(</div>\s*</section>)'
    
    # We need to be careful with the greedy match of .*? and the closing tags.
    # Let's try to match the opening tag and then find the matching closing tag is hard with regex.
    # Instead, let's identify the start string and the end of the section.
    
    start_marker = '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin: 24px 0;">'
    
    if start_marker not in content:
        print("Could not find grid container start marker.")
        return

    start_idx = content.find(start_marker) + len(start_marker)
    
    # Find the closing </div> for this grid. 
    # Since we know the structure, it's the </div> before </section> inside the #states section.
    # But checking indentation/structure might be safer.
    # Let's assume the grid div closes just before </section> since that's what the Read output suggested (nested divs).
    # Wait, looking at the file content:
    # <section id="states" ...>
    #    <div style="max-width: 1200px...">
    #        <h2>...</h2>
    #        <div style="display: grid... ">  <-- Grid Start
    #           ... items ...
    #        </div> <-- Grid End
    #    </div>
    # </section>
    
    # So we need to find the matching </div>. 
    # Let's look for the next occurrence of `</div>` followed by `</div>` followed by `</section>` roughly.
    
    # A safer approach involves splitting the file.
    pre_grid = content[:start_idx]
    remainder = content[start_idx:]
    
    # The grid ends at the first </div> that appears at the right nesting level. 
    # However, since the items themselves don't contain divs (they are <a> tags), 
    # we can likely just look for the first `</div>` after the start marker.
    # BUT, let's check if the items contain divs.
    # The generated items are <a> tags with <h4> and <p>. No divs inside.
    # So finding the next `</div>` should be safe.
    
    end_idx = remainder.find('</div>')
    if end_idx == -1:
        print("Could not find grid container end marker.")
        return
        
    post_grid = remainder[end_idx:]
    
    new_content = pre_grid + "\n\n" + new_grid_content + "\n\n            " + post_grid
    
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Successfully updated state-lien-guides.html")

if __name__ == "__main__":
    update_html_file()
