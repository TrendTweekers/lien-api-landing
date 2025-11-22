// API Tester functionality
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('api-form');
    const responseContainer = document.getElementById('response-container');
    const apiResponse = document.getElementById('api-response');
    const calculateButton = form.querySelector('button[type="submit"]');

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

        // Show loading state
        calculateButton.disabled = true;
        calculateButton.textContent = 'Calculating...';
        calculateButton.classList.add('loading');
        responseContainer.classList.add('hidden');
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

            // Make API call
            const response = await fetch('https://api.liendeadline.com/v1/calculate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(payload)
            });

            // Calculate response time
            const endTime = performance.now();
            const responseTime = Math.round(endTime - startTime);

            // Parse response
            const data = await response.json();

            // Check if API returned an error
            if (!response.ok || data.error) {
                // Display error message in red
                const errorMessage = data.error || data.message || 'An error occurred';
                apiResponse.textContent = JSON.stringify({
                    error: errorMessage,
                    message: data.message || errorMessage,
                    responseTime: responseTime + 'ms'
                }, null, 2);
                apiResponse.classList.add('error');
                apiResponse.classList.remove('success');
            } else {
                // Display successful response with response time
                const responseWithTime = {
                    ...data,
                    responseTime: responseTime + 'ms'
                };
                apiResponse.textContent = JSON.stringify(responseWithTime, null, 2);
                apiResponse.classList.add('success');
                apiResponse.classList.remove('error');
            }

            responseContainer.classList.remove('hidden');
            
            // Scroll to response
            responseContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        } catch (error) {
            // Handle network failures and other errors
            const endTime = performance.now();
            const responseTime = Math.round(endTime - startTime);
            
            apiResponse.textContent = JSON.stringify({
                error: 'Failed to fetch from API',
                message: error.message,
                details: 'Please check your internet connection and try again.',
                responseTime: responseTime + 'ms'
            }, null, 2);
            apiResponse.classList.add('error');
            apiResponse.classList.remove('success');
            responseContainer.classList.remove('hidden');
            responseContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } finally {
            // Reset button state
            calculateButton.disabled = false;
            calculateButton.textContent = 'Calculate';
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

