#!/usr/bin/env python3
"""
Add project details modal to customer-dashboard.html
"""
from pathlib import Path
import re

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add modal HTML before </body>
modal_html = """
    <!-- Project Details Modal -->
    <div id="project-details-modal" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center;">
        <div style="background: white; border-radius: 12px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto; padding: 24px; position: relative;">
            <!-- Close Button -->
            <button onclick="closeProjectModal()" style="position: absolute; top: 16px; right: 16px; background: none; border: none; font-size: 24px; cursor: pointer; color: #718096;">
                ×
            </button>
            
            <!-- Modal Header -->
            <h2 style="margin-top: 0; color: #2d3748;">Project Details</h2>
            
            <!-- Project Info -->
            <div id="project-details-content">
                <!-- Will be populated by JavaScript -->
            </div>
            
            <!-- Action Buttons -->
            <div style="display: flex; gap: 12px; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 24px;">
                <button onclick="downloadProjectPDF()" style="background: #f97316; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; flex: 1;">
                    📄 Download PDF
                </button>
                <button onclick="editProject()" style="background: #3182ce; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; flex: 1;">
                    ✏️ Edit Project
                </button>
                <button onclick="deleteProject()" style="background: #e53e3e; color: white; padding: 12px 24px; border: none; border-radius: 6px; cursor: pointer; flex: 1;">
                    🗑️ Delete
                </button>
            </div>
        </div>
    </div>
"""

content = content.replace('</body>', modal_html + '\n</body>')

# 2. Replace viewProject function
old_view_project = r'function viewProject\(calculationId\) \{[^}]*\}'
new_view_project = """function viewProject(calculationId) {
                // Find the project from the loaded calculations
                const project = window.loadedCalculations?.find(c => c.id === calculationId);
                
                if (!project) {
                    alert('Project not found');
                    return;
                }
                
                currentProject = project;
                
                // Format the project details
                const detailsHtml = `
                    <div style="display: grid; gap: 16px;">
                        <!-- Project Name -->
                        <div>
                            <label style="font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px;">
                                Project Name
                            </label>
                            <div style="padding: 12px; background: #f7fafc; border-radius: 6px; color: #2d3748;">
                                ${escapeHtml(project.projectName || project.project_name || 'N/A')}
                            </div>
                        </div>
                        
                        <!-- Client Name -->
                        <div>
                            <label style="font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px;">
                                Client/Customer
                            </label>
                            <div style="padding: 12px; background: #f7fafc; border-radius: 6px; color: #2d3748;">
                                ${escapeHtml(project.clientName || project.client_name || 'N/A')}
                            </div>
                        </div>
                        
                        <!-- Invoice Amount -->
                        <div>
                            <label style="font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px;">
                                Invoice Amount
                            </label>
                            <div style="padding: 12px; background: #f7fafc; border-radius: 6px; color: #2d3748;">
                                $${parseFloat(project.invoiceAmount || project.invoice_amount || 0).toLocaleString()}
                            </div>
                        </div>
                        
                        <!-- State -->
                        <div>
                            <label style="font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px;">
                                State
                            </label>
                            <div style="padding: 12px; background: #f7fafc; border-radius: 6px; color: #2d3748;">
                                ${escapeHtml(project.state || 'N/A')} ${project.stateCode || project.state_code ? `(${project.stateCode || project.state_code})` : ''}
                            </div>
                        </div>
                        
                        <!-- Invoice Date -->
                        <div>
                            <label style="font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px;">
                                Invoice/Delivery Date
                            </label>
                            <div style="padding: 12px; background: #f7fafc; border-radius: 6px; color: #2d3748;">
                                ${project.invoiceDate || project.invoice_date ? new Date(project.invoiceDate || project.invoice_date).toLocaleDateString() : 'N/A'}
                            </div>
                        </div>
                        
                        <!-- Preliminary Deadline -->
                        <div style="background: #c6f6d5; padding: 16px; border-radius: 8px; border: 2px solid #68d391;">
                            <label style="font-weight: bold; color: #276749; display: block; margin-bottom: 4px;">
                                📋 Preliminary Notice Deadline
                            </label>
                            <div style="font-size: 18px; color: #22543d; font-weight: bold;">
                                ${project.prelimDeadline || project.prelim_deadline ? new Date(project.prelimDeadline || project.prelim_deadline).toLocaleDateString() : 'Not Required'}
                            </div>
                            ${(project.prelimDeadline || project.prelim_deadline) && (project.prelimDeadlineDays || project.prelim_deadline_days) ? `
                                <div style="font-size: 14px; color: #276749; margin-top: 4px;">
                                    ${project.prelimDeadlineDays || project.prelim_deadline_days} days from invoice date
                                </div>
                            ` : ''}
                        </div>
                        
                        <!-- Lien Deadline -->
                        <div style="background: #fef5e7; padding: 16px; border-radius: 8px; border: 2px solid #f6ad55;">
                            <label style="font-weight: bold; color: #7c2d12; display: block; margin-bottom: 4px;">
                                ⚖️ Lien Filing Deadline
                            </label>
                            <div style="font-size: 18px; color: #7c2d12; font-weight: bold;">
                                ${project.lienDeadline || project.lien_deadline ? new Date(project.lienDeadline || project.lien_deadline).toLocaleDateString() : 'N/A'}
                            </div>
                            ${(project.lienDeadlineDays || project.lien_deadline_days) ? `
                                <div style="font-size: 14px; color: #7c2d12; margin-top: 4px;">
                                    ${project.lienDeadlineDays || project.lien_deadline_days} days from invoice date
                                </div>
                            ` : ''}
                        </div>
                        
                        <!-- Notes -->
                        ${project.notes ? `
                            <div>
                                <label style="font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px;">
                                    Notes
                                </label>
                                <div style="padding: 12px; background: #f7fafc; border-radius: 6px; color: #2d3748; white-space: pre-wrap;">
                                    ${escapeHtml(project.notes)}
                                </div>
                            </div>
                        ` : ''}
                        
                        <!-- QuickBooks Invoice ID (if applicable) -->
                        ${project.quickbooksInvoiceId || project.quickbooks_invoice_id ? `
                            <div>
                                <label style="font-weight: bold; color: #4a5568; display: block; margin-bottom: 4px;">
                                    QuickBooks Invoice
                                </label>
                                <div style="padding: 12px; background: #ebf8ff; border-radius: 6px; color: #2c5282;">
                                    Invoice #${escapeHtml(project.quickbooksInvoiceId || project.quickbooks_invoice_id)}
                                </div>
                            </div>
                        ` : ''}
                        
                        <!-- Created Date -->
                        <div style="font-size: 12px; color: #718096; text-align: center; padding-top: 12px; border-top: 1px solid #e2e8f0;">
                            Created: ${project.createdAt || project.created_at ? new Date(project.createdAt || project.created_at).toLocaleString() : 'N/A'}
                        </div>
                    </div>
                `;
                
                // Populate modal
                document.getElementById('project-details-content').innerHTML = detailsHtml;
                
                // Show modal
                const modal = document.getElementById('project-details-modal');
                modal.style.display = 'flex';
            }"""

content = re.sub(old_view_project, new_view_project, content, flags=re.DOTALL)

# 3. Add global variables and helper functions before viewProject
if 'let currentProject = null;' not in content:
    # Find the viewProject function and add variables before it
    content = re.sub(
        r'(function viewProject\()',
        '            // Global variable to store current project\n            let currentProject = null;\n            let loadedCalculations = [];\n\n            \\1',
        content
    )

# 4. Add helper functions after viewProject
helper_functions = """
            function closeProjectModal() {
                document.getElementById('project-details-modal').style.display = 'none';
                currentProject = null;
            }

            function downloadProjectPDF() {
                if (!currentProject) return;
                
                // Get invoice date
                const invoiceDate = currentProject.invoiceDate || currentProject.invoice_date;
                if (!invoiceDate) {
                    alert('Invoice date not available for this project');
                    return;
                }
                
                // Format date as YYYY-MM-DD
                const dateStr = new Date(invoiceDate).toISOString().split('T')[0];
                const stateCode = currentProject.stateCode || currentProject.state_code || 'UNKNOWN';
                const stateName = currentProject.state || '';
                
                // Generate PDF URL with invoice date
                const pdfUrl = `/api/v1/guide/${stateCode}/pdf?invoice_date=${dateStr}&state_name=${encodeURIComponent(stateName)}`;
                
                // Open PDF in new tab
                window.open(pdfUrl, '_blank');
            }

            function editProject() {
                if (!currentProject) return;
                
                // Close modal
                closeProjectModal();
                
                // Pre-fill the calculator with project data
                const dateInput = document.getElementById('dashInvoiceDate');
                const stateSelect = document.getElementById('dashState');
                
                if (dateInput && (currentProject.invoiceDate || currentProject.invoice_date)) {
                    const invoiceDate = currentProject.invoiceDate || currentProject.invoice_date;
                    // Format date as YYYY-MM-DD for date input
                    const dateStr = new Date(invoiceDate).toISOString().split('T')[0];
                    dateInput.value = dateStr;
                }
                
                if (stateSelect && (currentProject.stateCode || currentProject.state_code)) {
                    stateSelect.value = currentProject.stateCode || currentProject.state_code;
                }
                
                // Scroll to calculator
                const calculatorSection = document.getElementById('calculator') || document.querySelector('form#dashboardCalculatorForm');
                if (calculatorSection) {
                    calculatorSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
                
                alert('Project loaded into calculator. Make your changes and save again.');
            }

            async function deleteProject() {
                if (!currentProject) return;
                
                const confirmed = confirm(`Are you sure you want to delete the project "${currentProject.projectName || currentProject.project_name || 'this project'}"? This cannot be undone.`);
                
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
            }

            // Close modal when clicking outside
            document.addEventListener('DOMContentLoaded', function() {
                const modal = document.getElementById('project-details-modal');
                if (modal) {
                    modal.addEventListener('click', function(e) {
                        if (e.target === this) {
                            closeProjectModal();
                        }
                    });
                }
            });
"""

# Add helper functions after viewProject function
if 'function closeProjectModal()' not in content:
    content = re.sub(
        r'(modal\.style\.display = \'flex\';\s*\})',
        r'\1' + helper_functions,
        content
    )

# 5. Update loadCalculationHistory to store data globally
content = re.sub(
    r'(const data = await response\.json\(\);\s*const tbody = document\.getElementById\(\'history-tbody\'\);)',
    r'\1\n                    \n                    // Store globally so viewProject can access them\n                    window.loadedCalculations = data.calculations || [];',
    content
)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Added project details modal to customer-dashboard.html")

