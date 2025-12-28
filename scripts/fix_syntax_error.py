#!/usr/bin/env python3
"""
Fix JavaScript syntax error: Remove orphaned } else { after editProject()
"""
from pathlib import Path

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the problematic section around line 1628
# editProject() should end, then deleteProject() should start fresh
new_lines = []
i = 0
in_edit_function = False
found_orphaned_else = False

while i < len(lines):
    line = lines[i]
    
    # Detect end of editProject function
    if 'setTimeout(() => {' in line and 'alert(`Editing:' in lines[i+1] if i+1 < len(lines) else False:
        # This is the setTimeout in editProject
        new_lines.append(line)
        i += 1
        # Add the closing lines for editProject
        if i < len(lines) and '}, 500);' in lines[i]:
            new_lines.append(lines[i])
            i += 1
        # Close editProject function
        new_lines.append('            }\n')
        in_edit_function = False
        continue
    
    # Detect orphaned } else { 
    if '} else {' in line and 'const errorData = await response.json()' in (lines[i+1] if i+1 < len(lines) else ''):
        # This is the orphaned else - skip it and the next few lines until we find the proper deleteProject start
        found_orphaned_else = True
        # Skip until we find the catch block or closing brace
        while i < len(lines) and ('} catch (error) {' not in lines[i] and '} catch' not in lines[i]):
            i += 1
        # Now add the proper deleteProject function
        new_lines.append('\n            async function deleteProject() {\n')
        new_lines.append('                if (!currentProject) return;\n')
        new_lines.append('                \n')
        new_lines.append('                const confirmed = confirm(`Are you sure you want to delete the project "${currentProject.projectName || \'this project\'}"? This cannot be undone.`);\n')
        new_lines.append('                \n')
        new_lines.append('                if (!confirmed) return;\n')
        new_lines.append('                \n')
        new_lines.append('                try {\n')
        new_lines.append('                    const token = getSessionToken();\n')
        new_lines.append('                    const response = await fetch(`/api/calculations/${currentProject.id}`, {\n')
        new_lines.append('                        method: \'DELETE\',\n')
        new_lines.append('                        headers: {\n')
        new_lines.append('                            \'Authorization\': `Bearer ${token}`\n')
        new_lines.append('                        }\n')
        new_lines.append('                    });\n')
        new_lines.append('                    \n')
        new_lines.append('                    if (response.ok) {\n')
        new_lines.append('                        alert(\'Project deleted successfully\');\n')
        new_lines.append('                        closeProjectModal();\n')
        new_lines.append('                        loadCalculationHistory(); // Reload the projects table\n')
        new_lines.append('                    } else {\n')
        new_lines.append('                        const errorData = await response.json().catch(() => ({ detail: \'Failed to delete project\' }));\n')
        new_lines.append('                        alert(errorData.detail || \'Failed to delete project\');\n')
        new_lines.append('                    }\n')
        # Continue to the catch block
        continue
    
    new_lines.append(line)
    i += 1

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✅ Fixed JavaScript syntax error")

