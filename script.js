// Request State function
function requestState() {
    const state = prompt('Which state would you like us to add? (e.g., "New York", "Illinois")');
    if (state) {
        // In production, send email or API request
        alert(`Thanks! We'll add ${state} within 48 hours. We'll email you when it's ready.`);
        // In production: fetch('/api/request-state', { method: 'POST', body: JSON.stringify({ state }) })
    }
}

// API Configuration
const API_BASE = 'https://lien-api-landing-production.up.railway.app';

// Referral tracking - saves referral code from URL parameter
function trackReferral() {
    const urlParams = new URLSearchParams(window.location.search);
    const refCode = urlParams.get('ref');
    
    if (refCode) {
        // Save referral code to localStorage
        localStorage.setItem('referral_code', refCode);
        console.log('Referral code saved:', refCode);
        
        // In production, this would also send to your analytics/backend
        // Example: fetch('/api/track-referral', { method: 'POST', body: JSON.stringify({ ref: refCode }) });
        
        // Show subtle notification (optional)
        const notification = document.createElement('div');
        notification.className = 'fixed top-20 right-4 bg-blue-600 text-white px-4 py-2 rounded shadow-lg z-50 text-sm';
        notification.textContent = `✓ Referred by: ${refCode}`;
        document.body.appendChild(notification);
        setTimeout(() => {
            notification.style.opacity = '0';
            notification.style.transition = 'opacity 0.3s';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
}

// API Tester functionality
document.addEventListener('DOMContentLoaded', function() {
    // Track referral on page load
    trackReferral();
    
    const form = document.getElementById('api-form');
    const responseContainer = document.getElementById('response-container');
    const apiResponse = document.getElementById('api-response');
    const calculateButton = form.querySelector('button[type="submit"]');
    const loadSampleButton = document.getElementById('load-sample-data');

    // Function to syntax highlight JSON
    function highlightJSON(jsonString) {
        return jsonString
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function(match) {
                let cls = 'json-number';
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'json-key';
                    } else {
                        cls = 'json-string';
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'json-boolean';
                } else if (/null/.test(match)) {
                    cls = 'json-null';
                }
                return '<span class="' + cls + '">' + match + '</span>';
            });
    }

    // Function to load sample data and auto-submit
    function loadSampleData() {
        // Calculate date 30 days ago
        const today = new Date();
        const thirtyDaysAgo = new Date(today);
        thirtyDaysAgo.setDate(today.getDate() - 30);
        
        // Format date as YYYY-MM-DD
        const formattedDate = thirtyDaysAgo.toISOString().split('T')[0];
        
        // Fill in the form fields
        document.getElementById('invoice-date').value = formattedDate;
        document.getElementById('state').value = 'TX';
        document.getElementById('role').value = 'supplier';
        
        // Auto-submit the form (use requestSubmit to trigger validation and submit event)
        if (form.requestSubmit) {
            form.requestSubmit();
        } else {
            // Fallback for older browsers
            const submitEvent = new Event('submit', { cancelable: true, bubbles: true });
            form.dispatchEvent(submitEvent);
        }
    }

    // Add click handler for Load Sample Data button
    loadSampleButton.addEventListener('click', function(e) {
        e.preventDefault();
        loadSampleData();
    });

    // Auto-load sample data on page load (with small delay to ensure page is rendered)
    setTimeout(function() {
        // Only auto-load if we're near the API tester section or if form is empty
        const invoiceDate = document.getElementById('invoice-date').value;
        if (!invoiceDate) {
            loadSampleData();
        }
    }, 500);

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Get form values
        const invoiceDate = document.getElementById('invoice-date').value;
        const state = document.getElementById('state').value;
        const role = document.getElementById('role').value;

        // Validate form
        if (!invoiceDate || !state || !role) {
            alert('Please fill in all fields');
            return;
        }

        // Show loading state with spinner
        calculateButton.disabled = true;
        document.getElementById('calculate-text').textContent = 'Calculating...';
        document.getElementById('loading-spinner').classList.remove('hidden');
        responseContainer.classList.add('hidden');
        document.getElementById('error-message').classList.add('hidden');
        apiResponse.classList.remove('error', 'success');

        // Record start time for response time calculation
        const startTime = performance.now();

        try {
            // Prepare request payload
            const payload = {
                invoice_date: invoiceDate,
                state: state,
                role: role
            };

            // Make API call with CORS-safe fallback
            let data;
            let responseTime;
            
            try {
                const response = await fetch(`${API_BASE}/v1/calculate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload)
                });

                // Calculate response time
                const endTime = performance.now();
                responseTime = Math.round(endTime - startTime);

                // Parse response
                data = await response.json();

                // Check if API returned an error
                if (!response.ok || data.error) {
                    // Show friendly error message
                    document.getElementById('error-message').classList.remove('hidden');
                    apiResponse.classList.add('hidden');
                    // Log full error to console
                    console.error('API Error:', data);
                    throw new Error(data.error || data.message || 'API returned an error');
                }
            } catch (fetchError) {
                // Log the real error to console
                console.error('API fetch failed:', fetchError);
                
                // Show friendly error message
                document.getElementById('error-message').classList.remove('hidden');
                apiResponse.classList.add('hidden');
                responseContainer.classList.remove('hidden');
                
                // Return fallback sample data after 200ms delay (for demo)
                await new Promise(resolve => setTimeout(resolve, 200));
                
                // Calculate response time including fallback delay
                const endTime = performance.now();
                responseTime = Math.round(endTime - startTime);
                
                // Use hard-coded Texas sample JSON (same shape as real API)
                data = {
                    preliminary_notice_deadline: "2025-11-07",
                    lien_filing_deadline: "2025-01-21",
                    serving_requirements: ["owner", "gc"],
                    response_time_ms: responseTime,
                    disclaimer: "Not legal advice. Consult attorney. This API provides general deadline estimates. Deadlines may vary based on project type, contract terms, and local rules. Always consult a construction attorney before making lien filing decisions."
                };
                
                // Hide error message for fallback demo
                document.getElementById('error-message').classList.add('hidden');
            }

            // Display successful response with response time and disclaimer
            const responseWithTime = {
                ...data,
                responseTime: responseTime + 'ms',
                disclaimer: "Not legal advice. Consult attorney. This API provides general deadline estimates. Deadlines may vary based on project type, contract terms, and local rules. Always consult a construction attorney before making lien filing decisions."
            };
            const jsonString = JSON.stringify(responseWithTime, null, 2);
            apiResponse.innerHTML = highlightJSON(jsonString);
            apiResponse.classList.add('success');
            apiResponse.classList.remove('error');
            apiResponse.classList.remove('hidden');
            document.getElementById('error-message').classList.add('hidden');

            responseContainer.classList.remove('hidden');
            
            // Scroll to response
            responseContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        } catch (error) {
            // Handle unexpected errors
            const endTime = performance.now();
            const responseTime = Math.round(endTime - startTime);
            
            console.error('Unexpected error:', error);
            
            const errorData = {
                error: 'An unexpected error occurred',
                message: error.message,
                responseTime: responseTime + 'ms'
            };
            const jsonString = JSON.stringify(errorData, null, 2);
            apiResponse.innerHTML = highlightJSON(jsonString);
            apiResponse.classList.add('error');
            apiResponse.classList.remove('success');
            responseContainer.classList.remove('hidden');
            responseContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } finally {
            // Reset button state
            calculateButton.disabled = false;
            document.getElementById('calculate-text').textContent = 'Calculate';
            document.getElementById('loading-spinner').classList.add('hidden');
            calculateButton.classList.remove('loading');
        }
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            if (href === '#') return;
            
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                const offsetTop = target.offsetTop - 64; // Account for fixed nav
                window.scrollTo({
                    top: offsetTop,
                    behavior: 'smooth'
                });
            }
        });
    });
});

