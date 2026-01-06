// ==================== ADMIN DASHBOARD V2 ====================
// Reuses all existing API endpoints and functions from admin-dashboard.js
// Only changes: UI rendering to match Lovable design

console.log('🛡️ Admin Dashboard V2 Loading...');

// Admin credentials (same as V1)
const ADMIN_USER = window.ADMIN_USER || 'admin';
const ADMIN_PASS = window.ADMIN_PASS || 'LienAPI2025';

// Admin API key for /api/admin/* endpoints
const ADMIN_API_KEY = (window.ADMIN_API_KEY || "").trim();

// Debug log ONCE at boot
console.log("[AdminV2] key present:", ADMIN_API_KEY.length > 0, "len:", ADMIN_API_KEY.length);

// Show banner helpers
function showBanner(id, message) {
    const banner = document.getElementById(id) || document.createElement('div');
    banner.id = id;
    banner.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; background: #dc2626; color: white; padding: 12px; text-align: center; z-index: 10000; font-weight: bold;';
    banner.textContent = message;
    if (!document.getElementById(id)) {
        document.body.insertBefore(banner, document.body.firstChild);
    }
}

function removeBanner(id) {
    const banner = document.getElementById(id);
    if (banner) banner.remove();
}

// Single wrapper for ALL admin API requests
async function adminFetch(url, options = {}) {
    const key = ADMIN_API_KEY;
    
    if (!key) {
        showBanner('admin-key-missing-banner', '⚠️ ADMIN_API_KEY missing — set Railway variable ADMIN_API_KEY and redeploy');
        throw new Error("ADMIN_API_KEY not set");
    }
    
    // Build headers with X-ADMIN-KEY
    const headers = {
        "X-ADMIN-KEY": key,
        "Content-Type": "application/json",
        ...(options.headers || {})
    };
    
    // Merge options
    const fetchOptions = {
        ...options,
        headers,
        credentials: "include"
    };
    
    try {
        const response = await fetch(url, fetchOptions);
        
        // Handle 401 - unauthorized
        if (response.status === 401) {
            showBanner('admin-unauthorized-banner', '⚠️ Admin unauthorized (X-ADMIN-KEY missing/invalid)');
            const errorData = await response.json().catch(() => ({ detail: "Unauthorized" }));
            throw new Error(errorData.detail || "Unauthorized");
        }
        
        // Handle 503 - server not configured
        if (response.status === 503) {
            showBanner('admin-server-error-banner', '⚠️ ADMIN_API_KEY not configured on server');
            const errorData = await response.json().catch(() => ({ detail: "Server configuration error" }));
            throw new Error(errorData.detail || "Server configuration error");
        }
        
        // Parse JSON or return response
        if (response.ok) {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return await response.json();
            }
            return response;
        }
        
        // Other errors
        const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
        
    } catch (error) {
        if (error.message.includes("Unauthorized") || error.message.includes("X-ADMIN-KEY")) {
            throw error; // Already handled above
        }
        throw error;
    }
}

// Check admin key on page load and test connection
async function initAdminDashboard() {
    if (!ADMIN_API_KEY) {
        showBanner('admin-key-missing-banner', '⚠️ ADMIN_API_KEY missing — set Railway variable ADMIN_API_KEY and redeploy');
        return;
    }
    
    removeBanner('admin-key-missing-banner');
    
    // Test connection with ping endpoint
    try {
        const result = await adminFetch('/api/admin/ping');
        if (result && result.ok) {
            console.log('✅ Admin API connected');
            // Show success indicator in UI
            const statusEl = document.getElementById('admin-api-status') || document.createElement('div');
            statusEl.id = 'admin-api-status';
            statusEl.textContent = '✅ connected';
            statusEl.style.cssText = 'position: fixed; top: 50px; right: 20px; background: #10b981; color: white; padding: 8px 12px; border-radius: 4px; font-size: 12px; z-index: 9999;';
            if (!document.getElementById('admin-api-status')) {
                document.body.appendChild(statusEl);
            }
        }
    } catch (error) {
        console.error('[Admin V2] Ping failed:', error);
    }
}

// Initialize on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdminDashboard);
} else {
    initAdminDashboard();
}

// Safe helper functions (same as V1)
window.safe = {
    get: function(id) {
        const el = document.getElementById(id);
        if (!el && id) {
            console.log(`[Safe] Creating dummy #${id}`);
            const dummy = document.createElement('div');
            dummy.id = id;
            dummy.className = 'safe-dummy';
            dummy.style.display = 'none';
            document.body.appendChild(dummy);
            return dummy;
        }
        return el;
    },
    text: function(id, text) {
        const el = this.get(id);
        if (el) {
            el.textContent = text;
        }
    },
    html: function(id, html) {
        const el = this.get(id);
        if (el) {
            el.innerHTML = html;
        }
    },
    hide: function(id) {
        const el = this.get(id);
        if (el) el.style.display = 'none';
    },
    show: function(id) {
        const el = this.get(id);
        if (el) el.style.display = '';
    }
};

// Tab switching for payouts
function switchPayoutTab(tab) {
    // Hide all tabs
    document.querySelectorAll('#admin-v2 .tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('#admin-v2 .tab-button').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabContent = document.getElementById(`payout-tab-${tab}`);
    const tabButton = document.getElementById(`tab-${tab}`);
    if (tabContent) tabContent.classList.add('active');
    if (tabButton) tabButton.classList.add('active');
    
    // Load data for the selected tab
    if (tab === 'pending') {
        loadReadyToPay();
    } else if (tab === 'hold') {
        loadOnHold();
    } else if (tab === 'paid') {
        loadPaymentHistory();
    }
}

// Load partner applications (reuses V1 API)
async function loadPartnerApplications() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch('/api/admin/partner-applications?status=pending');
        let applications = data.applications || data || [];
        
        if (!Array.isArray(applications)) {
             console.warn('[Admin V2] Applications data is not an array, resetting to empty');
             applications = [];
        }
        
        applications = applications.filter(app => app.status === 'pending' || !app.status);
        
        if (!Array.isArray(applications) || applications.length === 0) {
            safe.html('v2-applicationsTable', `
                <tr>
                    <td colspan="6" class="text-center py-12">
                        <div class="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 text-3xl">
                            📋
                        </div>
                        <h3 class="text-lg font-semibold mb-2">No Applications Yet</h3>
                        <p class="text-gray-600">Partner applications will appear here when submitted</p>
                    </td>
                </tr>
            `);
            safe.text('v2-pendingCount', '0 Pending');
            safe.text('v2-pendingApps', '0');
            return;
        }
        
        const html = applications.map(app => {
            const commissionBadge = app.commission_model === 'bounty' 
                ? '<span class="badge badge-bounty">$500 Bounty</span>'
                : '<span class="badge badge-monthly">$50/month</span>';
            
            const statusBadge = app.status === 'approved'
                ? '<span class="badge badge-success">Approved</span>'
                : app.status === 'rejected'
                ? '<span class="badge badge-error">Rejected</span>'
                : '<span class="badge badge-pending">Pending</span>';
            
            let dateStr = 'Recently';
            if (app.created_at || app.applied_at || app.timestamp) {
                try {
                    const date = new Date(app.created_at || app.applied_at || app.timestamp);
                    dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                } catch (e) {
                    dateStr = 'Recently';
                }
            }
            
            return `
                <tr class="hover:bg-gray-50">
                    <td>
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                                <span class="text-blue-600 font-semibold">${(app.name || 'U').charAt(0).toUpperCase()}</span>
                            </div>
                            <div>
                                <div class="font-semibold">${app.name || 'Unknown'}</div>
                                <div class="text-sm" style="color: var(--muted);">${app.email || ''}</div>
                            </div>
                        </div>
                    </td>
                    <td>${commissionBadge}</td>
                    <td style="color: var(--muted);">${app.company || 'N/A'}</td>
                    <td class="text-sm" style="color: var(--muted);">${dateStr}</td>
                    <td>${statusBadge}</td>
                    <td>
                        <div class="flex gap-2">
                            <button onclick="approveApplication(${app.id}, '${(app.email || '').replace(/'/g, "\\'")}', '${(app.name || 'Unknown').replace(/'/g, "\\'")}', '${app.commission_model || 'bounty'}')" class="btn btn-success btn-sm">
                                ✓ Approve
                            </button>
                            <button onclick="rejectApplication(${app.id})" class="btn btn-danger btn-sm">
                                ✗ Reject
                            </button>
                            <button onclick="deleteApplication(${app.id})" class="btn btn-outline btn-sm">
                                🗑️
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        
        safe.html('v2-applicationsTable', html);
        safe.text('v2-pendingCount', `${applications.length} Pending`);
        safe.text('v2-pendingApps', applications.length.toString());
        
    } catch (error) {
        console.error('[Admin V2] Error loading applications:', error);
        safe.html('v2-applicationsTable', '<tr><td colspan="6" class="text-center py-8 text-red-500">Error: ' + error.message + '</td></tr>');
    }
}

// Load active brokers (reuses V1 API)
async function loadActiveBrokers() {
    if (!ADMIN_API_KEY) return;
    
    console.log('[Admin V2] Loading active brokers...');
    
    try {
        const data = await adminFetch('/api/admin/brokers');
        console.log('[Admin V2] Brokers API data:', data);

        let brokers = data.brokers || data || [];
        
        // Debug: Log all broker emails to help verify if the broker is present
        if (Array.isArray(brokers)) {
            console.log('[Admin V2] Received brokers count:', brokers.length);
            console.log('[Admin V2] Broker emails:', brokers.map(b => b.email));
        }

        if (!Array.isArray(brokers)) {
             console.warn('[Admin V2] Brokers data is not an array, resetting to empty');
             brokers = [];
        }
        
        console.log('[Admin V2] Processed brokers list:', brokers);

        if (!brokers || brokers.length === 0) {
            safe.html('v2-brokersList', `
                <tr>
                    <td colspan="8" class="text-center py-12">
                        <div class="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 text-3xl">
                            👥
                        </div>
                        <p style="color: var(--muted);">No active brokers yet</p>
                    </td>
                </tr>
            `);
            safe.text('v2-brokerCount', '0');
            safe.text('v2-activePartners', '0');
            return;
        }
        
        const html = brokers.map(broker => {
            try {
                const commissionBadge = broker.commission_model === 'bounty' || broker.model === 'bounty'
                    ? '<span class="badge badge-bounty">$500 Bounty</span>'
                    : '<span class="badge badge-monthly">$50/month</span>';
                
                const paymentMethod = broker.payment_method || '';
                let paymentBadge = '<span class="badge badge-pending">Not Set</span>';
                if (paymentMethod) {
                    const methodNames = {
                        'paypal': 'PayPal',
                        'wise': 'Wise',
                        'revolut': 'Revolut',
                        'sepa': 'SEPA',
                        'swift': 'SWIFT',
                        'crypto': 'Crypto',
                        'unlinked': 'Unlinked'
                    };
                    const name = methodNames[paymentMethod.toLowerCase()] || paymentMethod;
                    paymentBadge = `<span class="badge badge-ready">${name}</span>`;
                }
                
                let paymentStatusBadge = '<span class="badge badge-pending">Pending</span>';
                if (broker.payment_status === 'active') {
                    paymentStatusBadge = '<span class="badge badge-success">Active</span>';
                } else if (broker.payment_status === 'suspended') {
                    paymentStatusBadge = '<span class="badge badge-error">Suspended</span>';
                }
                
                const lastPaymentDate = broker.last_payment_date 
                    ? new Date(broker.last_payment_date).toLocaleDateString()
                    : 'Never';
                
                const totalPaid = broker.total_paid ? `$${parseFloat(broker.total_paid).toFixed(2)}` : '$0.00';
                
                // Safe quotes for strings
                const safeName = (broker.name || 'Unknown').replace(/'/g, "\\'");
                const safeEmail = (broker.email || '').replace(/'/g, "\\'");
                
                return `
                    <tr class="hover:bg-gray-50">
                        <td class="font-medium">${broker.name || 'Unknown'}</td>
                        <td style="color: var(--muted);">${broker.email || 'N/A'}</td>
                        <td class="text-center">${broker.total_referrals || 0}</td>
                        <td>${commissionBadge}</td>
                        <td>${paymentBadge}</td>
                        <td>${paymentStatusBadge}</td>
                        <td style="color: var(--muted);">${lastPaymentDate}</td>
                        <td class="font-semibold" style="color: var(--success);">${totalPaid}</td>
                        <td>
                            <div class="flex gap-2">
                                <button onclick="viewBrokerPaymentInfo('${broker.id}', '${safeName}', '${safeEmail}')" class="btn btn-outline btn-sm">
                                    👁️ View
                                </button>
                                <button onclick="deleteActiveBroker('${broker.id}')" class="btn btn-danger btn-sm">
                                    🗑️
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
            } catch (err) {
                console.error('[Admin V2] Error rendering broker row:', broker, err);
                return `<tr><td colspan="8" class="text-red-500">Error rendering broker: ${broker.email || 'Unknown'}</td></tr>`;
            }
        }).join('');
        
        safe.html('v2-brokersList', html);
        safe.text('v2-brokerCount', brokers.length.toString());
        safe.text('v2-activePartners', brokers.length.toString());
        
    } catch (error) {
        console.error('[Admin V2] Error loading brokers:', error);
        safe.html('v2-brokersList', '<tr><td colspan="8" class="text-center py-8 text-red-500">Error: ' + error.message + '</td></tr>');
    }
}

// Load ready to pay brokers (reuses V1 API)
async function loadReadyToPay() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch('/api/admin/brokers-ready-to-pay');
        // Handle both new ledger format (with brokers array) and legacy format
        let brokers = data.brokers || data || [];
        
        if (!Array.isArray(brokers)) {
             console.warn('[Admin V2] Ready-to-pay brokers data is not an array, resetting to empty');
             brokers = [];
        }
        
        // Filter brokers with total_due_now > 0 (from ledger)
        const brokersWithDue = brokers.filter(b => parseFloat(b.total_due_now || b.commission_owed || 0) > 0);
        
        if (brokersWithDue.length === 0) {
            safe.html('v2-ready-to-pay-list', `
                <tr>
                    <td colspan="8" class="text-center py-12">
                        <div class="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 text-3xl">
                            ✅
                        </div>
                        <p style="color: var(--muted);">All brokers are up to date</p>
                    </td>
                </tr>
            `);
            safe.text('pending-badge', '0');
            safe.text('v2-pendingPayouts', '0');
            return;
        }
        
        brokersWithDue.sort((a, b) => {
            // Sort by needs_setup first, then days_overdue, then commission_owed
            if (a.needs_setup && !b.needs_setup) return -1;
            if (!a.needs_setup && b.needs_setup) return 1;
            return (b.days_overdue || 0) - (a.days_overdue || 0) || 
                   parseFloat(b.total_due_now || b.commission_owed || 0) - parseFloat(a.total_due_now || a.commission_owed || 0);
        });
        
        const html = brokersWithDue.map(broker => {
            const isOverdue = (broker.days_overdue || 0) > 0;
            const overdueBadge = isOverdue 
                ? `<span class="badge badge-overdue">${broker.days_overdue} days overdue</span>`
                : '<span class="badge badge-ready">Ready</span>';
            
            const methodNames = {
                'paypal': 'PayPal',
                'wise': 'Wise',
                'revolut': 'Revolut',
                'sepa': 'SEPA',
                'swift': 'SWIFT',
                'crypto': 'Crypto'
            };
            const paymentMethod = methodNames[broker.payment_method?.toLowerCase()] || broker.payment_method || 'Not Set';
            
            const commissionBadge = broker.commission_model === 'bounty' || broker.commission_model === 'MODEL_BOUNTY'
                ? '<span class="badge badge-bounty">$500 Bounty</span>'
                : '<span class="badge badge-monthly">$50/month</span>';
            
            const dueAmount = parseFloat(broker.total_due_now || broker.commission_owed || 0);
            const earnedTotal = parseFloat(broker.total_earned || 0);
            const paidTotal = parseFloat(broker.total_paid || 0);
            
            return `
                <tr class="hover:bg-gray-50 ${isOverdue ? 'bg-red-50' : ''} ${broker.needs_setup ? 'bg-yellow-50' : ''}">
                    <td>
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                                <span class="text-blue-600 font-semibold">${(broker.name || broker.broker_name || 'U').charAt(0).toUpperCase()}</span>
                            </div>
                            <div>
                                <div class="font-semibold">${broker.name || broker.broker_name || 'Unknown'}</div>
                                <div class="text-sm" style="color: var(--muted);">${broker.email || broker.broker_email || 'N/A'}</div>
                            </div>
                        </div>
                    </td>
                    <td>${commissionBadge}</td>
                    <td class="font-semibold" style="color: var(--success);">$${dueAmount.toFixed(2)}</td>
                    <td style="color: var(--muted);">${paymentMethod}</td>
                    <td style="color: var(--muted);">${broker.next_payment_due || broker.next_payout_date ? new Date(broker.next_payment_due || broker.next_payout_date).toLocaleDateString() : '—'}</td>
                    <td>${overdueBadge}</td>
                    <td style="color: var(--muted); font-size: 0.875rem;">
                        Earned: $${earnedTotal.toFixed(2)}<br>
                        Paid: $${paidTotal.toFixed(2)}
                    </td>
                    <td>
                        <div class="flex gap-2 flex-wrap">
                            <button onclick="viewBrokerLedger('${broker.id}')" class="btn btn-outline btn-sm">
                                📊 Breakdown
                            </button>
                            <button onclick="showMarkPaidModal('${broker.id}', ${dueAmount.toFixed(2)})" class="btn btn-success btn-sm">
                                ✓ Mark Paid
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        
        safe.html('v2-ready-to-pay-list', html);
        safe.text('pending-badge', brokersWithDue.length.toString());
        safe.text('v2-pendingPayouts', brokersWithDue.length.toString());
        
        // Update overdue count
        const overdueCount = brokersWithDue.filter(b => (b.days_overdue || 0) > 0).length;
        safe.text('v2-overduePayments', overdueCount.toString());
        
        // Update summary stats if available
        if (data.summary) {
            safe.text('v2-totalCommissionOwed', `$${parseFloat(data.summary.total_commission_owed || 0).toFixed(2)}`);
        }
        
    } catch (error) {
        console.error('[Admin V2] Error loading ready to pay:', error);
        safe.html('v2-ready-to-pay-list', '<tr><td colspan="8" class="text-center py-8 text-red-500">Error: ' + error.message + '</td></tr>');
    }
}

// Load brokers on hold (total_on_hold > 0)
async function loadOnHold() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch('/api/admin/brokers-ready-to-pay');
        let brokers = data.brokers || data || [];
        
        if (!Array.isArray(brokers)) {
             console.warn('[Admin V2] On-hold brokers data is not an array, resetting to empty');
             brokers = [];
        }
        
        // Filter brokers with total_on_hold > 0
        const brokersOnHold = brokers.filter(b => parseFloat(b.total_on_hold || 0) > 0);
        
        if (brokersOnHold.length === 0) {
            safe.html('v2-on-hold-list', `
                <tr>
                    <td colspan="8" class="text-center py-12">
                        <div class="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 text-3xl">
                            ⏳
                        </div>
                        <p style="color: var(--muted);">No brokers on hold</p>
                    </td>
                </tr>
            `);
            safe.text('hold-badge', '0');
            return;
        }
        
        brokersOnHold.sort((a, b) => parseFloat(b.total_on_hold || 0) - parseFloat(a.total_on_hold || 0));
        
        const html = brokersOnHold.map(broker => {
            const methodNames = {
                'paypal': 'PayPal',
                'wise': 'Wise',
                'revolut': 'Revolut',
                'sepa': 'SEPA',
                'swift': 'SWIFT',
                'crypto': 'Crypto'
            };
            const paymentMethod = methodNames[broker.payment_method?.toLowerCase()] || broker.payment_method || 'Not Set';
            
            const commissionBadge = broker.commission_model === 'bounty' || broker.commission_model === 'MODEL_BOUNTY'
                ? '<span class="badge badge-bounty">$500 Bounty</span>'
                : '<span class="badge badge-monthly">$50/month</span>';
            
            const holdAmount = parseFloat(broker.total_on_hold || 0);
            const earnedTotal = parseFloat(broker.total_earned || 0);
            const paidTotal = parseFloat(broker.total_paid || 0);
            
            // Calculate days until eligible (if next_payout_date exists)
            let daysUntilEligible = '—';
            if (broker.next_payout_date) {
                const nextDate = new Date(broker.next_payout_date);
                const today = new Date();
                const days = Math.ceil((nextDate - today) / (1000 * 60 * 60 * 24));
                daysUntilEligible = days > 0 ? `${days} days` : 'Eligible now';
            }
            
            return `
                <tr class="hover:bg-gray-50">
                    <td>
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-yellow-100 flex items-center justify-center">
                                <span class="text-yellow-600 font-semibold">${(broker.name || broker.broker_name || 'U').charAt(0).toUpperCase()}</span>
                            </div>
                            <div>
                                <div class="font-semibold">${broker.name || broker.broker_name || 'Unknown'}</div>
                                <div class="text-sm" style="color: var(--muted);">${broker.email || broker.broker_email || 'N/A'}</div>
                            </div>
                        </div>
                    </td>
                    <td>${commissionBadge}</td>
                    <td class="font-semibold" style="color: var(--warning);">$${holdAmount.toFixed(2)}</td>
                    <td style="color: var(--muted);">${paymentMethod}</td>
                    <td style="color: var(--muted);">${daysUntilEligible}</td>
                    <td><span class="badge badge-pending">On Hold</span></td>
                    <td style="color: var(--muted); font-size: 0.875rem;">
                        Earned: $${earnedTotal.toFixed(2)}<br>
                        Paid: $${paidTotal.toFixed(2)}
                    </td>
                    <td>
                        <button onclick="viewBrokerLedger('${broker.id}')" class="btn btn-outline btn-sm">
                            📊 Breakdown
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        
        safe.html('v2-on-hold-list', html);
        safe.text('hold-badge', brokersOnHold.length.toString());
        
    } catch (error) {
        console.error('[Admin V2] Error loading on hold:', error);
        safe.html('v2-on-hold-list', '<tr><td colspan="8" class="text-center py-8 text-red-500">Error: ' + error.message + '</td></tr>');
    }
}

// View broker ledger breakdown
async function viewBrokerLedger(brokerId) {
    if (!ADMIN_API_KEY) return;
    
    try {
        const ledger = await adminFetch(`/api/admin/broker-ledger/${brokerId}`);
        
        // Populate modal
        safe.text('ledger-broker-name', ledger.broker_name || 'Unknown');
        safe.text('ledger-broker-email', ledger.broker_email || '—');
        safe.text('ledger-commission-model', ledger.commission_model === 'bounty' || ledger.commission_model === 'MODEL_BOUNTY' ? '$500 One-Time' : '$50/month Recurring');
        safe.text('ledger-total-earned', `$${parseFloat(ledger.total_earned || 0).toFixed(2)}`);
        safe.text('ledger-total-paid', `$${parseFloat(ledger.total_paid || 0).toFixed(2)}`);
        safe.text('ledger-total-due', `$${parseFloat(ledger.total_due_now || 0).toFixed(2)}`);
        safe.text('ledger-total-hold', `$${parseFloat(ledger.total_on_hold || 0).toFixed(2)}`);
        safe.text('ledger-next-payout', ledger.next_payout_date ? new Date(ledger.next_payout_date).toLocaleDateString() : '—');
        
        // Customer breakdown
        const customerBreakdown = ledger.customer_breakdown || {};
        const customerRows = Object.values(customerBreakdown).map(customer => {
            const statusBadge = {
                'ACTIVE': '<span class="badge badge-success">Active</span>',
                'CANCELED': '<span class="badge badge-error">Canceled</span>',
                'REFUNDED': '<span class="badge badge-error">Refunded</span>',
                'CHARGEBACK': '<span class="badge badge-error">Chargeback</span>',
                'PAST_DUE': '<span class="badge badge-warning">Past Due</span>'
            }[customer.status] || '<span class="badge badge-pending">Unknown</span>';
            
            return `
                <tr>
                    <td>${customer.customer_email || customer.customer_stripe_id || '—'}</td>
                    <td>${customer.commission_model === 'bounty' ? '$500' : '$50/month'}</td>
                    <td>${new Date(customer.last_payment_date).toLocaleDateString()}</td>
                    <td>$${parseFloat(customer.amount_earned || 0).toFixed(2)}</td>
                    <td>$${parseFloat(customer.amount_paid || 0).toFixed(2)}</td>
                    <td>$${parseFloat(customer.amount_due_now || 0).toFixed(2)}</td>
                    <td>$${parseFloat(customer.amount_on_hold || 0).toFixed(2)}</td>
                    <td>${statusBadge}</td>
                </tr>
            `;
        }).join('');
        
        safe.html('ledger-customer-breakdown', customerRows || '<tr><td colspan="8" class="text-center py-4" style="color: var(--muted);">No customers yet</td></tr>');
        
        // Store ledger data globally for batch creation
        window.currentLedgerBrokerId = brokerId;
        window.currentLedgerEvents = ledger.earning_events || [];
        
        // Earning events with checkboxes for DUE events
        const events = ledger.earning_events || [];
        const eventRows = events.map((event, index) => {
            const statusBadge = {
                'ACTIVE': event.is_eligible ? '<span class="badge badge-ready">DUE</span>' : '<span class="badge badge-pending">HELD</span>',
                'CANCELED': '<span class="badge badge-error">CANCELED</span>',
                'REFUNDED': '<span class="badge badge-error">REFUNDED</span>',
                'CHARGEBACK': '<span class="badge badge-error">CHARGEBACK</span>',
                'PAST_DUE': '<span class="badge badge-warning">PAST_DUE</span>'
            }[event.status] || '<span class="badge badge-pending">UNKNOWN</span>';
            
            const isSelectable = event.is_eligible && !event.is_paid && event.status === 'ACTIVE';
            const checkbox = isSelectable 
                ? `<input type="checkbox" class="event-checkbox" data-referral-id="${event.referral_id}" data-amount="${event.amount_due_now}" onchange="updateBatchSelection()">`
                : '<input type="checkbox" disabled>';
            
            return `
                <tr class="${isSelectable ? '' : 'opacity-50'}">
                    <td>${checkbox}</td>
                    <td>${event.customer_email || event.customer_stripe_id || '—'}</td>
                    <td>$${parseFloat(event.amount_earned || 0).toFixed(2)}</td>
                    <td>${new Date(event.payment_date).toLocaleDateString()}</td>
                    <td>${new Date(event.eligible_at).toLocaleDateString()}</td>
                    <td>${event.is_paid ? 'Yes' : 'No'}</td>
                    <td>${event.paid_at ? new Date(event.paid_at).toLocaleDateString() : '—'}</td>
                    <td>${statusBadge}</td>
                </tr>
            `;
        }).join('');
        
        safe.html('ledger-events-breakdown', eventRows || '<tr><td colspan="8" class="text-center py-4" style="color: var(--muted);">No earning events yet</td></tr>');
        
        // Reset selection summary
        document.getElementById('batch-selection-summary').classList.add('hidden');
        document.getElementById('select-all-events').checked = false;
        
        // Show modal
        document.getElementById('ledgerModal').classList.remove('hidden');
        
    } catch (error) {
        console.error('[Admin V2] Error loading broker ledger:', error);
        alert('❌ Error: ' + error.message);
    }
}

// Load payment history (reuses V1 API)
async function loadPaymentHistory() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const filter = document.getElementById('v2-payment-filter')?.value || 'all';
        const data = await adminFetch(`/api/admin/payment-history?time_filter=${filter}`);
        let payments = data.payments || [];
        
        if (!Array.isArray(payments)) {
             console.warn('[Admin V2] Payment history data is not an array, resetting to empty');
             payments = [];
        }
        
        if (payments.length === 0) {
            safe.html('v2-payment-history-table', `
                <tr>
                    <td colspan="7" class="text-center py-12">
                        <div class="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 text-3xl">
                            💸
                        </div>
                        <p style="color: var(--muted);">No payment history yet</p>
                    </td>
                </tr>
            `);
            safe.text('paid-badge', '0');
            return;
        }
        
        const html = payments.map(payment => {
            const date = new Date(payment.paid_at || payment.created_at);
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            
            const statusBadge = payment.status === 'completed'
                ? '<span class="badge badge-success">Completed</span>'
                : payment.status === 'failed' || payment.status === 'rejected'
                ? '<span class="badge badge-error">Failed</span>'
                : '<span class="badge badge-pending">Pending</span>';
            
            const methodNames = {
                'paypal': 'PayPal',
                'wise': 'Wise',
                'revolut': 'Revolut',
                'sepa': 'SEPA',
                'swift': 'SWIFT',
                'crypto': 'Crypto',
                'other': 'Other'
            };
            const methodName = methodNames[payment.payment_method?.toLowerCase()] || payment.payment_method || 'N/A';
            
            const notes = payment.notes || '';
            const notesDisplay = notes.length > 30 ? notes.substring(0, 30) + '...' : notes;
            
            return `
                <tr class="hover:bg-gray-50">
                    <td style="color: var(--muted);">${dateStr}</td>
                    <td class="font-medium">${payment.broker_name || 'Unknown'}</td>
                    <td class="font-semibold">$${parseFloat(payment.amount || 0).toFixed(2)}</td>
                    <td style="color: var(--muted);">${methodName}</td>
                    <td class="font-mono text-xs" style="color: var(--muted);">${payment.transaction_id || 'N/A'}</td>
                    <td>${statusBadge}</td>
                    <td style="color: var(--muted);" title="${notes}">${notesDisplay || '—'}</td>
                </tr>
            `;
        }).join('');
        
        safe.html('v2-payment-history-table', html);
        safe.text('paid-badge', payments.length.toString());
        
        // Update total paid
        const totalPaid = payments
            .filter(p => p.status === 'completed')
            .reduce((sum, p) => sum + parseFloat(p.amount || 0), 0);
        safe.text('v2-totalPaid', `$${totalPaid.toFixed(2)}`);
        
    } catch (error) {
        console.error('[Admin V2] Error loading payment history:', error);
        safe.html('v2-payment-history-table', '<tr><td colspan="7" class="text-center py-8 text-red-500">Error: ' + error.message + '</td></tr>');
    }
}

// Load comprehensive analytics (reuses V1 API)
async function loadComprehensiveAnalytics() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const stats = await adminFetch('/api/admin/analytics/comprehensive');
        
        safe.text('v2-calc-today', (stats.calculations_today || 0).toString());
        safe.text('v2-calc-week', (stats.calculations_week || 0).toString());
        safe.text('v2-calc-month', (stats.calculations_month || 0).toString());
        safe.text('v2-calc-all', (stats.calculations_all || 0).toString());
        
        safe.text('v2-rev-today', `$${(stats.revenue_today || 0).toFixed(2)}`);
        safe.text('v2-rev-week', `$${(stats.revenue_week || 0).toFixed(2)}`);
        safe.text('v2-rev-month', `$${(stats.revenue_month || 0).toFixed(2)}`);
        safe.text('v2-rev-all', `$${(stats.revenue_all || 0).toFixed(2)}`);
        
        safe.text('v2-email-today', (stats.emails_today || 0).toString());
        safe.text('v2-email-week', (stats.emails_week || 0).toString());
        safe.text('v2-email-month', (stats.emails_month || 0).toString());
        safe.text('v2-email-all', (stats.emails_all || 0).toString());
        
    } catch (error) {
        console.error('[Admin V2] Error loading analytics:', error);
        // Show "—" on error
        safe.text('v2-calc-today', '—');
        safe.text('v2-rev-today', '—');
        safe.text('v2-email-today', '—');
    }
}

// Update live analytics (reuses V1 API)
async function updateLiveAnalytics() {
    try {
        const response = await fetch('/api/analytics/today');
        if (!response.ok) {
            safe.text('v2-pvToday', '—');
            safe.text('v2-uvToday', '—');
            safe.text('v2-calcToday', '—');
            safe.text('v2-paidToday', '—');
            return;
        }
        
        const data = await response.json();
        safe.text('v2-pvToday', data.pv || '0');
        safe.text('v2-uvToday', data.uv || '0');
        safe.text('v2-calcToday', data.calc || '0');
        safe.text('v2-paidToday', data.paid ? `$${parseFloat(data.paid).toFixed(2)}` : '$0');
        
    } catch (error) {
        console.error('[Admin V2] Error updating live analytics:', error);
        safe.text('v2-pvToday', '—');
        safe.text('v2-uvToday', '—');
        safe.text('v2-calcToday', '—');
        safe.text('v2-paidToday', '—');
    }
}

// Update all stats (reuses V1 API)
async function updateAllStats() {
    if (!ADMIN_API_KEY) return;
    
    try {
        try {
            const calcData = await adminFetch('/api/admin/calculations-today');
            safe.text('v2-calculationsToday', calcData.calculations_today || '0');
        } catch (e) {
            safe.text('v2-calculationsToday', '—');
        }
        
        // Set defaults for other stats
        safe.text('v2-todayRevenue', '$0');
        safe.text('v2-activeCustomers', '0');
        
    } catch (error) {
        console.error('[Admin V2] Error updating stats:', error);
        safe.text('v2-calculationsToday', '—');
    }
}

// ==================== REUSE EXISTING FUNCTIONS FROM V1 ====================
// These functions are copied from admin-dashboard.js to maintain compatibility

async function approveApplication(id, email, name, commissionModel) {
    if (!confirm(`Approve ${name} (${email}) with ${commissionModel === 'bounty' ? '$500 bounty' : '$50/month recurring'} commission?`)) {
        return;
    }
    
    if (!ADMIN_API_KEY) return;
    
    try {
        await adminFetch(`/api/admin/approve-partner/${id}`, {
            method: 'POST',
            body: JSON.stringify({
                commission_model: commissionModel || 'bounty'
            })
        });
        
        alert('✅ Application approved!');
        loadPartnerApplications();
        loadActiveBrokers();
        updateAllStats();
        
    } catch (error) {
        console.error('[Admin V2] Error approving application:', error);
        alert(`❌ Error: ${error.message || 'Network error occurred'}`);
    }
}

async function rejectApplication(id) {
    if (!confirm('Reject this application?')) {
        return;
    }
    
    if (!ADMIN_API_KEY) return;
    
    try {
        await adminFetch(`/api/admin/reject-partner/${id}`, {
            method: 'POST'
        });
        
        alert('❌ Application rejected');
        loadPartnerApplications();
        
    } catch (error) {
        console.error('[Admin V2] Error rejecting application:', error);
        alert('❌ Error: ' + error.message);
    }
}

async function deleteApplication(id) {
    if (!confirm('Permanently delete this application? This cannot be undone.')) {
        return;
    }
    
    if (!ADMIN_API_KEY) return;
    
    try {
        await adminFetch(`/api/admin/delete-partner/${id}`, {
            method: 'DELETE'
        });
        
        alert('✅ Application deleted successfully');
        loadPartnerApplications();
        
    } catch (error) {
        console.error('[Admin V2] Error deleting application:', error);
        alert('❌ Error: ' + error.message);
    }
}

async function deleteActiveBroker(brokerId) {
    if (!confirm('Delete this broker? This will also delete all their referrals and commission data. This cannot be undone.')) {
        return;
    }
    
    if (!ADMIN_API_KEY) return;
    
    try {
        await adminFetch(`/api/admin/delete-broker/${brokerId}`, {
            method: 'DELETE'
        });
        
        alert('✅ Broker deleted successfully');
        loadActiveBrokers();
        
    } catch (error) {
        console.error('[Admin V2] Error deleting broker:', error);
        alert('❌ Error: ' + error.message);
    }
}

async function viewBrokerPaymentInfo(brokerId, brokerName, brokerEmail) {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch(`/api/admin/broker-payment-info/${brokerId}`);
        const paymentInfo = data.payment_info || {};
        const broker = data.broker || {};
        
        const methodNames = {
            'paypal': 'PayPal',
            'wise': 'Wise (TransferWise)',
            'revolut': 'Revolut',
            'sepa': 'SEPA Transfer (Europe)',
            'swift': 'SWIFT/Wire Transfer',
            'crypto': 'Cryptocurrency'
        };
        const paymentMethod = methodNames[paymentInfo.payment_method?.toLowerCase()] || paymentInfo.payment_method || 'Not Set';
        
        let paymentDetailsHTML = '';
        if (paymentInfo.payment_method === 'paypal' || paymentInfo.payment_method === 'wise' || paymentInfo.payment_method === 'revolut') {
            paymentDetailsHTML = `<div class="mb-4"><label class="block text-sm font-medium mb-1">Payment Email:</label><p class="font-mono">${paymentInfo.payment_email || 'Not provided'}</p></div>`;
        } else if (paymentInfo.payment_method === 'sepa') {
            paymentDetailsHTML = `
                <div class="mb-4"><label class="block text-sm font-medium mb-1">IBAN:</label><p class="font-mono">${paymentInfo.iban || 'Not provided'}</p></div>
                <div class="mb-4"><label class="block text-sm font-medium mb-1">BIC/SWIFT Code:</label><p class="font-mono">${paymentInfo.swift_code || 'Not provided'}</p></div>
                <div class="mb-4"><label class="block text-sm font-medium mb-1">Bank Name:</label><p>${paymentInfo.bank_name || 'Not provided'}</p></div>
            `;
        } else if (paymentInfo.payment_method === 'crypto') {
            paymentDetailsHTML = `<div class="mb-4"><label class="block text-sm font-medium mb-1">Wallet Address:</label><p class="font-mono break-all">${paymentInfo.crypto_wallet || 'Not provided'}</p></div>`;
        }
        
        const contentHTML = `
            <div class="space-y-4">
                <div><label class="block text-sm font-medium mb-1">Broker Name:</label><p class="font-semibold">${broker.name || brokerName || 'Unknown'}</p></div>
                <div><label class="block text-sm font-medium mb-1">Email:</label><p>${broker.email || brokerEmail || 'Not provided'}</p></div>
                <div class="border-t pt-4"><label class="block text-sm font-medium mb-1">Payment Method:</label><p class="font-semibold text-lg">${paymentMethod}</p></div>
                ${paymentDetailsHTML}
                <div class="border-t pt-4"><label class="block text-sm font-medium mb-1">Tax ID:</label><p>${paymentInfo.tax_id || 'Not provided'}</p></div>
            </div>
        `;
        
        safe.html('payment-info-content', contentHTML);
        document.getElementById('paymentInfoModal').classList.remove('hidden');
        
    } catch (error) {
        console.error('[Admin V2] Error loading payment info:', error);
        alert('❌ Error: ' + error.message);
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
    }
}

function showMarkPaidModal(brokerId, amount) {
    document.getElementById('paid-broker-id').value = brokerId;
    if (amount) {
        document.getElementById('paid-amount').value = amount.toFixed(2);
    }
    document.getElementById('markPaidModal').classList.remove('hidden');
}

async function handleMarkPaid(e) {
    e.preventDefault();
    
    const brokerId = document.getElementById('paid-broker-id').value;
    const amount = document.getElementById('paid-amount').value;
    const paymentMethod = document.getElementById('paid-method').value;
    const transactionId = document.getElementById('paid-transaction-id').value;
    const notes = document.getElementById('paid-notes').value;
    const confirm = document.getElementById('paid-confirm').checked;
    
    if (!confirm) {
        alert('Please confirm that payment was sent');
        return;
    }
    
    if (!ADMIN_API_KEY) return;
    
    try {
        const result = await adminFetch('/api/admin/mark-paid', {
            method: 'POST',
            body: JSON.stringify({
                broker_id: brokerId,
                amount: parseFloat(amount),
                payment_method: paymentMethod,
                transaction_id: transactionId,
                notes: notes
            })
        });
        const referralsMarked = result.referrals_marked || 0;
        const paidReferralIds = result.paid_referral_ids || [];
        
        alert(`✅ Payment marked as paid successfully\n${referralsMarked} referral(s) marked as paid`);
        closeModal('markPaidModal');
        loadPaymentHistory();
        loadReadyToPay();
        loadOnHold(); // Refresh on hold tab
        document.getElementById('mark-paid-form').reset();
        
    } catch (error) {
        console.error('[Admin V2] Error marking payment as paid:', error);
        alert('❌ Error: ' + error.message);
    }
}

async function exportPaymentHistory() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const filter = document.getElementById('v2-payment-filter')?.value || 'all';
        const response = await adminFetch(`/api/admin/payment-history/export?time_filter=${filter}`);
        
        // Handle blob response for exports
        if (response instanceof Response) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `payment-history-${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
        }
        
    } catch (error) {
        console.error('[Admin V2] Error exporting payment history:', error);
        alert('❌ Error: ' + error.message);
    }
}

function exportApplications() {
    alert('Export CSV functionality - using same endpoint as V1');
    // TODO: Implement CSV export if endpoint exists
}

function approveAllPending() {
    alert('Approve all pending - functionality coming soon');
}

function payAllReady() {
    alert('Pay all ready - functionality coming soon');
}

function generateTestKey() {
    alert('Generate test key - functionality coming soon');
}

function runBackup() {
    alert('Run backup - functionality coming soon');
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/';
    }
}

// ==================== API KEY MANAGEMENT ====================

let currentCustomerId = null;

async function loadCustomers() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch('/api/admin/customers');
        const customers = data.customers || [];
        
        const tbody = document.getElementById('api-customers-list');
        if (!tbody) return;
        
        if (customers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8" style="color: var(--muted);">No customers found</td></tr>';
            return;
        }
        
        tbody.innerHTML = customers.map(customer => {
            const createdDate = customer.created_at ? new Date(customer.created_at).toLocaleDateString() : '—';
            const lastUsed = customer.last_used_at ? new Date(customer.last_used_at).toLocaleDateString() : 'Never';
            const statusBadge = customer.is_active 
                ? '<span class="badge badge-ready">Active</span>'
                : '<span class="badge badge-pending">Revoked</span>';
            
            return `
                <tr>
                    <td>${customer.email}</td>
                    <td>${customer.plan || '$299/month'}</td>
                    <td><code class="text-xs">${customer.api_key_masked || 'No key'}</code></td>
                    <td>${customer.api_calls_30d || 0}</td>
                    <td>${lastUsed}</td>
                    <td>${statusBadge}</td>
                    <td>${createdDate}</td>
                    <td>
                        <div class="flex gap-2">
                            ${customer.api_key_masked ? `<button onclick="viewApiKey(${customer.id})" class="btn btn-outline btn-xs">View</button>` : ''}
                            ${customer.is_active ? `
                                <button onclick="showRegenerateModal(${customer.id}, '${customer.email}')" class="btn btn-warning btn-xs">Regenerate</button>
                                <button onclick="showRevokeModal(${customer.id}, '${customer.email}')" class="btn btn-error btn-xs">Revoke</button>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('[Admin V2] Error loading customers:', error);
        const tbody = document.getElementById('api-customers-list');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-8 text-red-600">Error loading customers</td></tr>';
        }
    }
}

async function loadApiUsageStats() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch('/api/admin/api-usage-stats');
        const stats = data.stats || {};
        
        safe.text('api-calls-today', stats.total_calls_today || 0);
        safe.text('api-calls-week', stats.total_calls_week || 0);
        safe.text('api-calls-month', stats.total_calls_month || 0);
        safe.text('api-error-rate', `${stats.error_rate || 0}%`);
        
        // Most used states
        const statesContainer = document.getElementById('api-most-used-states');
        if (statesContainer && stats.most_used_states) {
            statesContainer.innerHTML = stats.most_used_states.map(state => 
                `<span class="badge badge-ready">${state.state}: ${state.count}</span>`
            ).join('');
        }
    } catch (error) {
        console.error('[Admin V2] Error loading API usage stats:', error);
    }
}

async function viewApiKey(customerId) {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch(`/api/admin/customer/${customerId}/api-key`);
        
        const content = document.getElementById('api-key-content');
        if (content) {
            content.innerHTML = `
                <div>
                    <label class="block text-sm font-medium mb-2">API Key</label>
                    <div class="bg-gray-100 p-3 rounded-lg">
                        <code id="full-api-key" class="text-sm break-all">${data.api_key}</code>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-1">Total Calls</label>
                        <div class="text-lg font-semibold">${data.calls_count || 0}</div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">Last Used</label>
                        <div class="text-sm">${data.last_used_at ? new Date(data.last_used_at).toLocaleString() : 'Never'}</div>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-1">Created</label>
                        <div class="text-sm">${data.created_at ? new Date(data.created_at).toLocaleString() : '—'}</div>
                    </div>
                </div>
            `;
        }
        
        currentCustomerId = customerId;
        document.getElementById('viewApiKeyModal').classList.remove('hidden');
    } catch (error) {
        console.error('[Admin V2] Error viewing API key:', error);
        alert('Error loading API key: ' + error.message);
    }
}

function copyApiKey() {
    const apiKeyEl = document.getElementById('full-api-key');
    if (apiKeyEl) {
        navigator.clipboard.writeText(apiKeyEl.textContent).then(() => {
            alert('✅ API key copied to clipboard');
        }).catch(err => {
            console.error('Failed to copy:', err);
            alert('Failed to copy API key');
        });
    }
}

function showRegenerateModal(customerId, email) {
    currentCustomerId = customerId;
    document.getElementById('regenerate-customer-email').textContent = email;
    document.getElementById('regenerateApiKeyModal').classList.remove('hidden');
}

function showRevokeModal(customerId, email) {
    currentCustomerId = customerId;
    document.getElementById('revoke-customer-email').textContent = email;
    document.getElementById('revokeApiKeyModal').classList.remove('hidden');
}

async function confirmRegenerateApiKey() {
    if (!currentCustomerId) return;
    
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch(`/api/admin/customer/${currentCustomerId}/regenerate-key`, {
            method: 'POST'
        });
        alert('✅ API key regenerated successfully. Customer has been notified via email.');
        closeModal('regenerateApiKeyModal');
        loadCustomers();
    } catch (error) {
        console.error('[Admin V2] Error regenerating API key:', error);
        alert('Error regenerating API key: ' + error.message);
    }
}

async function confirmRevokeApiKey() {
    if (!currentCustomerId) return;
    
    if (!ADMIN_API_KEY) return;
    
    try {
        await adminFetch(`/api/admin/customer/${currentCustomerId}/revoke-key`, {
            method: 'POST'
        });
        
        alert('✅ API access revoked successfully. Customer has been notified via email.');
        closeModal('revokeApiKeyModal');
        loadCustomers();
    } catch (error) {
        console.error('[Admin V2] Error revoking API key:', error);
        alert('Error revoking API key: ' + error.message);
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
    currentCustomerId = null;
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing Admin Dashboard V2...');
    
    // Load all data
    loadPartnerApplications();
    loadActiveBrokers();
    loadReadyToPay();
    loadOnHold();
    loadPaymentHistory();
    loadComprehensiveAnalytics();
    updateAllStats();
    updateLiveAnalytics();
    loadCustomers();
    loadApiUsageStats();
    
    // Auto-refresh every 60 seconds
    setInterval(() => {
        loadPartnerApplications();
        loadActiveBrokers();
        loadReadyToPay();
        loadOnHold();
        loadPaymentHistory();
        updateAllStats();
        updateLiveAnalytics();
        loadCustomers();
        loadApiUsageStats();
    }, 60000);
    
    console.log('✅ Admin Dashboard V2 ready');
    
    // Load debug panel data if panel is expanded
    if (!document.getElementById('debug-panel-content').classList.contains('hidden')) {
        loadPayoutDebugData();
    }
});

// Toggle debug panel
function toggleDebugPanel() {
    const content = document.getElementById('debug-panel-content');
    const toggle = document.getElementById('debug-panel-toggle');
    
    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        toggle.textContent = '▲';
        loadPayoutDebugData();
    } else {
        content.classList.add('hidden');
        toggle.textContent = '▼';
    }
}

// Load payout debug data
async function loadPayoutDebugData() {
    if (!ADMIN_API_KEY) return;
    
    try {
        const data = await adminFetch('/api/admin/debug/payout-data');
        
        // Render referrals
        const referrals = data.referrals || [];
        if (referrals.length === 0) {
            safe.html('debug-referrals-table', '<tr><td colspan="12" class="text-center py-4" style="color: var(--muted);">0 rows</td></tr>');
        } else {
            const referralsRows = referrals.map(ref => `
                <tr>
                    <td>${ref.id || '—'}</td>
                    <td>${ref.broker_id || '—'}</td>
                    <td>${ref.customer_email || '—'}</td>
                    <td>${ref.customer_stripe_id || '—'}</td>
                    <td>${ref.subscription_id || '—'}</td>
                    <td><span class="badge badge-${ref.status === 'paid' ? 'success' : ref.status === 'active' ? 'ready' : 'pending'}">${ref.status || '—'}</span></td>
                    <td>${ref.payment_date ? new Date(ref.payment_date).toLocaleDateString() : '—'}</td>
                    <td>$${parseFloat(ref.payout || 0).toFixed(2)}</td>
                    <td>${ref.payout_type || '—'}</td>
                    <td>${ref.created_at ? new Date(ref.created_at).toLocaleDateString() : '—'}</td>
                    <td>${ref.paid_at ? new Date(ref.paid_at).toLocaleDateString() : '—'}</td>
                    <td>${ref.paid_batch_id || '—'}</td>
                </tr>
            `).join('');
            safe.html('debug-referrals-table', referralsRows);
        }
        
        // Render payments
        const payments = data.payments || [];
        if (payments.length === 0) {
            safe.html('debug-payments-table', '<tr><td colspan="10" class="text-center py-4" style="color: var(--muted);">0 rows</td></tr>');
        } else {
            const paymentsRows = payments.map(pay => `
                <tr>
                    <td>${pay.id || '—'}</td>
                    <td>${pay.broker_id || '—'}</td>
                    <td>${pay.broker_name || '—'}</td>
                    <td>${pay.broker_email || '—'}</td>
                    <td>$${parseFloat(pay.amount || 0).toFixed(2)}</td>
                    <td>${pay.payment_method || '—'}</td>
                    <td>${pay.transaction_id || '—'}</td>
                    <td><span class="badge badge-${pay.status === 'completed' ? 'success' : 'pending'}">${pay.status || '—'}</span></td>
                    <td>${pay.created_at ? new Date(pay.created_at).toLocaleDateString() : '—'}</td>
                    <td>${pay.paid_at ? new Date(pay.paid_at).toLocaleDateString() : '—'}</td>
                </tr>
            `).join('');
            safe.html('debug-payments-table', paymentsRows);
        }
        
        // Render batches
        const batches = data.batches || [];
        if (batches.length === 0) {
            safe.html('debug-batches-table', '<tr><td colspan="10" class="text-center py-4" style="color: var(--muted);">0 rows</td></tr>');
        } else {
            const batchesRows = batches.map(batch => `
                <tr>
                    <td>${batch.id || '—'}</td>
                    <td>${batch.broker_id || '—'}</td>
                    <td>${batch.broker_name || '—'}</td>
                    <td>${batch.broker_email || '—'}</td>
                    <td>$${parseFloat(batch.total_amount || 0).toFixed(2)}</td>
                    <td>${batch.payment_method || '—'}</td>
                    <td>${batch.transaction_id || '—'}</td>
                    <td><span class="badge badge-${batch.status === 'completed' ? 'success' : 'pending'}">${batch.status || '—'}</span></td>
                    <td>${batch.created_at ? new Date(batch.created_at).toLocaleDateString() : '—'}</td>
                    <td>${batch.paid_at ? new Date(batch.paid_at).toLocaleDateString() : '—'}</td>
                </tr>
            `).join('');
            safe.html('debug-batches-table', batchesRows);
        }
        
    } catch (error) {
        console.error('[Admin V2] Error loading debug data:', error);
        safe.html('debug-referrals-table', '<tr><td colspan="12" class="text-center py-4 text-red-500">Error: ' + error.message + '</td></tr>');
        safe.html('debug-payments-table', '<tr><td colspan="10" class="text-center py-4 text-red-500">Error: ' + error.message + '</td></tr>');
        safe.html('debug-batches-table', '<tr><td colspan="10" class="text-center py-4 text-red-500">Error: ' + error.message + '</td></tr>');
    }
}

window.toggleDebugPanel = toggleDebugPanel;
window.loadPayoutDebugData = loadPayoutDebugData;

// Make functions globally available
window.switchPayoutTab = switchPayoutTab;
window.approveApplication = approveApplication;
window.rejectApplication = rejectApplication;
window.deleteApplication = deleteApplication;
window.deleteActiveBroker = deleteActiveBroker;
window.viewBrokerPaymentInfo = viewBrokerPaymentInfo;
window.closeModal = closeModal;
window.handleMarkPaid = handleMarkPaid;
window.showMarkPaidModal = showMarkPaidModal;
window.viewBrokerLedger = viewBrokerLedger;
window.loadOnHold = loadOnHold;
window.switchPayoutTab = switchPayoutTab;
window.exportPaymentHistory = exportPaymentHistory;

// Batch selection functions
function updateBatchSelection() {
    const checkboxes = document.querySelectorAll('.event-checkbox:checked');
    const count = checkboxes.length;
    let total = 0;
    
    checkboxes.forEach(cb => {
        total += parseFloat(cb.getAttribute('data-amount') || 0);
    });
    
    const summaryDiv = document.getElementById('batch-selection-summary');
    if (count > 0) {
        summaryDiv.classList.remove('hidden');
        safe.text('selected-count', count.toString());
        safe.text('selected-total', `$${total.toFixed(2)}`);
    } else {
        summaryDiv.classList.add('hidden');
    }
}

function selectAllDueEvents() {
    const checkboxes = document.querySelectorAll('.event-checkbox:not(:disabled)');
    checkboxes.forEach(cb => {
        cb.checked = true;
    });
    document.getElementById('select-all-events').checked = true;
    updateBatchSelection();
}

function clearSelection() {
    const checkboxes = document.querySelectorAll('.event-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = false;
    });
    document.getElementById('select-all-events').checked = false;
    updateBatchSelection();
}

function toggleAllEvents(checked) {
    const checkboxes = document.querySelectorAll('.event-checkbox:not(:disabled)');
    checkboxes.forEach(cb => {
        cb.checked = checked;
    });
    updateBatchSelection();
}

async function createBatchFromSelection() {
    const checkboxes = document.querySelectorAll('.event-checkbox:checked');
    const referralIds = Array.from(checkboxes).map(cb => parseInt(cb.getAttribute('data-referral-id')));
    
    if (referralIds.length === 0) {
        alert('Please select at least one DUE earning event');
        return;
    }
    
    const brokerId = window.currentLedgerBrokerId;
    if (!brokerId) {
        alert('Error: Broker ID not found');
        return;
    }
    
    // Get payment method from broker info (or prompt)
    const paymentMethod = prompt('Enter payment method (paypal, wise, revolut, sepa, swift, crypto):', 'wise');
    if (!paymentMethod) {
        return;
    }
    
    const transactionId = prompt('Enter transaction ID (or leave blank to auto-generate):', '') || '';
    const notes = prompt('Enter notes (optional):', '') || '';
    
    if (!ADMIN_API_KEY) return;
    
    try {
        const result = await adminFetch('/api/admin/payout-batches/create', {
            method: 'POST',
            body: JSON.stringify({
                broker_id: brokerId,
                referral_ids: referralIds,
                payment_method: paymentMethod,
                transaction_id: transactionId,
                notes: notes
            })
        });
        alert(`✅ Batch created successfully!\n\nBatch ID: ${result.batch_id}\nTransaction ID: ${result.transaction_id}\nTotal: $${result.total_amount.toFixed(2)}\nReferrals marked: ${result.referrals_marked}`);
        
        // Close modal and refresh tabs
        closeModal('ledgerModal');
        loadReadyToPay();
        loadOnHold();
        loadPaymentHistory();
        
    } catch (error) {
        console.error('[Admin V2] Error creating batch:', error);
        alert('❌ Error: ' + error.message);
    }
}

window.updateBatchSelection = updateBatchSelection;
window.selectAllDueEvents = selectAllDueEvents;
window.clearSelection = clearSelection;
window.toggleAllEvents = toggleAllEvents;
window.createBatchFromSelection = createBatchFromSelection;
window.exportApplications = exportApplications;
window.approveAllPending = approveAllPending;
window.payAllReady = payAllReady;
window.generateTestKey = generateTestKey;
window.runBackup = runBackup;
window.logout = logout;

