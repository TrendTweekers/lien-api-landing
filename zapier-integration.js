// Zapier Integration JavaScript Functions

/**
 * Load Zapier webhook URLs dynamically
 * Fetches user-specific URLs from the backend or constructs them from base URL
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

        // Update input fields
        const webhookInput = document.getElementById('zapier-webhook-url');
        const triggerInput = document.getElementById('zapier-trigger-url');

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
    const webhookInput = document.getElementById('zapier-webhook-url');
    const triggerInput = document.getElementById('zapier-trigger-url');

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
            button.textContent = '✓ Copied!';
            button.classList.add('bg-green-100', 'text-green-700');
            button.classList.remove('bg-gray-100', 'text-gray-700');
            
            setTimeout(() => {
                button.textContent = originalText;
                button.classList.remove('bg-green-100', 'text-green-700');
                button.classList.add('bg-gray-100', 'text-gray-700');
            }, 2000);
        }

        // Show notification if available
        if (typeof showNotification === 'function') {
            showNotification('URL copied to clipboard!', 'success');
        } else {
            console.log('✅ Copied to clipboard:', input.value);
        }
    } catch (err) {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard. Please select and copy manually.');
    }
}

/**
 * Initialize Zapier integration on page load
 */
function initZapierIntegration() {
    // Load URLs when page loads
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadZapierUrls);
    } else {
        loadZapierUrls();
    }
}

// Auto-initialize when script loads
initZapierIntegration();

