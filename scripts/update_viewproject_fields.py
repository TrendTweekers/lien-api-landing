#!/usr/bin/env python3
"""
Update viewProject() function to use camelCase field names only
"""
from pathlib import Path
import re

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all snake_case fallbacks with camelCase only in viewProject function
# Pattern: project.fieldName || project.field_name -> project.fieldName

replacements = [
    # Project name
    (r'project\.projectName \|\| project\.project_name', 'project.projectName'),
    # Client name
    (r'project\.clientName \|\| project\.client_name', 'project.clientName'),
    # Invoice amount
    (r'project\.invoiceAmount \|\| project\.invoice_amount', 'project.invoiceAmount'),
    # Invoice date
    (r'project\.invoiceDate \|\| project\.invoice_date', 'project.invoiceDate'),
    # State code
    (r'project\.stateCode \|\| project\.state_code', 'project.stateCode'),
    # Preliminary deadline
    (r'project\.prelimDeadline \|\| project\.prelim_deadline', 'project.prelimDeadline'),
    (r'project\.prelimDeadlineDays \|\| project\.prelim_deadline_days', 'project.prelimDeadlineDays'),
    # Lien deadline
    (r'project\.lienDeadline \|\| project\.lien_deadline', 'project.lienDeadline'),
    (r'project\.lienDeadlineDays \|\| project\.lien_deadline_days', 'project.lienDeadlineDays'),
    # QuickBooks invoice ID
    (r'project\.quickbooksInvoiceId \|\| project\.quickbooks_invoice_id', 'project.quickbooksInvoiceId'),
    # Created at
    (r'project\.createdAt \|\| project\.created_at', 'project.createdAt'),
]

# Apply replacements
for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Also fix the conditional checks that use || for fallback
# Pattern: (project.fieldName || project.field_name) -> project.fieldName
conditional_replacements = [
    (r'\(project\.prelimDeadline \|\| project\.prelim_deadline\)', 'project.prelimDeadline'),
    (r'\(project\.prelimDeadlineDays \|\| project\.prelim_deadline_days\)', 'project.prelimDeadlineDays'),
    (r'\(project\.lienDeadline \|\| project\.lien_deadline\)', 'project.lienDeadline'),
    (r'\(project\.lienDeadlineDays \|\| project\.lien_deadline_days\)', 'project.lienDeadlineDays'),
]

for pattern, replacement in conditional_replacements:
    content = re.sub(pattern, replacement, content)

# Fix downloadProjectPDF function
content = re.sub(
    r'currentProject\.invoiceDate \|\| currentProject\.invoice_date',
    'currentProject.invoiceDate',
    content
)
content = re.sub(
    r'currentProject\.stateCode \|\| currentProject\.state_code',
    'currentProject.stateCode',
    content
)

# Fix editProject function
content = re.sub(
    r'\(currentProject\.invoiceDate \|\| currentProject\.invoice_date\)',
    'currentProject.invoiceDate',
    content
)
content = re.sub(
    r'currentProject\.invoiceDate \|\| currentProject\.invoice_date',
    'currentProject.invoiceDate',
    content
)
content = re.sub(
    r'\(currentProject\.stateCode \|\| currentProject\.state_code\)',
    'currentProject.stateCode',
    content
)
content = re.sub(
    r'currentProject\.stateCode \|\| currentProject\.state_code',
    'currentProject.stateCode',
    content
)

# Fix deleteProject function
content = re.sub(
    r'currentProject\.projectName \|\| currentProject\.project_name',
    'currentProject.projectName',
    content
)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Updated viewProject() function to use camelCase field names only")

