#!/usr/bin/env python3
"""
Fix downloadProjectPDF() to include project_type parameter - Version 2
"""
from pathlib import Path

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the function and update it
in_function = False
updated = False
new_lines = []

for i, line in enumerate(lines):
    if 'function downloadProjectPDF()' in line:
        in_function = True
        new_lines.append(line)
        continue
    
    if in_function:
        # Look for the pdfUrl line
        if 'const pdfUrl =' in line and 'project_type' not in line:
            # Insert project type before the pdfUrl line
            new_lines.append('                // Get project type (default to commercial if not specified)\n')
            new_lines.append('                const projectType = currentProject.projectType || \'commercial\';\n')
            new_lines.append('                \n')
            new_lines.append('                // Build the PDF URL with all required parameters\n')
            # Update the pdfUrl line to include project_type
            if '&state_name=' in line:
                line = line.replace('&state_name=', '&state_name=').replace('`;', '&project_type=${projectType}`;')
            new_lines.append(line)
            updated = True
            continue
        
        # Stop when we hit the closing brace
        if line.strip() == '}' and updated:
            in_function = False
            updated = False
    
    new_lines.append(line)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Fixed PDF download to include project_type parameter")

