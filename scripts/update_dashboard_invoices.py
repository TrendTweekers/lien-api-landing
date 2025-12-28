#!/usr/bin/env python3
"""
Update customer-dashboard.html to add QuickBooks invoice functionality
"""
import re
from pathlib import Path

dashboard_file = Path(__file__).parent.parent / "customer-dashboard.html"

with open(dashboard_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Update the heading and add description using regex
content = re.sub(
    r"let html = '<h4 class=\"font-semibold text-lg mb-4 text-gray-900\">Recent Invoices from QuickBooks</h4>';",
    "let html = '<h4 class=\"font-semibold text-lg mb-4 text-gray-900\">📊 QuickBooks Invoices</h4>';\n            html += '<p class=\"text-sm text-gray-600 mb-4\">Select invoices to calculate lien deadlines</p>';",
    content
)

# Update invoice display logic
old_invoice_loop = """invoices.forEach(inv => {
                const date = inv.date || 'N/A';
                const amount = inv.amount ? `$${inv.amount.toFixed(2)}` : '$0.00';
                const state = inv.state || '';
                const customer = escapeHtml(inv.customer || 'Unknown');
                
                html += `
                    <div class="bg-white p-4 rounded-lg border border-gray-200 hover:border-blue-300 transition">
                        <div class="flex justify-between items-center flex-wrap gap-4">
                            <div class="flex-1">
                                <p class="font-medium text-gray-900">${customer}</p>
                                <p class="text-sm text-gray-600">Date: ${date} | Amount: ${amount}</p>
                                ${state ? `<p class="text-xs text-gray-500 mt-1">State: ${state}</p>` : ''}
                            </div>
                            <button 
                                onclick="calculateForInvoice('${date}', '${state}')"
                                class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition whitespace-nowrap"
                            >
                                Calculate Deadline
                            </button>
                        </div>
                    </div>
                `;
            });"""

new_invoice_loop = """invoices.forEach(inv => {
                const date = inv.date || inv.invoice_number || 'N/A';
                const amount = inv.amount ? `$${inv.amount.toLocaleString()}` : '$0.00';
                const customer = escapeHtml(inv.customer_name || inv.customer || 'Unknown');
                const invoiceId = inv.id || inv.invoice_id || '';
                const invoiceNumber = inv.invoice_number || '';
                const balance = inv.balance || 0;
                const status = inv.status || (balance > 0 ? 'Unpaid' : 'Paid');
                
                html += `
                    <div class="bg-white p-4 rounded-lg border border-gray-200 hover:border-blue-300 transition">
                        <div class="flex justify-between items-center flex-wrap gap-4">
                            <div class="flex-1">
                                <p class="font-medium text-gray-900">${date} - ${customer}</p>
                                <p class="text-sm text-gray-600">Amount: <span class="text-gray-900 font-semibold">${amount}</span></p>
                                ${invoiceNumber ? `<p class="text-xs text-gray-500">Invoice #${invoiceNumber}</p>` : ''}
                                <p class="text-xs ${status === 'Unpaid' ? 'text-red-600' : 'text-green-600'} font-medium mt-1">${status}</p>
                            </div>
                            <div class="flex items-center gap-2">
                                <select id="state-${invoiceId}" class="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    <option value="">Select State...</option>
                                    ${getStateOptions()}
                                </select>
                                <button 
                                    onclick="calculateFromInvoice('${invoiceId}', '${date}', '${escapeHtml(customer)}', ${inv.amount || 0})"
                                    class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition whitespace-nowrap"
                                >
                                    Calculate
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });"""

# Use regex with flexible whitespace
content = re.sub(
    re.escape(old_invoice_loop).replace(r'\ ', r'\s+'),
    new_invoice_loop,
    content,
    flags=re.DOTALL
)

# Add new functions before escapeHtml
insertion_point = "        }\n\n        function escapeHtml(text) {"
new_functions = """        }
        
        function getStateOptions() {
            const states = [
                { code: 'AL', name: 'Alabama' }, { code: 'AK', name: 'Alaska' }, { code: 'AZ', name: 'Arizona' },
                { code: 'AR', name: 'Arkansas' }, { code: 'CA', name: 'California' }, { code: 'CO', name: 'Colorado' },
                { code: 'CT', name: 'Connecticut' }, { code: 'DE', name: 'Delaware' }, { code: 'FL', name: 'Florida' },
                { code: 'GA', name: 'Georgia' }, { code: 'HI', name: 'Hawaii' }, { code: 'ID', name: 'Idaho' },
                { code: 'IL', name: 'Illinois' }, { code: 'IN', name: 'Indiana' }, { code: 'IA', name: 'Iowa' },
                { code: 'KS', name: 'Kansas' }, { code: 'KY', name: 'Kentucky' }, { code: 'LA', name: 'Louisiana' },
                { code: 'ME', name: 'Maine' }, { code: 'MD', name: 'Maryland' }, { code: 'MA', name: 'Massachusetts' },
                { code: 'MI', name: 'Michigan' }, { code: 'MN', name: 'Minnesota' }, { code: 'MS', name: 'Mississippi' },
                { code: 'MO', name: 'Missouri' }, { code: 'MT', name: 'Montana' }, { code: 'NE', name: 'Nebraska' },
                { code: 'NV', name: 'Nevada' }, { code: 'NH', name: 'New Hampshire' }, { code: 'NJ', name: 'New Jersey' },
                { code: 'NM', name: 'New Mexico' }, { code: 'NY', name: 'New York' }, { code: 'NC', name: 'North Carolina' },
                { code: 'ND', name: 'North Dakota' }, { code: 'OH', name: 'Ohio' }, { code: 'OK', name: 'Oklahoma' },
                { code: 'OR', name: 'Oregon' }, { code: 'PA', name: 'Pennsylvania' }, { code: 'RI', name: 'Rhode Island' },
                { code: 'SC', name: 'South Carolina' }, { code: 'SD', name: 'South Dakota' }, { code: 'TN', name: 'Tennessee' },
                { code: 'TX', name: 'Texas' }, { code: 'UT', name: 'Utah' }, { code: 'VT', name: 'Vermont' },
                { code: 'VA', name: 'Virginia' }, { code: 'WA', name: 'Washington' }, { code: 'WV', name: 'West Virginia' },
                { code: 'WI', name: 'Wisconsin' }, { code: 'WY', name: 'Wyoming' }, { code: 'DC', name: 'District of Columbia' }
            ];
            
            return states.map(s => `<option value="${s.code}">${s.code} - ${s.name}</option>`).join('');
        }
        
        function calculateFromInvoice(invoiceId, date, customer, amount) {
            const stateSelect = document.getElementById(`state-${invoiceId}`);
            const state = stateSelect ? stateSelect.value : '';
            
            if (!state) {
                alert('Please select a state first');
                return;
            }
            
            // Pre-fill calculator
            const dateInput = document.getElementById('dashInvoiceDate');
            const stateSelectMain = document.getElementById('dashState');
            
            if (dateInput && date) {
                dateInput.value = date;
            }
            
            if (stateSelectMain && state) {
                stateSelectMain.value = state;
            }
            
            // Scroll to calculator section
            const calculatorSection = document.getElementById('calculator') || document.querySelector('[id*="calculator"]') || document.querySelector('form#dashboardCalculatorForm');
            if (calculatorSection) {
                calculatorSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            
            // Auto-calculate after a short delay
            setTimeout(() => {
                const calculateButton = document.querySelector('form#dashboardCalculatorForm button[type="submit"]');
                if (calculateButton) {
                    calculateButton.click();
                }
            }, 500);
        }

        function escapeHtml(text) {"""

# Use regex for insertion point
content = re.sub(
    re.escape(insertion_point),
    new_functions,
    content
)

with open(dashboard_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Updated customer-dashboard.html")

