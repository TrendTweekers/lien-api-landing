// calculator.js

// Server-side tracking - no more localStorage counting!
// Counter is now managed server-side via /api/v1/track-calculation

let userEmail = localStorage.getItem('userEmail') || null; // Still store email locally for display

// Check if calculator is in dashboard mode
function isDashboardMode() {
    const calculatorSection = document.getElementById('calculator');
    return calculatorSection && calculatorSection.hasAttribute('data-dashboard');
}

// Update remaining calculations counter display (fetches from server)
async function updateRemainingCounter() {
    // Skip counter update in dashboard mode
    if (isDashboardMode()) {
        return;
    }
    
    try {
        // Fetch current count from server
        const response = await fetch('/api/v1/track-calculation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.status === 'allowed' || data.status === 'limit_reached') {
            const count = data.calculation_count || 0;
            const remaining = data.remaining_calculations || 0;
            const emailProvided = data.email_provided || false;
            const limit = emailProvided ? 6 : 3;
            
            // Update counter in form area (always visible)
            const remainingCalcsTop = document.getElementById('remainingCalcsTop');
            if (remainingCalcsTop) {
                if (remaining > 0) {
                    remainingCalcsTop.textContent = `${remaining} of ${limit} free calculations remaining`;
                } else {
                    remainingCalcsTop.textContent = `0 of ${limit} free calculations remaining`;
                }
            }
            
            // Update counter in results area (if visible)
            const remainingCalcsEl = document.getElementById('remainingCalcs');
            if (remainingCalcsEl) {
                if (remaining > 0) {
                    remainingCalcsEl.textContent = `${remaining} of ${limit} free calculations remaining`;
                    remainingCalcsEl.parentElement.classList.remove('hidden');
                } else {
                    remainingCalcsEl.textContent = `0 of ${limit} free calculations remaining`;
                }
            }
        }
    } catch (error) {
        console.error('Error updating counter:', error);
        // Fallback: show default message
        const remainingCalcsTop = document.getElementById('remainingCalcsTop');
        if (remainingCalcsTop) {
            remainingCalcsTop.textContent = 'Free calculations available';
        }
    }
}

// Initialize counter on page load
window.addEventListener('DOMContentLoaded', function() {
    updateRemainingCounter();
});

// Also run if DOM already loaded
if (document.readyState !== 'loading') {
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

// Helper function to parse invoice date (handles both YYYY-MM-DD and MM/DD/YYYY)
function parseInvoiceDate(raw) {
    if (!raw) return null;
    
    // Native <input type="date"> returns YYYY-MM-DD
    if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
        const [y, m, d] = raw.split("-").map(Number);
        return new Date(y, m - 1, d);
    }
    
    // Fallback: MM/DD/YYYY
    const mdy = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (mdy) {
        const [, mm, dd, yyyy] = mdy.map(Number);
        return new Date(yyyy, mm - 1, dd);
    }
    
    // Last resort
    const dt = new Date(raw);
    return isNaN(dt.getTime()) ? null : dt;
}

// Form submission - NOW WITH SERVER-SIDE TRACKING
const calculatorForm = document.getElementById('calculatorForm');
if (calculatorForm) {
    calculatorForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Get form values
        const rawDate = document.getElementById('invoice_date')?.value?.trim() || 
                       document.getElementById('invoiceDatePicker')?.value?.trim() || 
                       document.getElementById('invoiceDateDisplay')?.value?.trim();
        const invoiceDateObj = parseInvoiceDate(rawDate);
        
        if (!invoiceDateObj) {
            alert("Please select a valid date.");
            return;
        }
        
        // Use YYYY-MM-DD format (native date input already provides this)
        const invoiceDate = rawDate.match(/^\d{4}-\d{2}-\d{2}$/) ? rawDate : 
                           (invoiceDateObj.getFullYear() + '-' + 
                            String(invoiceDateObj.getMonth() + 1).padStart(2, '0') + '-' + 
                            String(invoiceDateObj.getDate()).padStart(2, '0'));
        
        const state = document.getElementById('state').value;
        const role = document.getElementById('role') ? document.getElementById('role').value : 'supplier';
        
        // Show loading state
        const submitButton = e.target.querySelector('button[type="submit"]') || document.getElementById('calculateBtn');
        const originalText = submitButton.innerHTML || submitButton.textContent;
        submitButton.disabled = true;
        submitButton.innerHTML = 'Calculating...';
        
        try {
            // Get session token if in dashboard mode
            const sessionToken = localStorage.getItem('session_token');
            const headers = {
                'Content-Type': 'application/json'
            };
            if (sessionToken && isDashboardMode()) {
                headers['Authorization'] = `Bearer ${sessionToken}`;
            }
            
            // STEP 1: Check limits server-side BEFORE calculation (skip in dashboard mode)
            // Admin/dev user bypass - check BEFORE API call
            const DEV_EMAIL = "kartaginy1@gmail.com";
            const userEmail = localStorage.getItem('userEmail') || '';
            const isDevUser = userEmail && userEmail.toLowerCase() === DEV_EMAIL.toLowerCase();
            
            let trackData = { status: 'allowed', quota: { unlimited: false } };
            if (!isDashboardMode() && !isDevUser) {
                // Only check limits if not admin user
                const trackResponse = await fetch('/api/v1/track-calculation', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        state: state,
                        notice_date: invoiceDate,
                        email: userEmail || null  // Send email so backend can check admin status
                    })
                });
                trackData = await trackResponse.json();
                
                // Handle limit reached
                if (trackData.status === 'limit_reached') {
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalText;
                    
                    if (trackData.limit_type === 'before_email') {
                        const emailModal = document.getElementById('emailModal');
                        if (emailModal) emailModal.classList.remove('hidden');
                        return;
                    } else if (trackData.limit_type === 'upgrade_required') {
                        const upgradeModal = document.getElementById('upgradeModal');
                        if (upgradeModal) upgradeModal.classList.remove('hidden');
                        return;
                    }
                }
            } else if (isDevUser) {
                // Admin user - skip limit check, allow calculation
                console.log('✅ Admin user detected - skipping limit checks');
                trackData = { status: 'allowed', quota: { unlimited: true } };
            }
            
            // STEP 2: Proceed with calculation
            const response = await fetch('/api/v1/calculate-deadline', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    invoice_date: invoiceDate,
                    state: state,
                    role: role
                })
            });
        
        const trackData = await trackResponse.json();
        
        // Handle limit reached
        if (trackData.status === 'limit_reached') {
            submitButton.textContent = originalText;
            submitButton.disabled = false;
            
            if (trackData.limit_type === 'before_email') {
                // Show email gate modal
                document.getElementById('emailModal').classList.remove('hidden');
                return;
            } else if (trackData.limit_type === 'upgrade_required') {
                // Show upgrade modal
                document.getElementById('upgradeModal').classList.remove('hidden');
                return;
            }
        }
        
        // STEP 2: If allowed, proceed with calculation
        submitButton.textContent = 'Calculating...';
        
            
            const data = await response.json();
            
            // Handle API errors (including 403 from server-side limit check)
            if (response.status === 403 && !isDashboardMode()) {
                // Server-side limit enforcement (backup check)
                if (data.detail && data.detail.includes('email')) {
                    const emailModal = document.getElementById('emailModal');
                    if (emailModal) emailModal.classList.remove('hidden');
                } else {
                    const upgradeModal = document.getElementById('upgradeModal');
                    if (upgradeModal) upgradeModal.classList.remove('hidden');
                }
                submitButton.disabled = false;
                submitButton.innerHTML = originalText;
                return;
            }
            
            if (data.error || !response.ok) {
                alert(`Error: ${data.error || data.detail || 'Unknown error'}\n${data.message || ''}`);
                submitButton.disabled = false;
                submitButton.innerHTML = originalText;
                return;
            }
            
            // STEP 3: Update counter display (server-side count) - skip in dashboard mode
            if (!isDashboardMode()) {
                await updateRemainingCounter();
                
                // STEP 4: Check if email gate should appear (based on server response)
                if (trackData.email_required && !trackData.email_provided) {
                    // Store result to show after email is entered
                    window.pendingCalculationResult = data;
                    const emailModal = document.getElementById('emailModal');
                    if (emailModal) emailModal.classList.remove('hidden');
                    submitButton.disabled = false;
                    submitButton.innerHTML = originalText;
                    return;
                }
            }
            
            // Display results
            if (typeof displayResults === 'function') {
                displayResults(data);
            } else if (typeof window.displayResults === 'function') {
                window.displayResults(data);
            }
            
            // Track calculator submission
            if (typeof gtag !== 'undefined') {
                gtag('event', 'calculator_submit', {
                    'event_category': 'Calculator',
                    'event_label': state,
                    'value': 1
                });
            }
            
            // Scroll to results (if not in dashboard mode)
            if (!isDashboardMode()) {
                const resultsEl = document.getElementById('results') || document.getElementById('calculatorResults');
                if (resultsEl) {
                    resultsEl.scrollIntoView({ behavior: 'smooth' });
                }
            }
            
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to calculate deadlines. Please try again.');
        } finally {
            // Reset button
            submitButton.disabled = false;
            submitButton.innerHTML = originalText;
        }
    });
}

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
    
    // Store email locally (for display purposes)
    userEmail = email;
    localStorage.setItem('userEmail', email);
    
    // Send email to server (links to tracking record)
    try {
        const response = await fetch('/api/v1/capture-email', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                email: email,
                timestamp: new Date().toISOString()
            })
        });
        
        const data = await response.json();
        
        // Handle enhanced error responses
        if (!response.ok) {
            const errorCode = data.error_code || 'UNKNOWN_ERROR';
            let errorMessage = data.message || 'Failed to save email';
            
            // Provide user-friendly error messages
            switch(errorCode) {
                case 'DISPOSABLE_EMAIL':
                    errorMessage = '❌ Temporary email addresses are not allowed. Please use a permanent email address.';
                    break;
                case 'DUPLICATE_EMAIL':
                    errorMessage = '❌ This email is already registered from a different location. If this is your email, please contact support.';
                    break;
                case 'INVALID_FORMAT':
                    errorMessage = '❌ Invalid email format. Please check your email address.';
                    break;
                case 'RATE_LIMIT':
                    errorMessage = '⏱️ Too many requests. Please wait a moment before trying again.';
                    break;
                default:
                    errorMessage = data.help_text || errorMessage;
            }
            
            alert(errorMessage);
            return;
        }
        
        if (!response.ok || data.status === 'error') {
            alert(`Error: ${data.message || 'Failed to save email'}`);
            return;
        }
        
        // Track lead generation
        if (typeof gtag !== 'undefined') {
            gtag('event', 'generate_lead', {
                'event_category': 'Lead Generation',
                'event_label': 'Email Capture',
                'value': 1
            });
        }
    } catch (error) {
        console.error('Error tracking email:', error);
        alert('Email saved locally, but server sync failed. Please try again.');
        return;
    }
    
    // Hide modal
    document.getElementById('emailModal').classList.add('hidden');
    
    // Update counter display (now shows 6 total instead of 3)
    await updateRemainingCounter();
    
    // Show success message
    alert('Email saved! You now have 3 more free calculations (6 total).');
    
    // Display the pending calculation result (the one that triggered the email gate)
    if (window.pendingCalculationResult) {
        displayResults(window.pendingCalculationResult);
        document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
        window.pendingCalculationResult = null; // Clear it
    }
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
const downloadPDFBtn = document.getElementById('downloadPDF');
if (downloadPDFBtn) {
    downloadPDFBtn.addEventListener('click', () => {
        if (!window.currentCalculation) {
            alert('Please calculate deadlines first');
            return;
        }
        
        // Track PDF download
        if (typeof gtag !== 'undefined') {
            gtag('event', 'pdf_download', {
                'event_category': 'PDF',
                'event_label': window.currentCalculation.state || 'Unknown',
                'value': 1
            });
        }
        
        generatePDF(window.currentCalculation);
    });
}

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

// One-click calendar setup
const picker = document.getElementById('invoiceDatePicker');
const display = document.getElementById('invoiceDateDisplay');

/* native → US mask */
if (picker && display) {
    picker.addEventListener('change', e => {
        const [y, m, d] = e.target.value.split('-');
        display.value = `${m}/${d}/${y}`;
    });
}

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


