import os

states_data = [
    {"name": "Oklahoma", "slug": "oklahoma"},
    {"name": "Oregon", "slug": "oregon"},
    {"name": "Rhode Island", "slug": "rhode-island"},
    {"name": "South Carolina", "slug": "south-carolina"},
    {"name": "South Dakota", "slug": "south-dakota"},
    {"name": "Tennessee", "slug": "tennessee"},
    {"name": "Utah", "slug": "utah"},
    {"name": "Vermont", "slug": "vermont"},
    {"name": "Virginia", "slug": "virginia"},
    {"name": "Washington", "slug": "washington"},
    {"name": "West Virginia", "slug": "west-virginia"},
    {"name": "Wisconsin", "slug": "wisconsin"},
    {"name": "Wyoming", "slug": "wyoming"},
    {"name": "North Dakota", "slug": "north-dakota"}
]

def update_sitemap():
    try:
        with open("public/sitemap.xml", "r", encoding="utf-8") as f:
            content = f.read()
        
        new_entries = ""
        for state in states_data:
            if f"/state-lien-guides/{state['slug']}" not in content:
                new_entries += f"""
    <url>
        <loc>https://liendeadline.com/state-lien-guides/{state['slug']}</loc>
        <lastmod>2025-12-29</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.8</priority>
    </url>"""
                print(f"Adding {state['slug']} to sitemap")
        
        if new_entries:
            insert_pos = content.rfind("</urlset>")
            if insert_pos != -1:
                new_content = content[:insert_pos] + new_entries + "\n" + content[insert_pos:]
                with open("public/sitemap.xml", "w", encoding="utf-8") as f:
                    f.write(new_content)
                print("Sitemap updated.")
            else:
                print("Error: </urlset> not found")
        else:
            print("Sitemap already up to date.")
    except Exception as e:
        print(f"Error updating sitemap: {e}")

def update_hub():
    try:
        with open("public/state-lien-guides.html", "r", encoding="utf-8") as f:
            content = f.read()
        
        new_cards = ""
        for state in states_data:
            if f"/state-lien-guides/{state['slug']}" not in content:
                new_cards += f"""
                    <a href="/state-lien-guides/{state['slug']}" style="text-decoration: none; color: inherit; display: block; padding: 20px; border: 1px solid #E5E7EB; border-radius: 8px; background: white; transition: all 0.2s ease;" onmouseover="this.style.borderColor='#F97316'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.08)'" onmouseout="this.style.borderColor='#E5E7EB'; this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                        <h4 style="color: #F97316; margin-bottom: 6px; font-size: 18px; font-weight: 600;">{state['name']}</h4>
                        <p style="font-size: 14px; color: #6B7280;">{state['name']} supplier lien deadlines</p>
                    </a>"""
                print(f"Adding {state['slug']} to hub")

        if new_cards:
            # Try to insert after New Mexico, or fall back to Iowa
            search_marker = 'href="/state-lien-guides/new-mexico"'
            if search_marker not in content:
                search_marker = 'href="/state-lien-guides/iowa"'
            
            pos = content.find(search_marker)
            if pos != -1:
                end_tag = "</a>"
                end_pos = content.find(end_tag, pos)
                if end_pos != -1:
                    insert_pos = end_pos + len(end_tag)
                    new_content = content[:insert_pos] + new_cards + content[insert_pos:]
                    with open("public/state-lien-guides.html", "w", encoding="utf-8") as f:
                        f.write(new_content)
                    print("Hub page updated.")
                else:
                    print("Error: Closing </a> tag not found")
            else:
                print(f"Error: Anchor link ({search_marker}) not found in hub page")
        else:
            print("Hub page already up to date.")
    except Exception as e:
        print(f"Error updating hub page: {e}")

if __name__ == "__main__":
    update_sitemap()
    update_hub()
