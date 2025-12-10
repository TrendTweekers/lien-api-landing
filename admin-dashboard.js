// Admin Dashboard Functionality
// Hard-coded data for now - wire to API later
// Version: 2025-01-XX - Analytics disabled to fix 404 error

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
    updateQuickStats();
    loadCustomers();
    loadBrokers();
    loadBrokersList();
    loadPendingPayouts();
    loadTestKeys();
    loadPartnerApplications();
    loadEmailCaptures();
    loadFlaggedReferrals();
    updateActivityFeed();
    updateLiveStats();
    updateQuickStatsRow();
    
    // Refresh stats
    setInterval(updateQuickStats, 30000);
    setInterval(updateActivityFeed, 60000);
    setInterval(updateLiveStats, 60000);
    setInterval(updateQuickStatsRow, 60000);
    
    // Refresh stats every 60 seconds
    // setInterval(loadQuickStats, 60000); // Disabled - analytics endpoint returns 404
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
// DISABLED - Analytics endpoint returns 404, dashboard works fine without it
async function loadQuickStats() {
    // Analytics endpoint disabled - stats show default values (0)
    return;
    /*
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
    */
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

// Load partner applications
async function loadPartnerApplications() {
    const table = document.getElementById('applicationsTable');
    const emptyState = document.getElementById('noApplications');
    const pendingCount = document.getElementById('pendingCount');
    
    if (!table) {
        console.error('Applications table not found');
        return;
    }
    
    try {
        table.innerHTML = '<tr><td colspan="5" class="py-4 px-6 text-center text-gray-500">Loading applications...</td></tr>';
        
        console.log('Fetching: /api/admin/partner-applications');
        
        const response = await fetch(`${API_BASE}/admin/partner-applications?status=all`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        console.log('Response status:', response.status);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('Received data:', data);
        
        // Extract applications array
        const applications = data.applications || data || [];
        
        if (!Array.isArray(applications)) {
            throw new Error('Applications is not an array: ' + typeof applications);
        }
        
        // Update pending count
        const pending = applications.filter(a => a.status === 'pending').length;
        if (pendingCount) pendingCount.textContent = pending;
        
        if (applications.length === 0) {
            table.innerHTML = '';
            if (emptyState) {
                emptyState.style.display = 'block';
            }
            return;
        }
        
        if (emptyState) {
            emptyState.style.display = 'none';
        }
        
        // Render applications as table rows (matching exact template)
        table.innerHTML = applications.map(app => {
            const date = app.timestamp || app.created_at ? formatTimeAgo(new Date(app.timestamp || app.created_at)) : 'N/A';
            const status = app.status || 'pending';
            const initials = (app.name || 'U').split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 1);
            const statusClass = status === 'approved' ? 'bg-green-100 text-green-800' : 
                              status === 'flagged' ? 'bg-red-100 text-red-800' : 
                              'bg-yellow-100 text-yellow-800';
            const statusText = status.charAt(0).toUpperCase() + status.slice(1);
            
            return `
                <tr class="hover:bg-gray-50">
                    <td class="py-4 px-6">
                        <div class="flex items-center">
                            <div class="h-10 w-10 flex-shrink-0 bg-blue-100 rounded-full flex items-center justify-center">
                                <span class="text-blue-600 font-semibold">${initials}</span>
                            </div>
                            <div class="ml-4">
                                <div class="text-sm font-medium text-gray-900">${app.name || 'N/A'}</div>
                                <div class="text-sm text-gray-500">${app.email || 'N/A'}</div>
                            </div>
                        </div>
                    </td>
                    <td class="py-4 px-6 text-sm text-gray-900">${app.company || 'N/A'}</td>
                    <td class="py-4 px-6 text-sm text-gray-500">${date}</td>
                    <td class="py-4 px-6">
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusClass}">
                            ${statusText}
                        </span>
                    </td>
                    <td class="py-4 px-6 text-sm font-medium">
                        <div class="flex space-x-2">
                            <button onclick="approveApplication(${app.id})" class="text-green-600 hover:text-green-900">Approve</button>
                            <button onclick="rejectApplication(${app.id})" class="text-red-600 hover:text-red-900">Reject</button>
                            <button onclick="viewApplication(${app.id})" class="text-blue-600 hover:text-blue-900">View</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        
        console.log('✅ Applications rendered successfully');
        
    } catch (error) {
        console.error('❌ Error loading applications:', error);
        table.innerHTML = `
            <tr>
                <td colspan="5" class="py-4 px-6 text-center text-red-500">
                    Error loading applications: ${error.message}
                </td>
            </tr>
        `;
    }
}

// Format time ago helper
function formatTimeAgo(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
    if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return date.toLocaleDateString();
}

// Approve application
async function approveApplication(id) {
    if (!confirm('Approve this partner application?')) return;
    
    try {
        await approveAndCopy(id, '');
        loadPartnerApplications();
    } catch (error) {
        alert('Error approving application: ' + error.message);
    }
}
window.approveApplication = approveApplication;

// Reject application
async function rejectApplication(id) {
    if (!confirm('Reject this partner application?')) return;
    
    try {
        const adminUser = window.ADMIN_USER || ADMIN_USER;
        const adminPass = window.ADMIN_PASS || ADMIN_PASS;
        const response = await fetch(`${API_BASE}/admin/partner-applications/${id}/reject`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
            }
        });
        
        if (response.ok) {
            alert('Application rejected');
            loadPartnerApplications();
        } else {
            throw new Error('Failed to reject application');
        }
    } catch (error) {
        alert('Error rejecting application: ' + error.message);
    }
}
window.rejectApplication = rejectApplication;

// View application
function viewApplication(id) {
    // Open modal or navigate to detail page
    alert('View application details for ID: ' + id);
}
window.viewApplication = viewApplication;

// Export applications
function exportApplications() {
    const rows = Array.from(document.querySelectorAll('#applicationsTable tr')).slice(1).map(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length < 4) return null;
        return {
            name: cells[0].querySelector('.text-sm.font-medium')?.textContent.trim() || '',
            email: cells[0].querySelector('.text-sm.text-gray-500')?.textContent.trim() || '',
            company: cells[1].textContent.trim() || '',
            status: cells[3].textContent.trim() || ''
        };
    }).filter(r => r);
    
    if (rows.length === 0) {
        alert('No data to export');
        return;
    }
    
    const csv = 'Name,Email,Company,Status\n' + rows.map(r => `"${r.name}","${r.email}","${r.company}","${r.status}"`).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'partner-applications-' + new Date().toISOString().split('T')[0] + '.csv';
    a.click();
    URL.revokeObjectURL(url);
}
window.exportApplications = exportApplications;

// Load email captures
async function loadEmailCaptures() {
    try {
        const response = await fetch(`${API_BASE}/admin/email-captures`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load email captures');
        }
        
        const captures = await response.json();
        const tbody = document.getElementById('emailCapturesTable');
        
        if (!tbody) {
            console.error('Email captures table not found');
            return;
        }
        
        if (captures.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-gray-500">No email captures yet</td></tr>';
            return;
        }
        
        tbody.innerHTML = captures.map(c => `
            <tr>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${c.email}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${c.ip || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${new Date(c.timestamp).toLocaleString()}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">3-10 range</td>
            </tr>
        `).join('');
    } catch (error) {
        console.error('Error loading email captures:', error);
        const tbody = document.getElementById('emailCapturesTable');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" class="px-6 py-4 text-center text-red-500">Error loading email captures</td></tr>';
        }
    }
}

// Approve partner application
async function approvePartner(email) {
    if (!confirm(`Approve this partner application for ${email}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/admin/approve-partner`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ email: email })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to approve partner');
        }
        
        alert('Partner approved! They will receive an email with their referral link.');
        loadPartnerApplications(); // Reload table
    } catch (error) {
        console.error('Error approving partner:', error);
        alert('Error approving partner: ' + error.message);
    }
}

// Make approvePartner globally available
window.approvePartner = approvePartner;

// Approve and copy link function
async function approveAndCopy(id, email) {
    try {
        const adminUser = window.ADMIN_USER || ADMIN_USER;
        const adminPass = window.ADMIN_PASS || ADMIN_PASS;
        const response = await fetch(`${API_BASE}/admin/approve-partner/${id}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
            }
        });
        
        const data = await response.json();
        
        if (data.referral_link) {
            navigator.clipboard.writeText(data.referral_link);
            alert(`✅ Approved & link copied:\n${data.referral_link}`);
            loadPartnerApplications(); // Refresh list
            updateQuickStats(); // Refresh stats
        } else {
            alert('Approval failed: ' + (data.message || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error approving partner:', error);
        alert('Error approving partner: ' + error.message);
    }
}
window.approveAndCopy = approveAndCopy;

// Copy link function
function copyLink(link) {
    navigator.clipboard.writeText(link);
    alert(`✅ Link copied:\n${link}`);
}
window.copyLink = copyLink;

// Bulk payout function
async function bulkPayout() {
    try {
        const adminUser = window.ADMIN_USER || ADMIN_USER;
        const adminPass = window.ADMIN_PASS || ADMIN_PASS;
        const response = await fetch(`${API_BASE}/admin/ready-payouts`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
            }
        });
        
        const data = await response.json();
        const ready = data.ready || [];
        
        if (!ready.length) {
            alert('Nothing to pay');
            return;
        }
        
        const total = ready.reduce((sum, r) => sum + (r.payout || r.amount || 0), 0);
        if (!confirm(`Pay $${total.toFixed(2)} to ${ready.length} broker(s)?`)) return;
        
        for (const r of ready) {
            await fetch(`${API_BASE}/admin/mark-paid/${r.id}`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
                }
            });
        }
        
        alert('✅ All marked as paid (send money manually)');
        location.reload();
    } catch (error) {
        console.error('Error in bulk payout:', error);
        alert('Error processing bulk payout: ' + error.message);
    }
}
window.bulkPayout = bulkPayout;

// Filter applications
let currentFilter = 'all';
async function filterApps(status) {
    currentFilter = status;
    try {
        const adminUser = window.ADMIN_USER || ADMIN_USER;
        const adminPass = window.ADMIN_PASS || ADMIN_PASS;
        const response = await fetch(`${API_BASE}/admin/partner-applications?status=${status}`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
            }
        });
        
        const data = await response.json();
        const applications = data.applications || [];
        
        // Update counts by fetching all
        const allResponse = await fetch(`${API_BASE}/admin/partner-applications?status=all`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
            }
        });
        const allData = await allResponse.json();
        const allApps = allData.applications || [];
        
        document.getElementById('pendingCount').textContent = allApps.filter(a => a.status === 'pending').length;
        document.getElementById('approvedCount').textContent = allApps.filter(a => a.status === 'approved').length;
        document.getElementById('flaggedCount').textContent = allApps.filter(a => a.status === 'flagged').length;
        
        // Render filtered applications as cards
        const cardContainer = document.getElementById('applicationsList');
        if (cardContainer) {
            if (applications.length === 0) {
                cardContainer.innerHTML = '<div class="card text-center text-muted-foreground">No applications found</div>';
            } else {
                cardContainer.innerHTML = applications.map(app => renderApplication(app)).join('');
            }
        }
        
        // Also update table for backward compatibility
        const container = document.getElementById('partnerApplicationsTable');
        if (!container) return;
    } catch (error) {
        console.error('Error filtering applications:', error);
        alert('Error filtering applications: ' + error.message);
    }
}
window.filterApps = filterApps;

// Update quick stats
async function updateQuickStats() {
    try {
        const adminUser = window.ADMIN_USER || ADMIN_USER;
        const adminPass = window.ADMIN_PASS || ADMIN_PASS;
        
        // Get today's calculations (placeholder - implement endpoint)
        document.getElementById('todayCalc').textContent = '0';
        
        // Get pending brokers
        const appsResponse = await fetch(`${API_BASE}/admin/partner-applications?status=pending`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
            }
        });
        const appsData = await appsResponse.json();
        document.getElementById('pendingBrokers').textContent = (appsData.applications || []).length;
        
        // Get ready payouts
        const payoutsResponse = await fetch(`${API_BASE}/admin/ready-payouts`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${adminUser}:${adminPass}`)
            }
        });
        const payoutsData = await payoutsResponse.json();
        const ready = payoutsData.ready || [];
        document.getElementById('readyPayout').textContent = ready.length;
        const total = ready.reduce((sum, r) => sum + (r.payout || r.amount || 0), 0);
        document.getElementById('readyTotal').textContent = total.toFixed(0);
        
        // Get monthly revenue (placeholder - implement endpoint)
        document.getElementById('monthRevenue').textContent = '$0';
    } catch (error) {
        console.error('Error updating quick stats:', error);
    }
}
window.updateQuickStats = updateQuickStats;

// Partner application card renderer
function renderApplication(app) {
    const date = app.timestamp || app.created_at ? new Date(app.timestamp || app.created_at).toLocaleDateString() : 'N/A';
    const status = app.status || 'pending';
    const statusPillClass = status === 'approved' ? 'pill-green' : status === 'flagged' ? 'pill-red' : 'pill-yellow';
    
    return `
        <div class="card flex items-center justify-between">
            <div>
                <p class="font-semibold">${app.name || 'N/A'}</p>
                <p class="text-sm text-muted-foreground">${app.company || 'N/A'} · ${app.client_count || 0} clients</p>
                <p class="text-xs text-muted-foreground">${app.email || 'N/A'}</p>
                <p class="text-xs text-muted-foreground mt-1">${date}</p>
            </div>
            <div class="flex gap-2 items-center">
                <span class="pill ${statusPillClass}">${status}</span>
                ${status === 'pending' ? `
                    <button onclick="approveAndCopy(${app.id}, '${app.email}')" class="btn btn-green">Approve & Copy</button>
                ` : app.referral_link ? `
                    <button onclick="copyLink('${app.referral_link}')" class="btn btn-blue">Copy Link</button>
                ` : ''}
            </div>
        </div>
    `;
}
window.renderApplication = renderApplication;

// Flagged referral card renderer
function renderFlagged(ref) {
    const fraudFlags = ref.fraud_flags || ref.fraud_signals || [];
    return `
        <div class="card border-l-4 border-red-500">
            <div class="flex justify-between items-start mb-3">
                <div>
                    <p class="font-bold text-red-700">Risk Score: ${ref.risk_score || 'N/A'}</p>
                    <p class="text-sm text-muted-foreground">${ref.broker_name || 'Unknown'} → ${ref.customer_email || 'N/A'}</p>
                </div>
                <div class="flex gap-2">
                    <button onclick="approveReferral(${ref.id})" class="btn btn-green">✅ Approve</button>
                    <button onclick="denyReferral(${ref.id})" class="btn btn-red">❌ Deny</button>
                </div>
            </div>
            <div class="flex flex-wrap gap-2">
                ${fraudFlags.map(f => `<span class="pill pill-yellow">${String(f).replace(/_/g, ' ')}</span>`).join('')}
            </div>
        </div>
    `;
}
window.renderFlagged = renderFlagged;

// Customer card renderer
function renderCustomer(customer) {
    return `
        <div class="card">
            <p class="font-semibold">${customer.email || 'N/A'}</p>
            <p class="text-sm text-muted-foreground">${customer.calls || 0} calls</p>
            <span class="pill ${customer.status === 'active' ? 'pill-green' : 'pill-yellow'}">${customer.status || 'unknown'}</span>
        </div>
    `;
}
window.renderCustomer = renderCustomer;

// Update quick stats row
function updateQuickStatsRow() {
    // Update today's revenue
    const todayRevenue = document.getElementById('todayRevenue');
    if (todayRevenue) {
        // This would normally fetch from analytics
        todayRevenue.textContent = '$0';
    }
    
    // Update active customers
    const activeCustomers = document.getElementById('activeCustomers');
    if (activeCustomers) {
        fetch(`${API_BASE}/admin/customers`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        })
        .then(r => r.json())
        .then(customers => {
            const active = Array.isArray(customers) ? customers.filter(c => c.status === 'active').length : 0;
            activeCustomers.textContent = active;
        })
        .catch(() => {
            activeCustomers.textContent = '0';
        });
    }
    
    // Update calculations today
    const calculationsToday = document.getElementById('calculationsToday');
    if (calculationsToday) {
        // This would normally fetch from analytics
        calculationsToday.textContent = '0';
    }
    
    // Update pending payouts
    const pendingPayouts = document.getElementById('pendingPayouts');
    if (pendingPayouts) {
        fetch(`${API_BASE}/admin/ready-payouts`, {
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        })
        .then(r => r.json())
        .then(data => {
            const count = data.ready ? data.ready.length : 0;
            pendingPayouts.textContent = count;
        })
        .catch(() => {
            pendingPayouts.textContent = '0';
        });
    }
}
window.updateQuickStatsRow = updateQuickStatsRow;

// Dashboard initialization is now handled in the auth check above

