#!/usr/bin/env python3
"""
Fix JavaScript syntax error and form submission issue
1. Remove orphaned } else { after editProject()
2. Ensure form has preventDefault
"""
from pathlib import Path
import re

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Remove the orphaned } else { after editProject() and fix deleteProject()
# The editProject function should end properly, then deleteProject should start fresh

# Find the problematic section
old_edit_end = r'                \}, 500\);\s*\} else \{\s*const errorData = await response\.json\(\)\.catch\(\(\) => \(\{ detail: \'Failed to delete project\' \}\)\);\s*alert\(errorData\.detail \|\| \'Failed to delete project\'\);\s*\}\s*\} catch \(error\) \{\s*console\.error\(\'Error deleting project:\', error\);\s*alert\(\'Error deleting project\'\);\s*\}\s*\}'

# Replace with proper structure: editProject closes, then deleteProject starts
new_delete_function = """            }
            
            async function deleteProject() {
                if (!currentProject) return;
                
                const confirmed = confirm(`Are you sure you want to delete the project "${currentProject.projectName || 'this project'}"? This cannot be undone.`);
                
                if (!confirmed) return;
                
                try {
                    const token = getSessionToken();
                    const response = await fetch(`/api/calculations/${currentProject.id}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${token}`
                        }
                    });
                    
                    if (response.ok) {
                        alert('Project deleted successfully');
                        closeProjectModal();
                        loadCalculationHistory(); // Reload the projects table
                    } else {
                        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete project' }));
                        alert(errorData.detail || 'Failed to delete project');
                    }
                } catch (error) {
                    console.error('Error deleting project:', error);
                    alert('Error deleting project');
                }
            }"""

# Replace the broken code
content = re.sub(old_edit_end, new_delete_function, content, flags=re.DOTALL)

# Fix 2: Ensure form submission has preventDefault (it should already have it, but let's verify)
# The form listener should already have e.preventDefault() at line 1033, but let's make sure
if 'e.preventDefault()' not in content.split('dashboardCalculatorForm')[1].split('addEventListener')[1].split('submit')[1][:500]:
    # If somehow preventDefault is missing, add it
    form_submit_pattern = r'(document\.getElementById\(\'dashboardCalculatorForm\'\)\.addEventListener\(\'submit\', async \(e\) => \{)\s*(?!\s*e\.preventDefault)'
    content = re.sub(form_submit_pattern, r'\1\n                e.preventDefault();', content)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed JavaScript syntax error and verified form submission prevention")

