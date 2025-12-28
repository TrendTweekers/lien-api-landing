#!/usr/bin/env python3
"""
Fix PDF download, editProject, and add beta banner
"""
from pathlib import Path
import re

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Update downloadProjectPDF() to include project_type
old_download = r'function downloadProjectPDF\(\) \{[^}]*\}'
new_download = """function downloadProjectPDF() {
                if (!currentProject) return;
                
                // Format the invoice date for the URL
                const invoiceDate = currentProject.invoiceDate;
                if (!invoiceDate) {
                    alert('Invoice date not available for this project');
                    return;
                }
                
                // Format date as YYYY-MM-DD
                const dateStr = new Date(invoiceDate).toISOString().split('T')[0];
                
                // Get project type (default to commercial if not specified)
                const projectType = currentProject.projectType || 'commercial';
                
                // Build the PDF URL with all required parameters
                const stateCode = currentProject.stateCode || 'UNKNOWN';
                const stateName = currentProject.state || '';
                const pdfUrl = `/api/v1/guide/${stateCode}/pdf?invoice_date=${dateStr}&state_name=${encodeURIComponent(stateName)}&project_type=${projectType}`;
                
                // Open PDF in new tab
                window.open(pdfUrl, '_blank');
            }"""

# Use a more specific pattern to match the exact function
content = re.sub(
    r'function downloadProjectPDF\(\) \{[\s\S]*?window\.open\(pdfUrl, \'_\'blank\'\);[\s\S]*?\}',
    new_download,
    content
)

# Fix 2: Update editProject() function
old_edit = r'function editProject\(\) \{[\s\S]*?alert\(\'Project loaded into calculator[\s\S]*?\}\);[\s\S]*?\}'
new_edit = """function editProject() {
                if (!currentProject) return;
                
                // Close modal
                closeProjectModal();
                
                // Pre-fill the calculator with project data
                const dateInput = document.getElementById('dashInvoiceDate');
                const stateSelect = document.getElementById('dashState');
                const projectTypeSelect = document.getElementById('dashProjectType');
                
                if (dateInput && currentProject.invoiceDate) {
                    // Format date as YYYY-MM-DD for date input
                    const dateStr = new Date(currentProject.invoiceDate).toISOString().split('T')[0];
                    dateInput.value = dateStr;
                }
                
                if (stateSelect && currentProject.stateCode) {
                    stateSelect.value = currentProject.stateCode;
                    // Trigger change event to show project type field if needed
                    stateSelect.dispatchEvent(new Event('change'));
                }
                
                if (projectTypeSelect && currentProject.projectType) {
                    projectTypeSelect.value = currentProject.projectType;
                } else if (projectTypeSelect) {
                    // Default to commercial if not specified
                    projectTypeSelect.value = 'commercial';
                }
                
                // Scroll to calculator section
                const calculatorSection = document.querySelector('.calculate-section') || document.getElementById('calculate-section') || document.querySelector('form#dashboardCalculatorForm');
                if (calculatorSection) {
                    calculatorSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                
                // Optional: Show a message
                setTimeout(() => {
                    alert(`Editing: ${currentProject.projectName}. Make your changes and click "Save Project & Set Reminders" to update.`);
                }, 500);
            }"""

content = re.sub(old_edit, new_edit, content)

# Fix 3: Add beta banner before integrations grid
beta_banner = """
            
            <!-- BETA BANNER -->
            <div style="background: #fef3c7; border: 2px solid #f59e0b; padding: 12px 16px; border-radius: 8px; margin-bottom: 24px; display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 24px;">⚠️</span>
                <div>
                    <strong style="color: #92400e;">Beta Feature</strong>
                    <p style="margin: 4px 0 0 0; color: #78350f; font-size: 14px;">
                        Integrations are currently in beta testing. For now, we recommend manually entering invoice dates into the calculator above.
                    </p>
                </div>
            </div>
            
"""

# Add banner after the h2 and before the grid
content = re.sub(
    r'(<h2 class="text-2xl font-bold text-gray-900 mb-6">Accounting Integrations</h2>)\s*(<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">)',
    r'\1' + beta_banner + r'\2',
    content
)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Fixed PDF download, editProject, and added beta banner")

