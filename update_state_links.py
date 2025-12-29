import os
import re

# List of all 50 states and District of Columbia
STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
    "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
    "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina",
    "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming"
]

def format_slug(name):
    """Convert state name to slug format (lowercase, hyphens)."""
    return name.lower().replace(" ", "-")

def get_subtitle(state_name):
    """Get the subtitle for a state.
    Uses specific subtitles for states with known high risks or specific requirements,
    defaults to generic text for others.
    """
    # Map of specific subtitles based on existing file content to maintain consistency
    subtitles = {
        "Alabama": "Alabama material supplier lien deadlines",
        "Alaska": "Alaska lien deadlines for suppliers",
        "Arizona": "20-day notice required • High supplier risk",
        "Arkansas": "Arkansas supplier lien rights",
        "California": "Preliminary notice required • High risk for suppliers",
        "Colorado": "Colorado supplier lien deadlines",
        "Connecticut": "Connecticut supplier lien rights",
        "Delaware": "Delaware material supplier deadlines",
        "Florida": "45-day notice deadline • High risk for suppliers",
        "Georgia": "30-day notice required • High supplier risk",
        "Hawaii": "Hawaii supplier lien deadlines",
        "Idaho": "Idaho material supplier deadlines",
        "Illinois": "Illinois supplier lien deadlines",
        "Indiana": "Indiana building material supplier deadlines",
        "Iowa": "Iowa material supplier deadlines",
        "Kansas": "Kansas supplier lien deadlines",
        "Kentucky": "Kentucky building material supplier deadlines",
        "Louisiana": "Louisiana supplier lien rights & timing",
        "Maine": "Maine material supplier deadlines",
        "Maryland": "Maryland building material supplier deadlines",
        "Massachusetts": "Massachusetts supplier lien deadlines",
        "Michigan": "Michigan supplier lien deadlines",
        "Minnesota": "Minnesota supplier lien deadlines",
        "Mississippi": "Mississippi supplier lien deadlines",
        "Missouri": "Missouri supplier lien deadlines",
        "Montana": "Montana supplier lien deadlines",
        "Nebraska": "Nebraska supplier lien deadlines",
        "Nevada": "Nevada supplier lien deadlines",
        "New Hampshire": "New Hampshire supplier lien deadlines",
        "New Jersey": "New Jersey supplier lien deadlines",
        "New Mexico": "New Mexico supplier lien deadlines",
        "New York": "New York supplier lien deadlines",
        "North Carolina": "North Carolina supplier lien deadlines",
        "North Dakota": "North Dakota supplier lien deadlines",
        "Ohio": "Ohio supplier lien deadlines",
        "Oklahoma": "Oklahoma supplier lien deadlines",
        "Oregon": "Oregon supplier lien deadlines",
        "Pennsylvania": "Pennsylvania supplier lien deadlines",
        "Rhode Island": "Rhode Island supplier lien deadlines",
        "South Carolina": "South Carolina supplier lien deadlines",
        "South Dakota": "South Dakota supplier lien deadlines",
        "Tennessee": "Tennessee supplier lien deadlines",
        "Texas": "15th day notice deadline • High supplier risk",
        "Utah": "Utah supplier lien deadlines",
        "Vermont": "Vermont supplier lien deadlines",
        "Virginia": "Virginia supplier lien deadlines",
        "Washington": "Washington supplier lien deadlines",
        "West Virginia": "West Virginia supplier lien deadlines",
        "Wisconsin": "Wisconsin supplier lien deadlines",
        "Wyoming": "Wyoming supplier lien deadlines",
        "District of Columbia": "DC supplier lien deadlines"
    }
    return subtitles.get(state_name, f"{state_name} supplier lien deadlines")

def generate_state_card(name):
    """Generate HTML for a single state card."""
    slug = format_slug(name)
    subtitle = get_subtitle(name)
    
    return f"""
            <a href="/state-lien-guides/{slug}" style="text-decoration: none; color: inherit; display: block; padding: 20px; border: 1px solid #E5E7EB; border-radius: 8px; background: white; transition: all 0.2s ease;" onmouseover="this.style.borderColor='#F97316'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'" onmouseout="this.style.borderColor='#E5E7EB'; this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                <h4 style="color: #F97316; margin-bottom: 6px; font-size: 18px; font-weight: 600;">{name}</h4>
                <p style="font-size: 14px; color: #6B7280;">{subtitle}</p>
            </a>"""

def update_state_links():
    file_path = os.path.join("public", "state-lien-guides.html")
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Generate all state cards
        # Sort states alphabetically just in case, though the list is already sorted
        sorted_states = sorted(STATES)
        cards_html = "\n".join([generate_state_card(state) for state in sorted_states])

        # Define the regex pattern to find the grid container
        # We look for the specific style attribute of the grid container
        pattern = r'(<div style="display: grid; grid-template-columns: repeat\(auto-fit, minmax\(250px, 1fr\)\); gap: 16px; margin: 24px 0;">)([\s\S]*?)(</div>)'
        
        match = re.search(pattern, content)
        if match:
            # Construct the new content
            # group(1) is the opening tag, group(3) is the closing tag
            new_content = content[:match.start(2)] + "\n" + cards_html + "\n            " + content[match.end(2):]
            
            # Write the updated content back to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            print(f"Successfully updated {file_path} with {len(sorted_states)} state links.")
        else:
            print("Error: Could not find the state grid container in the HTML file.")
            
    except PermissionError:
        print(f"Error: Permission denied when accessing {file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    update_state_links()
