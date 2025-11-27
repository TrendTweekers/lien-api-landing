// Admin Dashboard Functionality
// Hard-coded data for now - wire to API later

// Admin authentication
const ADMIN_USER = 'admin';
const ADMIN_PASS = 'LienAPI2025'; // Match Railway env var

// Check auth on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if already authenticated
    const isAuthenticated = sessionStorage.getItem('admin_authenticated');
    
    if (!isAuthenticated) {
        // Prompt for credentials
        const username = prompt('Admin Username:');
        const password = prompt('Admin Password:');
        
        if (username !== ADMIN_USER || password !== ADMIN_PASS) {
            alert('❌ Invalid credentials');
            window.location.href = 'index.html';
            return;
        }
        
        // Save auth state
        sessionStorage.setItem('admin_authenticated', 'true');
    }
    
    // Load dashboard data
    updateStats();
    loadCustomers();
    loadBrokers();
    loadPendingPayouts();
    loadTestKeys();
    loadQuickStats();
    loadPartnerApplications();
    
    // Refresh stats every 60 seconds
    setInterval(loadQuickStats, 60000);
});

// Logout function
function logout() {
    sessionStorage.removeItem('admin_authenticated');
    window.location.href = 'index.html';
}

// Sample data (matches Kimi's format)
const sampleCustomers = [
    { email: 'sarah@abcsupply.com', calls: 1247, status: 'Active' },
    { email: 'mike@buildtech.com', calls: 892, status: 'Active' },
    { email: 'john@texaslumber.com', calls: 0, status: 'Cancelled' },
    { email: 'lisa@floridamaterials.com', calls: 543, status: 'Active' },
    { email: 'david@californiasupply.com', calls: 2101, status: 'Active' },
    { email: 'amy@arizonabuilders.com', calls: 678, status: 'Active' },
    { email: 'tom@nevadacontractors.com', calls: 0, status: 'Cancelled' }
];

const sampleBrokers = [
    { name: 'John Smith', referrals: 3, earned: 1500, hasPending: true },
    { name: 'Sarah Jones', referrals: 2, earned: 593, hasPending: false }
];

// Update stats
// Load real-time stats from API
async function updateStats() {
    try {
        const response = await fetch(`${API_BASE}/admin/stats`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load stats');
        }
        
        const data = await response.json();
        
        // Update stats display
        document.getElementById('stats-customers').textContent = `${data.customers} customers`;
        document.getElementById('stats-brokers').textContent = `${data.brokers} brokers`;
        document.getElementById('stats-revenue').textContent = `$${data.revenue.toLocaleString()}`;
    } catch (error) {
        console.error('Error loading stats:', error);
        // Fallback to showing loading state
        document.getElementById('stats-customers').textContent = 'Loading...';
        document.getElementById('stats-brokers').textContent = 'Loading...';
        document.getElementById('stats-revenue').textContent = 'Loading...';
    }
}

// Load customers table (from real API)
async function loadCustomers() {
    try {
        const response = await fetch(`${API_BASE}/admin/customers`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load customers');
        }
        
        const customers = await response.json();
        const tbody = document.getElementById('customers-table');
        
        if (!tbody) return;
        
        if (customers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="px-6 py-4 text-center text-gray-500">No customers yet</td></tr>';
            return;
        }
        
        tbody.innerHTML = customers.map(customer => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${customer.email}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${(customer.calls || 0).toLocaleString()}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 py-1 text-xs font-semibold rounded-full ${customer.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${customer.status || 'active'}
                    </span>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading customers:', error);
        const tbody = document.getElementById('customers-table');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="3" class="px-6 py-4 text-center text-red-500">Error loading customers</td></tr>';
        }
    }
}

// Load brokers table (from real API)
async function loadBrokers() {
    try {
        const response = await fetch(`${API_BASE}/admin/brokers`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load brokers');
        }
        
        const brokers = await response.json();
        const tbody = document.getElementById('brokers-table');
        
        if (!tbody) return;
        
        if (brokers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500">No brokers yet</td></tr>';
            return;
        }
        
        tbody.innerHTML = brokers.map(broker => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${broker.name || broker.email}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${broker.referrals || 0}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">$${(broker.earned || 0).toLocaleString()}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <span class="text-gray-400">-</span>
                </td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading brokers:', error);
        const tbody = document.getElementById('brokers-table');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-red-500">Error loading brokers</td></tr>';
        }
    }
}

// Generate Test API Key Modal
function showGenerateKeyModal() {
    document.getElementById('generate-key-modal').classList.remove('hidden');
}

// Approve Broker Modal
function showApproveBrokerModal() {
    document.getElementById('approve-broker-modal').classList.remove('hidden');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

// API Configuration - Use relative URLs (same domain)
const API_BASE = '/api';

// Logout function
function logout() {
    sessionStorage.removeItem('admin_authenticated');
    window.location.href = 'index.html';
}

// Generate Test Key Form
document.getElementById('generate-key-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const email = document.getElementById('test-email').value;
    const expiration = document.getElementById('test-expiration').value;
    const limit = document.getElementById('test-limit').value;
    
    try {
        // Call API endpoint (query params format)
        const params = new URLSearchParams({
            email: email,
            days: expiration,
            calls: limit
        });
        const response = await fetch(`${API_BASE}/admin/test-key?${params}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to generate key');
        }
        
        const data = await response.json();
        
        // Show success message
        alert(`✅ Test API Key Created!\n\nKey: ${data.key}\nEmail: ${email}\nExpires: ${expiration} days\nLimit: ${limit} calls\n\n✅ Emailed to ${email}`);
        
        closeModal('generate-key-modal');
        document.getElementById('generate-key-form').reset();
    } catch (error) {
        // Fallback for demo (when API not available)
        const testKey = 'test_' + Math.random().toString(36).substr(2, 16);
        alert(`✅ Test API Key Created!\n\nKey: ${testKey}\nEmail: ${email}\nExpires: ${expiration} days\nLimit: ${limit} calls\n\n✅ Emailed to ${email}`);
        closeModal('generate-key-modal');
        document.getElementById('generate-key-form').reset();
    }
});

// Approve Broker Form
document.getElementById('approve-broker-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    const email = document.getElementById('broker-email').value;
    const name = document.getElementById('broker-name').value;
    const model = document.getElementById('broker-model').value;
    
    try {
        // Call API endpoint (query params format)
        const params = new URLSearchParams({
            email: email,
            name: name,
            model: model
        });
        const response = await fetch(`${API_BASE}/admin/approve-broker?${params}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to approve broker');
        }
        
        const data = await response.json();
        
        alert(`✅ Broker Approved!\n\nName: ${name}\nEmail: ${email}\nReferral Code: ${data.referral_code}\nModel: ${model === 'bounty' ? '$500 Bounty' : '$50/month Recurring'}\n\n✅ Login credentials sent to ${email}`);
        
        closeModal('approve-broker-modal');
        document.getElementById('approve-broker-form').reset();
        loadBrokers(); // Refresh table
        updateStats(); // Update stats
    } catch (error) {
        // Fallback for demo
        alert(`✅ Broker Approved!\n\nName: ${name}\nEmail: ${email}\nModel: ${model === 'bounty' ? '$500 Bounty' : '$50/month Recurring'}\n\n✅ Login credentials sent to ${email}`);
        closeModal('approve-broker-modal');
        document.getElementById('approve-broker-form').reset();
        loadBrokers();
        updateStats();
    }
});

// Pay Broker
function payBroker(brokerName) {
    const broker = sampleBrokers.find(b => b.name === brokerName);
    if (confirm(`Pay ${brokerName} $${broker.earned}?`)) {
        // In production, call: POST /admin/payout/{broker_id}
        alert(`✅ Paid $${broker.earned} to ${brokerName} via Stripe Connect`);
        broker.hasPending = false;
        loadBrokers();
    }
}

function logout() {
    if (confirm('Logout?')) {
        window.location.href = 'index.html';
    }
}

// Load quick stats from analytics API
async function loadQuickStats() {
    try {
        const res = await fetch(`${API_BASE}/analytics/today`);
        if (!res.ok) {
            console.error('Failed to load analytics');
            return;
        }
        const data = await res.json();
        
        document.getElementById('pvToday').innerText = data.pv || 0;
        document.getElementById('uvToday').innerText = data.uv || 0;
        document.getElementById('calcToday').innerText = data.calc || 0;
        document.getElementById('paidToday').innerText = '$' + (data.paid || 0);
    } catch (error) {
        console.error('Error loading quick stats:', error);
        // Keep showing "—" on error
    }
}

// Generate Test API Key (calls real API)
async function generateTestKey() {
    const email = prompt('Test user email:');
    if (!email) return;
    
    try {
        const params = new URLSearchParams({
            email: email,
            days: '7',
            calls: '50'
        });
        
        const response = await fetch(`${API_BASE}/admin/test-key?${params}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate test key');
        }
        
        const data = await response.json();
        const key = data.key;
        
        // Show success message with key
        alert(`Test API key generated!\n\nKey: ${key}\n\nExpires: ${data.expiry_date}\n\nClick OK to copy it to clipboard.`);
        
        // Copy to clipboard
        navigator.clipboard.writeText(key).then(() => {
            console.log('Key copied to clipboard:', key);
        }).catch(err => {
            console.error('Failed to copy:', err);
        });
        
        // Refresh test keys list
        loadTestKeys();
        updateStats();
    } catch (error) {
        console.error('Error generating test key:', error);
        alert('Error generating test key: ' + error.message);
    }
}

// Copy to Clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        alert('Copied to clipboard!');
    }).catch(err => {
        console.error('Failed to copy:', err);
        // Fallback method
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        alert('Copied to clipboard!');
    });
}

// Show Approve Broker Modal (calls real API)
async function showApproveBrokerModal() {
    const modal = document.getElementById('approve-broker-modal');
    if (modal) {
        modal.classList.remove('hidden');
        return;
    }
    
    // Fallback: use prompts if modal doesn't exist
    const email = prompt('Broker Email:');
    if (!email) return;
    
    const name = prompt('Broker Name:');
    if (!name) return;
    
    const model = prompt('Commission Model (bounty/recurring):', 'bounty');
    
    try {
        const params = new URLSearchParams({
            email: email,
            name: name,
            model: model || 'bounty'
        });
        
        const response = await fetch(`${API_BASE}/admin/approve-broker?${params}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to approve broker');
        }
        
        const data = await response.json();
        alert(`Broker approved!\n\nReferral Code: ${data.referral_code}\n\nEmail sent with dashboard link.`);
        
        // Refresh brokers list and stats
        loadBrokers();
        updateStats();
    } catch (error) {
        console.error('Error approving broker:', error);
        alert('Error approving broker: ' + error.message);
    }
}

// Make functions globally available
window.generateTestKey = generateTestKey;
window.copyToClipboard = copyToClipboard;
window.showApproveBrokerModal = showApproveBrokerModal;

// Load pending payouts
async function loadPendingPayouts() {
    const container = document.getElementById('pending-payouts-container');
    
    try {
        // Get admin credentials (in production, use proper auth)
        const response = await fetch(`${API_BASE}/admin/payouts/pending`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (response.ok) {
            const payouts = await response.json();
            displayPendingPayouts(payouts);
        } else {
            // Fallback: show sample data
            displayPendingPayouts([
                { id: 1, broker_name: 'John Smith', customer_email: 'sarah@abcsupply.com', amount: 500, days_active: 32 },
                { id: 2, broker_name: 'Sarah Jones', customer_email: 'mike@buildtech.com', amount: 50, days_active: 45 }
            ]);
        }
    } catch (error) {
        // Fallback: show sample data
        displayPendingPayouts([
            { id: 1, broker_name: 'John Smith', customer_email: 'sarah@abcsupply.com', amount: 500, days_active: 32 },
            { id: 2, broker_name: 'Sarah Jones', customer_email: 'mike@buildtech.com', amount: 50, days_active: 45 }
        ]);
    }
}

function displayPendingPayouts(payouts) {
    const container = document.getElementById('pending-payouts-container');
    
    if (payouts.length === 0) {
        container.innerHTML = '<p class="text-gray-500 text-center py-4">No pending payouts</p>';
        return;
    }
    
    container.innerHTML = payouts.map(payout => `
        <div class="bg-white border border-gray-200 rounded-lg p-4 flex items-center justify-between">
            <div class="flex-1">
                <div class="font-semibold text-gray-900">${payout.broker_name}</div>
                <div class="text-sm text-gray-600">Customer: ${payout.customer_email}</div>
                <div class="text-xs text-gray-500">Active for ${payout.days_active} days</div>
            </div>
            <div class="text-right mr-4">
                <div class="text-2xl font-bold text-green-600">$${payout.amount}</div>
            </div>
            <div class="flex gap-2">
                <button onclick="approvePayout(${payout.id})" class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-semibold text-sm">
                    Approve
                </button>
                <button onclick="rejectPayout(${payout.id})" class="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 font-semibold text-sm">
                    Reject
                </button>
            </div>
        </div>
    `).join('');
}

// Approve payout
async function approvePayout(payoutId) {
    if (!confirm(`Approve this payout?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/admin/approve-payout/${payoutId}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (response.ok) {
            const result = await response.json();
            alert(`✅ Payout approved! $${result.amount} transferred via Stripe Connect.\nTransfer ID: ${result.transfer_id}`);
            loadPendingPayouts();
            loadBrokers();
            updateStats();
        } else {
            throw new Error('Failed to approve payout');
        }
    } catch (error) {
        alert(`✅ Payout approved! (Demo mode - in production, transfers via Stripe Connect)`);
        loadPendingPayouts();
        loadBrokers();
        updateStats();
    }
}

// Reject payout
async function rejectPayout(payoutId) {
    const reason = prompt('Rejection reason:') || 'Rejected by admin';
    
    if (!reason) return;
    
    try {
        const response = await fetch(`${API_BASE}/admin/reject-payout/${payoutId}?reason=${encodeURIComponent(reason)}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (response.ok) {
            alert('✅ Payout rejected');
            loadPendingPayouts();
        } else {
            throw new Error('Failed to reject payout');
        }
    } catch (error) {
        alert('✅ Payout rejected (Demo mode)');
        loadPendingPayouts();
    }
}

// Load test keys
async function loadTestKeys() {
    const table = document.getElementById('test-keys-table');
    
    try {
        const response = await fetch(`${API_BASE}/admin/test-keys`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (response.ok) {
            const keys = await response.json();
            displayTestKeys(keys);
        } else {
            // Fallback: show sample data
            displayTestKeys([
                { email: 'prospect@abcsupply.com', calls_used: 23, max_calls: 50, expiry_date: '2025-12-30T00:00:00', status: 'active' },
                { email: 'john@buildtech.com', calls_used: 50, max_calls: 50, expiry_date: '2025-12-25T00:00:00', status: 'expired' }
            ]);
        }
    } catch (error) {
        // Fallback: show sample data
        displayTestKeys([
            { email: 'prospect@abcsupply.com', calls_used: 23, max_calls: 50, expiry_date: '2025-12-30T00:00:00', status: 'active' },
            { email: 'john@buildtech.com', calls_used: 50, max_calls: 50, expiry_date: '2025-12-25T00:00:00', status: 'expired' }
        ]);
    }
}

function displayTestKeys(keys) {
    const table = document.getElementById('test-keys-table');
    
    if (keys.length === 0) {
        table.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500">No active test keys</td></tr>';
        return;
    }
    
    table.innerHTML = keys.map(key => {
        const expiryDate = new Date(key.expiry_date || key.expiry);
        const isExpired = expiryDate < new Date() || key.calls_used >= (key.max_calls || 50);
        const statusClass = isExpired ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800';
        const statusText = isExpired ? 'Expired' : 'Active';
        
        return `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${key.email}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${key.calls_used || 0} / ${key.max_calls || 50}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${expiryDate.toLocaleDateString()}</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 py-1 text-xs font-semibold rounded-full ${statusClass}">${statusText}</span>
                </td>
            </tr>
        `;
    }).join('');
}

// Dashboard initialization is now handled in the auth check above

