#!/usr/bin/env python3
"""
Fix downloadProjectPDF() to include project_type parameter
"""
from pathlib import Path
import re

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the PDF URL generation line
old_url = r'const pdfUrl = `/api/v1/guide/\$\{stateCode\}/pdf\?invoice_date=\$\{dateStr\}&state_name=\$\{encodeURIComponent\(stateName\)\}`;'
new_url_code = """                // Get project type (default to commercial if not specified)
                const projectType = currentProject.projectType || 'commercial';
                
                // Build the PDF URL with all required parameters
                const pdfUrl = `/api/v1/guide/${stateCode}/pdf?invoice_date=${dateStr}&state_name=${encodeURIComponent(stateName)}&project_type=${projectType}`;"""

# Replace the URL line and add project type before it
content = re.sub(
    r'(const stateCode = currentProject\.stateCode \|\| \'UNKNOWN\';\s*const stateName = currentProject\.state \|\| \'\';\s*)const pdfUrl = `/api/v1/guide/\$\{stateCode\}/pdf\?invoice_date=\$\{dateStr\}&state_name=\$\{encodeURIComponent\(stateName\)\}`;',
    r'\1' + new_url_code,
    content
)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed PDF download to include project_type parameter")

