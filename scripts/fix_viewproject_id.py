#!/usr/bin/env python3
"""
Fix viewProject() to convert calculationId to number
"""
from pathlib import Path
import re

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the viewProject function to convert ID to number
old_pattern = r'function viewProject\(calculationId\) \{\s*// Find the project from the loaded calculations\s*const project = window\.loadedCalculations\?\.find\(c => c\.id === calculationId\);'
new_code = """function viewProject(calculationId) {
                // Convert to number in case it's passed as a string
                const id = parseInt(calculationId, 10);
                // Find the project from the loaded calculations
                const project = window.loadedCalculations?.find(c => c.id === id);"""

content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Updated viewProject() to convert calculationId to number")

