// dashboard.js

const API_BASE = ''; // Use relative URL since API is on same domain

// Check login status on page load
document.addEventListener('DOMContentLoaded', () => {
    checkLoginStatus();
    loadHistory();
    checkZapierStatus();
});

function checkLoginStatus() {
    const userEmail = localStorage.getItem('userEmail');
    
    if (userEmail) {
        // User is logged in
        showDashboard(userEmail);
    } else {
        // User is not logged in
        showLogin();
    }
}

function showLogin() {
    document.getElementById('loginSection').classList.remove('hidden');
    document.getElementById('dashboardSection').classList.add('hidden');
    document.getElementById('logoutBtn').classList.add('hidden');
}

function showDashboard(email) {
    document.getElementById('loginSection').classList.add('hidden');
    document.getElementById('dashboardSection').classList.remove('hidden');
    document.getElementById('userEmail').textContent = email;
    document.getElementById('logoutBtn').classList.remove('hidden');
    
    // Set default date
    document.getElementById('dashInvoiceDate').valueAsDate = new Date();
    
    // Load history
    loadHistory();
}

// Login Form - Real API Authentication
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('error-message');
    
    // Clear previous errors
    errorDiv.textContent = '';
    errorDiv.classList.add('hidden');
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({email, password})
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // Store session token
            localStorage.setItem('session_token', data.token);
            localStorage.setItem('user_email', data.email);
            
            // Redirect to React dashboard
            window.location.href = '/dashboard';
        } else {
            const error = await response.json();
            errorDiv.textContent = error.detail || 'Invalid email or password';
            errorDiv.classList.remove('hidden');
        }
    } catch (err) {
        console.error('Login error:', err);
        errorDiv.textContent = 'Login failed. Please try again.';
        errorDiv.classList.remove('hidden');
    }
});

// Logout
document.getElementById('logoutBtn').addEventListener('click', async () => {
    try {
        // Call logout API endpoint if token exists
        const token = localStorage.getItem('session_token');
        if (token) {
            try {
                await fetch('/api/logout', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });
            } catch (error) {
                // If logout endpoint doesn't exist, that's okay - we'll still clear client-side
                console.log('Logout endpoint not available, clearing client-side only');
            }
        }
        
        // Clear all localStorage items
        localStorage.clear();
        sessionStorage.clear();
        
        // Clear any cookies
        document.cookie.split(";").forEach((c) => {
            document.cookie = c
                .replace(/^ +/, "")
                .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
        });
        
        // Show login screen
        showLogin();
        
        // Redirect to login page after a brief delay
        setTimeout(() => {
            window.location.href = '/login.html';
        }, 500);
    } catch (error) {
        console.error('Logout error:', error);
        // Even if there's an error, clear localStorage and redirect
        localStorage.clear();
        sessionStorage.clear();
        showLogin();
        window.location.href = '/login.html';
    }
});

// Dashboard Calculator Form
document.getElementById('dashboardCalculatorForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const invoiceDate = document.getElementById('dashInvoiceDate').value;
    const state = document.getElementById('dashState').value;
    const role = document.getElementById('dashRole').value;
    
    const submitButton = e.target.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;
    submitButton.textContent = 'Calculating...';
    submitButton.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE}/api/v1/calculate-deadline`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                invoice_date: invoiceDate,
                state: state,
                role: role
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert(`Error: ${data.error}`);
            return;
        }
        
        // Display results
        displayDashboardResults(data);
        
        // Save to history
        saveCalculation(data);
        
        // Reload history table
        loadHistory();
        
        // Scroll to results
        document.getElementById('dashResults').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to calculate. Please try again.');
    } finally {
        submitButton.textContent = originalText;
        submitButton.disabled = false;
    }
});

function displayDashboardResults(data) {
    document.getElementById('dashResults').classList.remove('hidden');
    
    // Preliminary Notice
    const prelimCard = document.getElementById('dashPrelimCard');
    prelimCard.className = `bg-white shadow-lg rounded-lg p-6 border-l-4 ${getUrgencyColor(data.preliminary_notice.urgency)}`;
    document.getElementById('dashPrelimTitle').textContent = data.preliminary_notice.name;
    document.getElementById('dashPrelimDate').textContent = formatDate(data.preliminary_notice.deadline);
    document.getElementById('dashPrelimDays').textContent = `${data.preliminary_notice.days_from_now} days`;
    document.getElementById('dashPrelimDays').className = `text-2xl font-bold ${getUrgencyTextColor(data.preliminary_notice.urgency)}`;
    
    // Lien Filing
    const lienCard = document.getElementById('dashLienCard');
    lienCard.className = `bg-white shadow-lg rounded-lg p-6 border-l-4 ${getUrgencyColor(data.lien_filing.urgency)}`;
    document.getElementById('dashLienTitle').textContent = data.lien_filing.name;
    document.getElementById('dashLienDate').textContent = formatDate(data.lien_filing.deadline);
    document.getElementById('dashLienDays').textContent = `${data.lien_filing.days_from_now} days`;
    document.getElementById('dashLienDays').className = `text-2xl font-bold ${getUrgencyTextColor(data.lien_filing.urgency)}`;
}

function saveCalculation(data) {
    // Get existing history
    let history = JSON.parse(localStorage.getItem('calculationHistory') || '[]');
    
    // Add new calculation
    const calculation = {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        invoice_date: data.invoice_date,
        state: data.state_code,
        state_name: data.state,
        prelim_deadline: data.preliminary_notice.deadline,
        lien_deadline: data.lien_filing.deadline,
        data: data // Store full data for PDF generation
    };
    
    history.unshift(calculation); // Add to beginning
    
    // Keep only last 100 calculations
    if (history.length > 100) {
        history = history.slice(0, 100);
    }
    
    localStorage.setItem('calculationHistory', JSON.stringify(history));
}

function loadHistory() {
    const history = JSON.parse(localStorage.getItem('calculationHistory') || '[]');
    const tbody = document.getElementById('historyTableBody');
    const noHistory = document.getElementById('noHistory');
    
    if (history.length === 0) {
        tbody.innerHTML = '';
        noHistory.classList.remove('hidden');
        return;
    }
    
    noHistory.classList.add('hidden');
    
    tbody.innerHTML = history.map(calc => `
        <tr>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${new Date(calc.timestamp).toLocaleDateString()}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${calc.invoice_date}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${calc.state}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${calc.prelim_deadline}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                ${calc.lien_deadline}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                <button onclick="downloadHistoryPDF(${calc.id})" class="text-blue-600 hover:text-blue-900 mr-3">
                    📄 PDF
                </button>
                <button onclick="deleteCalculation(${calc.id})" class="text-red-600 hover:text-red-900">
                    🗑️ Delete
                </button>
            </td>
        </tr>
    `).join('');
}

function deleteCalculation(id) {
    if (!confirm('Delete this calculation?')) return;
    
    let history = JSON.parse(localStorage.getItem('calculationHistory') || '[]');
    history = history.filter(calc => calc.id !== id);
    localStorage.setItem('calculationHistory', JSON.stringify(history));
    loadHistory();
}

function downloadHistoryPDF(id) {
    const history = JSON.parse(localStorage.getItem('calculationHistory') || '[]');
    const calc = history.find(c => c.id === id);
    
    if (calc && calc.data) {
        generatePDF(calc.data);
    } else {
        alert('Unable to generate PDF. Please recalculate.');
    }
}

// Export to CSV
document.getElementById('exportCSV').addEventListener('click', () => {
    const history = JSON.parse(localStorage.getItem('calculationHistory') || '[]');
    
    if (history.length === 0) {
        alert('No calculations to export');
        return;
    }
    
    // Create CSV content
    const headers = ['Date', 'Invoice Date', 'State', 'Prelim Deadline', 'Lien Deadline'];
    const rows = history.map(calc => [
        new Date(calc.timestamp).toLocaleDateString(),
        calc.invoice_date,
        calc.state,
        calc.prelim_deadline,
        calc.lien_deadline
    ]);
    
    const csvContent = [
        headers.join(','),
        ...rows.map(row => row.join(','))
    ].join('\n');
    
    // Download CSV
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lien-calculations-${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
});

// Utility functions
function getUrgencyColor(urgency) {
    switch(urgency) {
        case 'critical': return 'border-red-500';
        case 'warning': return 'border-yellow-500';
        default: return 'border-green-500';
    }
}

function getUrgencyTextColor(urgency) {
    switch(urgency) {
        case 'critical': return 'text-red-600';
        case 'warning': return 'text-yellow-600';
        default: return 'text-green-600';
    }
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
}

// PDF Generation (same as calculator.js)
function generatePDF(data) {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    const pageWidth = doc.internal.pageSize.getWidth();
    const margin = 20;
    let yPos = 20;
    
    // Header
    doc.setFontSize(24);
    doc.setTextColor(37, 99, 235);
    doc.text('LienDeadline', margin, yPos);
    
    yPos += 10;
    doc.setFontSize(18);
    doc.setTextColor(0, 0, 0);
    doc.text('Lien Deadline Report', margin, yPos);
    
    yPos += 5;
    doc.setFontSize(10);
    doc.setTextColor(100, 100, 100);
    doc.text(`Generated: ${new Date().toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    })}`, margin, yPos);
    
    yPos += 5;
    doc.setDrawColor(200, 200, 200);
    doc.line(margin, yPos, pageWidth - margin, yPos);
    yPos += 10;
    
    // Project Information
    doc.setFontSize(14);
    doc.setTextColor(0, 0, 0);
    doc.text('Project Information', margin, yPos);
    yPos += 7;
    
    doc.setFontSize(10);
    doc.setTextColor(60, 60, 60);
    doc.text(`State: ${data.state}`, margin + 5, yPos);
    yPos += 6;
    doc.text(`Invoice Date: ${formatDate(data.invoice_date)}`, margin + 5, yPos);
    yPos += 6;
    doc.text(`Role: ${data.role.charAt(0).toUpperCase() + data.role.slice(1)}`, margin + 5, yPos);
    yPos += 10;
    
    // Preliminary Notice
    doc.setFontSize(14);
    doc.setTextColor(0, 0, 0);
    doc.text(data.preliminary_notice.name, margin, yPos);
    yPos += 7;
    
    const prelimColor = getUrgencyPDFColor(data.preliminary_notice.urgency);
    doc.setFillColor(prelimColor.r, prelimColor.g, prelimColor.b);
    doc.rect(margin, yPos - 5, 5, 5, 'F');
    
    doc.setFontSize(12);
    doc.setTextColor(0, 0, 0);
    doc.text(`Deadline: ${formatDate(data.preliminary_notice.deadline)}`, margin + 10, yPos);
    yPos += 6;
    
    doc.setFontSize(10);
    doc.setTextColor(prelimColor.r, prelimColor.g, prelimColor.b);
    doc.text(`${data.preliminary_notice.days_from_now} days from now`, margin + 10, yPos);
    yPos += 6;
    
    doc.setFontSize(9);
    doc.setTextColor(100, 100, 100);
    const prelimDesc = doc.splitTextToSize(data.preliminary_notice.description, pageWidth - margin * 2 - 10);
    doc.text(prelimDesc, margin + 10, yPos);
    yPos += prelimDesc.length * 5 + 5;
    
    // Lien Filing
    doc.setFontSize(14);
    doc.setTextColor(0, 0, 0);
    doc.text(data.lien_filing.name, margin, yPos);
    yPos += 7;
    
    const lienColor = getUrgencyPDFColor(data.lien_filing.urgency);
    doc.setFillColor(lienColor.r, lienColor.g, lienColor.b);
    doc.rect(margin, yPos - 5, 5, 5, 'F');
    
    doc.setFontSize(12);
    doc.setTextColor(0, 0, 0);
    doc.text(`Deadline: ${formatDate(data.lien_filing.deadline)}`, margin + 10, yPos);
    yPos += 6;
    
    doc.setFontSize(10);
    doc.setTextColor(lienColor.r, lienColor.g, lienColor.b);
    doc.text(`${data.lien_filing.days_from_now} days from now`, margin + 10, yPos);
    yPos += 6;
    
    doc.setFontSize(9);
    doc.setTextColor(100, 100, 100);
    const lienDesc = doc.splitTextToSize(data.lien_filing.description, pageWidth - margin * 2 - 10);
    doc.text(lienDesc, margin + 10, yPos);
    yPos += lienDesc.length * 5 + 8;
    
    // Serving Requirements
    doc.setFontSize(12);
    doc.setTextColor(0, 0, 0);
    doc.text('Must Serve:', margin, yPos);
    yPos += 7;
    
    doc.setFontSize(10);
    doc.setTextColor(60, 60, 60);
    data.serving_requirements.forEach(req => {
        doc.text(`• ${formatServing(req)}`, margin + 5, yPos);
        yPos += 5;
    });
    yPos += 5;
    
    // Critical Warnings
    if (yPos > 220) {
        doc.addPage();
        yPos = 20;
    }
    
    doc.setFontSize(12);
    doc.setTextColor(220, 38, 38);
    doc.text('⚠ Critical Warnings:', margin, yPos);
    yPos += 7;
    
    doc.setFontSize(9);
    doc.setTextColor(153, 27, 27);
    data.critical_warnings.forEach(warning => {
        const warningText = doc.splitTextToSize(warning, pageWidth - margin * 2 - 5);
        doc.text(warningText, margin + 5, yPos);
        yPos += warningText.length * 5 + 3;
    });
    yPos += 5;
    
    // Statute Citations
    if (yPos > 220) {
        doc.addPage();
        yPos = 20;
    }
    
    doc.setFontSize(12);
    doc.setTextColor(0, 0, 0);
    doc.text('Legal References:', margin, yPos);
    yPos += 7;
    
    doc.setFontSize(9);
    doc.setTextColor(100, 100, 100);
    data.statute_citations.forEach(citation => {
        const citationText = doc.splitTextToSize(citation, pageWidth - margin * 2 - 5);
        doc.text(citationText, margin + 5, yPos);
        yPos += citationText.length * 4 + 2;
    });
    yPos += 8;
    
    // Disclaimer
    if (yPos > 240) {
        doc.addPage();
        yPos = 20;
    }
    
    doc.setFillColor(254, 252, 232);
    doc.rect(margin - 5, yPos - 5, pageWidth - margin * 2 + 10, 30, 'F');
    
    doc.setFontSize(10);
    doc.setTextColor(120, 53, 15);
    doc.text('DISCLAIMER', margin, yPos);
    yPos += 6;
    
    doc.setFontSize(8);
    doc.setTextColor(113, 63, 18);
    const disclaimer = doc.splitTextToSize(
        'This is general information only, NOT legal advice. Always consult a licensed construction attorney before taking any legal action. Deadlines vary based on project specifics, and this tool cannot account for all variables. LienDeadline assumes no liability for missed deadlines or legal consequences.',
        pageWidth - margin * 2
    );
    doc.text(disclaimer, margin, yPos);
    
    // Footer
    const pageCount = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(150, 150, 150);
        doc.text(
            `Page ${i} of ${pageCount} | LienDeadline.com | Not Legal Advice`,
            pageWidth / 2,
            doc.internal.pageSize.getHeight() - 10,
            { align: 'center' }
        );
    }
    
    const filename = `Lien-Deadline-Report-${data.state_code}-${data.invoice_date}.pdf`;
    doc.save(filename);
}

function getUrgencyPDFColor(urgency) {
    switch(urgency) {
        case 'critical': return { r: 220, g: 38, b: 38 };
        case 'warning': return { r: 234, g: 179, b: 8 };
        default: return { r: 34, g: 197, b: 94 };
    }
}

function formatServing(requirement) {
    const map = {
        'property_owner': 'Property Owner',
        'original_contractor': 'Original Contractor',
        'direct_contractor': 'Direct Contractor',
        'construction_lender': 'Construction Lender'
    };
    return map[requirement] || requirement;
}

// ==========================================
// Zapier Integration Functions
// ==========================================

/**
 * Load Zapier webhook URLs dynamically
 */
async function loadZapierUrls() {
    const token = localStorage.getItem('session_token');
    if (!token) {
        console.warn('No session token found, using default URLs');
        setDefaultZapierUrls();
        return;
    }

    try {
        // Get base URL (current domain)
        const baseUrl = window.location.origin;
        
        // Construct webhook URLs
        const webhookUrl = `${baseUrl}/api/zapier/webhook/invoice`;
        const triggerUrl = `${baseUrl}/api/zapier/trigger/upcoming?limit=10`;

        // Update input fields (support both old and new IDs)
        const webhookInput = document.getElementById('webhook-url') || document.getElementById('zapier-webhook-url');
        const triggerInput = document.getElementById('trigger-url') || document.getElementById('zapier-trigger-url');

        if (webhookInput) {
            webhookInput.value = webhookUrl;
        }
        if (triggerInput) {
            triggerInput.value = triggerUrl;
        }

        console.log('✅ Zapier URLs loaded successfully');
    } catch (error) {
        console.error('❌ Error loading Zapier URLs:', error);
        setDefaultZapierUrls();
    }
}

/**
 * Set default Zapier URLs (fallback)
 */
function setDefaultZapierUrls() {
    const baseUrl = window.location.origin;
    // Support both old and new IDs for backwards compatibility
    const webhookInput = document.getElementById('webhook-url') || document.getElementById('zapier-webhook-url');
    const triggerInput = document.getElementById('trigger-url') || document.getElementById('zapier-trigger-url');

    if (webhookInput) {
        webhookInput.value = `${baseUrl}/api/zapier/webhook/invoice`;
    }
    if (triggerInput) {
        triggerInput.value = `${baseUrl}/api/zapier/trigger/upcoming?limit=10`;
    }
}

/**
 * Copy text to clipboard
 * @param {string} inputId - ID of the input element to copy from
 */
function copyToClipboard(inputId) {
    const input = document.getElementById(inputId);
    if (!input) {
        console.error(`Input element with ID '${inputId}' not found`);
        return;
    }

    // Select the text
    input.select();
    input.setSelectionRange(0, 99999); // For mobile devices

    try {
        // Copy to clipboard
        document.execCommand('copy');
        
        // Visual feedback
        const button = event.target.closest('button');
        if (button) {
            const originalText = button.textContent;
            button.textContent = '✓';
            button.classList.add('bg-green-100', 'text-green-700');
            button.classList.remove('bg-gray-100', 'text-gray-700');
            
            setTimeout(() => {
                button.textContent = originalText;
                button.classList.remove('bg-green-100', 'text-green-700');
                button.classList.add('bg-gray-100', 'text-gray-700');
            }, 2000);
        }

        console.log('✅ Copied to clipboard:', input.value);
    } catch (err) {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard. Please select and copy manually.');
    }
}

// Placeholder functions for other integrations (to prevent errors)
function connectQuickBooks() {
    // Redirect to Zapier integration page
    window.location.href = '/dashboard/zapier';
}

function connectSage() {
    alert('Sage integration coming soon!');
}

function connectProcore() {
    alert('Procore integration coming soon!');
}

/**
 * Check Zapier connection status (minimal check for /dashboard)
 */
async function checkZapierStatus() {
    const token = localStorage.getItem('session_token');
    if (!token) {
        return;
    }

    try {
        const response = await fetch('/api/zapier/token', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            const statusElement = document.getElementById('zapier-status');
            if (statusElement && data.has_token) {
                statusElement.textContent = 'Connected';
                statusElement.className = 'text-sm text-green-600';
            }
        }
    } catch (error) {
        // Silently fail - status check is optional
        console.log('Zapier status check skipped');
    }
}


