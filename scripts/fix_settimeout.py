#!/usr/bin/env python3
"""
Fix broken setTimeout structure in editProject function
"""
from pathlib import Path

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix the broken setTimeout around line 1625-1628
new_lines = []
i = 0

while i < len(lines):
    line = lines[i]
    
    # Find the broken setTimeout structure
    if 'setTimeout(() => {' in line and i + 1 < len(lines) and '}' in lines[i+1] and 'alert(`Editing:' in lines[i+2]:
        # This is the broken setTimeout - fix it
        new_lines.append('                // Optional: Show a message\n')
        new_lines.append('                setTimeout(() => {\n')
        new_lines.append('                    alert(`Editing: ${currentProject.projectName}. Make your changes and click "Save Project & Set Reminders" to update.`);\n')
        new_lines.append('                }, 500);\n')
        new_lines.append('            }\n')
        # Skip the broken lines
        i += 4  # Skip setTimeout, }, alert, and }, 500);
        continue
    
    new_lines.append(line)
    i += 1

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Fixed broken setTimeout structure")

