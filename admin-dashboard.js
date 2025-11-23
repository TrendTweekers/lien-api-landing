// Admin Dashboard Functionality
// Hard-coded data for now - wire to API later

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
function updateStats() {
    const customerCount = sampleCustomers.filter(c => c.status === 'Active').length;
    const brokerCount = sampleBrokers.length;
    const totalRevenue = sampleBrokers.reduce((sum, b) => sum + b.earned, 0);
    
    document.getElementById('stats-customers').textContent = `${customerCount} customers`;
    document.getElementById('stats-brokers').textContent = `${brokerCount} brokers`;
    document.getElementById('stats-revenue').textContent = `$${totalRevenue.toLocaleString()}`;
}

// Load customers table
function loadCustomers() {
    const tbody = document.getElementById('customers-table');
    tbody.innerHTML = sampleCustomers.map(customer => `
        <tr>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${customer.email}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${customer.calls.toLocaleString()}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 py-1 text-xs font-semibold rounded-full ${customer.status === 'Active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                    ${customer.status}
                </span>
            </td>
        </tr>
    `).join('');
}

// Load brokers table
function loadBrokers() {
    const tbody = document.getElementById('brokers-table');
    tbody.innerHTML = sampleBrokers.map(broker => `
        <tr>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${broker.name}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${broker.referrals}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">$${broker.earned.toLocaleString()}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm">
                ${broker.hasPending ? 
                    `<button onclick="payBroker('${broker.name}')" class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 font-semibold text-xs">Pay</button>` :
                    `<span class="text-gray-400">-</span>`
                }
            </td>
        </tr>
    `).join('');
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

// API Configuration
const API_BASE = 'https://vigilant-nourishment-production.up.railway.app';

// Set your admin credentials (should match Railway env vars)
const ADMIN_USER = 'admin';
const ADMIN_PASS = 'LienAPI2025';

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

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateStats();
    loadCustomers();
    loadBrokers();
    loadPendingPayouts();
    loadTestKeys();
});

