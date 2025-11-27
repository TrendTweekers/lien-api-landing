// calculator.js

// Usage tracking - check localStorage for calcCount and userEmail
let calcCount = parseInt(localStorage.getItem('calcCount') || '0');
let userEmail = localStorage.getItem('userEmail') || null;

// Update remaining calculations counter
function updateRemainingCounter() {
    const remainingCalcsEl = document.getElementById('remainingCalcs');
    if (!remainingCalcsEl) return;
    
    if (calcCount >= 10) {
        remainingCalcsEl.textContent = '';
        remainingCalcsEl.parentElement.classList.add('hidden');
    } else if (calcCount >= 3 && !userEmail) {
        const remaining = 3 - calcCount;
        remainingCalcsEl.textContent = `${remaining} of 3 free calculations remaining`;
    } else if (userEmail) {
        const remaining = 10 - calcCount;
        remainingCalcsEl.textContent = `${remaining} of 10 free calculations remaining`;
    } else {
        const remaining = 3 - calcCount;
        remainingCalcsEl.textContent = `${remaining} of 3 free calculations remaining`;
    }
}

// Initialize counter on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', updateRemainingCounter);
} else {
    updateRemainingCounter();
}

// Handle referral codes for Stripe checkout
(function() {
    // Get referral code from URL
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = urlParams.get('ref') || '';
    
    // Update all Stripe upgrade links to include referral code
    function updateStripeLinks() {
        const stripeLinks = document.querySelectorAll('a[href*="buy.stripe.com"]');
        stripeLinks.forEach(link => {
            const originalHref = link.getAttribute('href');
            if (refCode && !originalHref.includes('client_reference_id')) {
                // Stripe payment links use metadata, but we can pass via URL params
                // Note: Stripe checkout sessions need metadata set server-side
                // For now, we'll store the ref in localStorage and webhook will check it
                localStorage.setItem('referral_code', refCode);
            }
        });
    }
    
    // Run on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateStripeLinks);
    } else {
        updateStripeLinks();
    }
})();

// API Base URL - use relative URL since API is on same domain
const API_BASE = '';

// Form submission
document.getElementById('calculatorForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Check usage limits
    if (calcCount >= 10) {
        document.getElementById('upgradeModal').classList.remove('hidden');
        return;
    }
    
    if (calcCount >= 3 && !userEmail) {
        document.getElementById('emailModal').classList.remove('hidden');
        return;
    }
    
    // Get form values
    const invoiceDate = document.getElementById('invoiceDate').value;
    const state = document.getElementById('state').value;
    const role = document.getElementById('role').value;
    
    // Show loading state
    const submitButton = e.target.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;
    submitButton.textContent = 'Calculating...';
    submitButton.disabled = true;
    
    try {
        // Call API with POST and JSON body
        const response = await fetch('/v1/calculate', {
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
            alert(`Error: ${data.error}\n${data.message || ''}`);
            return;
        }
        
        // Increment calculation count
        calcCount++;
        localStorage.setItem('calcCount', calcCount.toString());
        updateRemainingCounter();
        
        // Display results
        displayResults(data);
        
        // Scroll to results
        document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to calculate deadlines. Please try again.');
    } finally {
        // Reset button
        submitButton.textContent = originalText;
        submitButton.disabled = false;
    }
});

// Email submission handler (wait for DOM)
function initEmailHandler() {
    const submitEmailBtn = document.getElementById('submitEmail');
    if (!submitEmailBtn) return;
    
    submitEmailBtn.addEventListener('click', async () => {
    const emailInput = document.getElementById('emailInput');
    const email = emailInput.value.trim();
    
    if (!email || !email.includes('@')) {
        alert('Please enter a valid email address');
        return;
    }
    
    // Store email
    userEmail = email;
    localStorage.setItem('userEmail', email);
    
    // Track email submission
    try {
        // Get IP address (simplified - in production use a proper IP service)
        const response = await fetch('/track-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                timestamp: new Date().toISOString()
            })
        });
        
        if (!response.ok) {
            console.error('Failed to track email');
        }
    } catch (error) {
        console.error('Error tracking email:', error);
    }
    
    // Hide modal and allow calculation
    document.getElementById('emailModal').classList.add('hidden');
    updateRemainingCounter();
    
    // Trigger form submission again
    document.getElementById('calculatorForm').dispatchEvent(new Event('submit'));
    });
}

// Initialize email handler on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEmailHandler);
} else {
    initEmailHandler();
}

function displayResults(data) {
    // Store results for email functionality
    latestResults = data;
    
    // Show results section
    document.getElementById('results').classList.remove('hidden');
    
    // Show/hide upgrade prompt based on login status
    const userEmail = localStorage.getItem('userEmail');
    const upgradePrompt = document.getElementById('upgradePrompt');
    if (userEmail) {
        // User is logged in, hide upgrade prompt
        if (upgradePrompt) upgradePrompt.style.display = 'none';
    } else {
        // User is not logged in, show upgrade prompt
        if (upgradePrompt) upgradePrompt.style.display = 'block';
    }
    
    // Always show state expansion prompt (everyone wants more states)
    document.getElementById('stateExpansionPrompt').classList.remove('hidden');
    
    // Preliminary Notice Card
    const prelimCard = document.getElementById('prelimCard');
    const prelimUrgency = data.preliminary_notice.urgency;
    prelimCard.className = `bg-white shadow-lg rounded-lg p-6 border-l-4 ${getUrgencyColor(prelimUrgency)}`;
    
    document.getElementById('prelimTitle').textContent = data.preliminary_notice.name;
    document.getElementById('prelimDate').textContent = formatDate(data.preliminary_notice.deadline);
    document.getElementById('prelimDays').textContent = `${data.preliminary_notice.days_from_now} days`;
    document.getElementById('prelimDays').className = `text-2xl font-bold ${getUrgencyTextColor(prelimUrgency)}`;
    document.getElementById('prelimDescription').textContent = data.preliminary_notice.description;
    
    // Lien Filing Card
    const lienCard = document.getElementById('lienCard');
    const lienUrgency = data.lien_filing.urgency;
    lienCard.className = `bg-white shadow-lg rounded-lg p-6 border-l-4 ${getUrgencyColor(lienUrgency)}`;
    
    document.getElementById('lienTitle').textContent = data.lien_filing.name;
    document.getElementById('lienDate').textContent = formatDate(data.lien_filing.deadline);
    document.getElementById('lienDays').textContent = `${data.lien_filing.days_from_now} days`;
    document.getElementById('lienDays').className = `text-2xl font-bold ${getUrgencyTextColor(lienUrgency)}`;
    document.getElementById('lienDescription').textContent = data.lien_filing.description;
    
    // Serving Requirements
    const servingList = document.getElementById('servingList');
    servingList.innerHTML = '';
    data.serving_requirements.forEach(req => {
        const li = document.createElement('li');
        li.className = 'flex items-center text-gray-700';
        li.innerHTML = `
            <svg class="h-5 w-5 text-green-500 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
            </svg>
            ${formatServing(req)}
        `;
        servingList.appendChild(li);
    });
    
    // Critical Warnings
    const warningsList = document.getElementById('warningsList');
    warningsList.innerHTML = '';
    if (data.critical_warnings && data.critical_warnings.length > 0) {
        data.critical_warnings.forEach(warning => {
            const li = document.createElement('li');
            li.className = 'text-red-700 text-sm';
            li.textContent = warning;
            warningsList.appendChild(li);
        });
    } else {
        document.getElementById('warningsSection').classList.add('hidden');
    }
    
    // Statute Citations
    const citationsList = document.getElementById('citationsList');
    citationsList.innerHTML = '';
    data.statute_citations.forEach(citation => {
        const li = document.createElement('li');
        li.textContent = citation;
        citationsList.appendChild(li);
    });
    
    // Store data for PDF/Email
    window.currentCalculation = data;
}

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
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    });
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

// PDF Download
document.getElementById('downloadPDF').addEventListener('click', () => {
    if (!window.currentCalculation) {
        alert('Please calculate deadlines first');
        return;
    }
    
    generatePDF(window.currentCalculation);
});

// Store latest calculation results for email
let latestResults = null;

// Email Report functionality removed - button removed from UI
// Email functionality can be added back later if needed
/*
document.getElementById('emailReport').addEventListener('click', async () => {
    if (!latestResults) {
        alert('Please calculate deadlines first!');
        return;
    }
    
    const userEmail = prompt("Enter your email address:");
    if (!userEmail) return;
    
    // Basic email validation
    if (!userEmail.includes('@') || !userEmail.includes('.')) {
        alert('Please enter a valid email address');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/v1/send-email`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                to_email: userEmail,
                results: {
                    state: document.getElementById('state').value,
                    prelimDeadline: document.getElementById('prelimDate').textContent,
                    lienDeadline: document.getElementById('lienDate').textContent
                }
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            alert(`✅ Report emailed to ${userEmail}`);
        } else {
            alert(`❌ Failed to send email: ${data.detail || data.message || 'Unknown error'}\n\nTry downloading PDF instead.`);
        }
    } catch (error) {
        console.error('Email error:', error);
        alert('❌ Email failed. Please download PDF instead.');
    }
});
*/

// Set today as default invoice date
document.getElementById('invoiceDate').valueAsDate = new Date();

// Hide upgrade prompt if user is logged in (on page load)
document.addEventListener('DOMContentLoaded', function() {
    if (localStorage.getItem('userEmail')) {
        const prompt = document.getElementById('upgradePrompt');
        if (prompt) prompt.style.display = 'none';
    }
});

// State expansion email capture
document.getElementById('notifyMeBtn').addEventListener('click', function() {
    const emailInput = document.getElementById('stateEmailInput');
    const email = emailInput.value.trim();
    const successMessage = document.getElementById('stateEmailSuccess');
    
    // Basic email validation
    if (!email || !email.includes('@')) {
        alert('Please enter a valid email address');
        return;
    }
    
    // Store email in localStorage (for MVP - later send to backend)
    let stateWaitlist = JSON.parse(localStorage.getItem('stateWaitlist') || '[]');
    if (!stateWaitlist.includes(email)) {
        stateWaitlist.push(email);
        localStorage.setItem('stateWaitlist', JSON.stringify(stateWaitlist));
    }
    
    // Show success message
    successMessage.classList.remove('hidden');
    emailInput.value = '';
    emailInput.disabled = true;
    document.getElementById('notifyMeBtn').disabled = true;
    document.getElementById('notifyMeBtn').textContent = '✓ Added!';
    
    // In production, send to backend API:
    // fetch('/api/waitlist', { method: 'POST', body: JSON.stringify({ email, states: ['NY', 'PA', 'IL', 'GA', 'NC', 'WA', 'OH', 'AZ', 'CO', 'VA'] }) })
});

function generatePDF(data) {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();
    
    // Page dimensions
    const pageWidth = doc.internal.pageSize.getWidth();
    const margin = 20;
    let yPos = 20;
    
    // Header
    doc.setFontSize(24);
    doc.setTextColor(37, 99, 235); // Blue color
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
    
    // Line separator
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
    
    // Add colored box for urgency
    const prelimColor = getUrgencyPDFColor(data.preliminary_notice.urgency);
    doc.setFillColor(prelimColor.r, prelimColor.g, prelimColor.b);
    doc.rect(margin, yPos - 5, 5, 5, 'F');
    
    doc.setFontSize(12);
    doc.setTextColor(0, 0, 0);
    doc.text(`Deadline: ${formatDate(data.preliminary_notice.deadline)}`, margin + 10, yPos);
    yPos += 6;
    
    doc.setFontSize(10);
    doc.setTextColor(getUrgencyPDFColor(data.preliminary_notice.urgency).r, 
                     getUrgencyPDFColor(data.preliminary_notice.urgency).g, 
                     getUrgencyPDFColor(data.preliminary_notice.urgency).b);
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
    
    // Add colored box for urgency
    const lienColor = getUrgencyPDFColor(data.lien_filing.urgency);
    doc.setFillColor(lienColor.r, lienColor.g, lienColor.b);
    doc.rect(margin, yPos - 5, 5, 5, 'F');
    
    doc.setFontSize(12);
    doc.setTextColor(0, 0, 0);
    doc.text(`Deadline: ${formatDate(data.lien_filing.deadline)}`, margin + 10, yPos);
    yPos += 6;
    
    doc.setFontSize(10);
    doc.setTextColor(getUrgencyPDFColor(data.lien_filing.urgency).r, 
                     getUrgencyPDFColor(data.lien_filing.urgency).g, 
                     getUrgencyPDFColor(data.lien_filing.urgency).b);
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
    doc.setTextColor(220, 38, 38); // Red color
    doc.text('⚠ Critical Warnings:', margin, yPos);
    yPos += 7;
    
    doc.setFontSize(9);
    doc.setTextColor(153, 27, 27); // Dark red
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
    
    doc.setFillColor(254, 252, 232); // Light yellow background
    doc.rect(margin - 5, yPos - 5, pageWidth - margin * 2 + 10, 30, 'F');
    
    doc.setFontSize(10);
    doc.setTextColor(120, 53, 15); // Dark yellow/brown
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
    
    // Save PDF
    const filename = `Lien-Deadline-Report-${data.state_code}-${data.invoice_date}.pdf`;
    doc.save(filename);
}

function getUrgencyPDFColor(urgency) {
    switch(urgency) {
        case 'critical': return { r: 220, g: 38, b: 38 }; // Red
        case 'warning': return { r: 234, g: 179, b: 8 }; // Yellow
        default: return { r: 34, g: 197, b: 94 }; // Green
    }
}

