// ==================== ENHANCED SAFETY ====================
console.log('🛡️ Admin Dashboard Loading...');

// 1. Define missing global that old code expects
window.API_BASE = window.API_BASE || '/api';

// 2. Admin credentials (from environment or defaults)
const ADMIN_USER = window.ADMIN_USER || 'admin';
const ADMIN_PASS = window.ADMIN_PASS || 'LienAPI2025';

// 3. Enhanced safe functions
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
            console.log(`[Safe] Set #${id} text: ${text}`);
        }
    },
    
    html: function(id, html) {
        const el = this.get(id);
        if (el) {
            el.innerHTML = html;
            console.log(`[Safe] Set #${id} HTML`);
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

// 4. Load partner applications from real API
async function loadPartnerApplications() {
    try {
        console.log('[Admin] Loading partner applications from /api/admin/partner-applications...');
        
        // Fetch with authentication - only get pending applications
        const response = await fetch('/api/admin/partner-applications?status=pending', {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            console.error(`[Admin] API error: ${response.status}`);
            safe.html('applicationsTable', `
                <tr>
                    <td colspan="6" class="text-center py-8 text-red-500">
                        Error loading applications: ${response.status}
                    </td>
                </tr>
            `);
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Received data:', data);
        
        const container = safe.get('applicationsTable');
        if (!container) {
            console.warn('[Admin] applicationsTable element not found');
            return;
        }
        
        // Handle different response formats and filter to only pending
        let applications = data.applications || data || [];
        // Double-check: only show pending applications
        applications = applications.filter(app => app.status === 'pending' || !app.status);
        
        if (!Array.isArray(applications) || applications.length === 0) {
            safe.html('applicationsTable', `
                <tr>
                    <td colspan="6" class="text-center py-12">
                        <div class="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mb-4 text-3xl">
                            📋
                        </div>
                        <h3 class="text-lg font-semibold mb-2 text-gray-900">No Applications Yet</h3>
                        <p class="text-gray-600 mb-4">Partner applications will appear here when submitted</p>
                        <a href="/partners.html" class="text-blue-600 hover:underline inline-block">
                            View Partner Program →
                        </a>
                    </td>
                </tr>
            `);
            
            // Update pending count
            safe.text('pendingCount', '0');
            safe.text('pendingAppsCount', '0');
            return;
        }
        
        // Render applications
        const html = applications.map(app => {
            const commissionBadge = app.commission_model === 'bounty' 
                ? '<span class="px-3 py-1 rounded-full text-sm bg-purple-100 text-purple-800">$500 Bounty</span>'
                : '<span class="px-3 py-1 rounded-full text-sm bg-green-100 text-green-800">$50/month</span>';
            
            const statusBadge = app.status === 'approved'
                ? '<span class="px-3 py-1 rounded-full text-sm bg-green-100 text-green-800">Approved</span>'
                : app.status === 'rejected'
                ? '<span class="px-3 py-1 rounded-full text-sm bg-red-100 text-red-800">Rejected</span>'
                : '<span class="px-3 py-1 rounded-full text-sm bg-yellow-100 text-yellow-800">Pending</span>';
            
            // Format date
            let dateStr = 'Recently';
            if (app.created_at || app.applied_at || app.timestamp) {
                try {
                    const date = new Date(app.created_at || app.applied_at || app.timestamp);
                    dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
                } catch (e) {
                    dateStr = 'Recently';
                }
            }
            
            const actionButtons = app.status === 'pending' ? `
                <button type="button" class="approve-btn px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg text-sm mr-2" data-app-id="${app.id}" data-email="${app.email || ''}" data-name="${(app.name || 'Unknown').replace(/"/g, '&quot;')}" data-commission-model="${app.commission_model || 'bounty'}">
                    Approve
                </button>
                <button type="button" class="reject-btn px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg text-sm mr-2" data-app-id="${app.id}">
                    Reject
                </button>
                <button type="button" class="delete-btn px-3 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg text-sm" data-app-id="${app.id}" title="Delete application">
                    Delete
                </button>
            ` : `
                <span class="text-gray-500 text-sm">${app.status === 'approved' ? '✅ Approved' : '❌ Rejected'}</span>
            `;
            
            return `
                <tr class="border-b hover:bg-gray-50" data-app-id="${app.id}">
                    <td class="py-3 px-4">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                                <span class="text-blue-600 font-semibold">${(app.name || 'U').charAt(0).toUpperCase()}</span>
                            </div>
                            <div>
                                <div class="font-semibold text-gray-900">${app.name || 'Unknown'}</div>
                                <div class="text-sm text-gray-600">${app.email || ''}</div>
                            </div>
                        </div>
                    </td>
                    <td class="py-3 px-4">${commissionBadge}</td>
                    <td class="py-3 px-4 text-gray-900">${app.company || 'N/A'}</td>
                    <td class="py-3 px-4 text-sm text-gray-600">${dateStr}</td>
                    <td class="py-3 px-4">${statusBadge}</td>
                    <td class="py-3 px-4">${actionButtons}</td>
                </tr>
            `;
        }).join('');
        
        safe.html('applicationsTable', html);
        
        // Update pending count
        const pendingCount = applications.filter(app => app.status === 'pending' || !app.status).length;
        safe.text('pendingCount', pendingCount.toString());
        safe.text('pendingAppsCount', pendingCount.toString());
        
        console.log(`✅ Loaded ${applications.length} applications (${pendingCount} pending)`);
        
    } catch (error) {
        console.error('[Admin] Error loading applications:', error);
        safe.html('applicationsTable', `
            <tr>
                <td colspan="6" class="text-center py-8 text-red-500">
                    Error: ${error.message}
                </td>
            </tr>
        `);
    }
}

// ONE handler only. Remove any other click listeners for approve/reject/delete.
window.addEventListener(
  "click",
  async (e) => {
    const btn =
      e.target.closest(".approve-btn") ||
      e.target.closest(".reject-btn") ||
      e.target.closest(".delete-btn") ||
      e.target.closest(".delete-broker-btn") ||
      e.target.closest(".view-payment-btn");

    if (!btn) return;

    // HARD STOP: prevent *anything* else from canceling the request
    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const appId = btn.dataset.appId;
    const brokerId = btn.dataset.brokerId;

    const auth = window.ADMIN_BASIC_AUTH
      ? { Authorization: window.ADMIN_BASIC_AUTH }
      : { Authorization: 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`) };

    // Handle view payment info button FIRST (before other handlers)
    if (btn.classList.contains("view-payment-btn")) {
      const brokerId = btn.dataset.brokerId;
      const brokerName = btn.dataset.brokerName || 'Unknown';
      const brokerEmail = btn.dataset.brokerEmail || '';
      await viewBrokerPaymentInfo(brokerId, brokerName, brokerEmail);
      return;
    }

    // Disable button to prevent double clicks
    btn.disabled = true;

    try {
      let url = "";
      let method = "POST";

      if (btn.classList.contains("approve-btn")) {
        url = `/api/admin/approve-partner/${appId}`;
        method = "POST";
      } else if (btn.classList.contains("reject-btn")) {
        url = `/api/admin/reject-partner/${appId}`;
        method = "POST";
      } else if (btn.classList.contains("delete-btn")) {
        url = `/api/admin/delete-partner/${appId}`;
        method = "DELETE";
      } else if (btn.classList.contains("delete-broker-btn")) {
        url = `/api/admin/delete-broker/${brokerId}`;
        method = "DELETE";
      }

      if (!url.includes("/")) throw new Error("Missing id on button");

      console.log("[ADMIN] sending:", method, url);

      const r = await fetch(url, {
        method,
        headers: { ...auth },
        credentials: "include",
        keepalive: true, // <-- IMPORTANT: request continues even if page navigates/reloads
        cache: "no-store",
      });

      const text = await r.text();
      console.log("[ADMIN] response:", r.status, text);

      if (!r.ok) throw new Error(text || `HTTP ${r.status}`);

      alert("✅ Success");

      // Refresh UI
      if (typeof loadPartnerApplications === "function") loadPartnerApplications();
      if (typeof loadActiveBrokers === "function") loadActiveBrokers();
    } catch (err) {
      console.error(err);
      alert("❌ " + (err?.message || err));
    } finally {
      btn.disabled = false;
    }
  },
  true // <-- capture phase: runs before anything else
);

// 5. Approve application (kept for backward compatibility, but now handled by event delegation)
async function approveApplication(id, email, name, commissionModel) {
    if (!confirm(`Approve ${name} (${email}) with ${commissionModel === 'bounty' ? '$500 bounty' : '$50/month recurring'} commission?`)) {
        return;
    }
    
    const url = `/api/admin/approve-partner/${id}`;
    console.log(`[Admin] Approving application ${id} via ${url}`);
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            },
            body: JSON.stringify({
                commission_model: commissionModel || 'bounty'
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            let errorDetail = 'Failed to approve application';
            try {
                const errorJson = JSON.parse(errorText);
                errorDetail = errorJson.detail || errorJson.error || errorDetail;
            } catch {
                errorDetail = errorText || `HTTP ${response.status}`;
            }
            console.error(`[Admin] Approve error: ${response.status}`, errorDetail);
            alert(`❌ Error (${response.status}): ${errorDetail}`);
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Approve response:', data);
        
        // Show success message with email status
        let message = `✅ Application approved!`;
        if (data.email_sent) {
            message += `\n📧 Welcome email sent via ${data.email_channel || 'email'}`;
        } else if (data.email_error) {
            message += `\n⚠️ Email failed: ${data.email_error}`;
        }
        alert(message);
        
        // Optimistic UI update - remove row immediately
        const row = document.querySelector(`tr[data-app-id="${id}"]`);
        if (row) {
            row.remove();
        }
        
        // Refresh lists and stats
        loadPartnerApplications(); // Refresh pending applications
        loadActiveBrokers(); // Refresh brokers list
        updateAllStats(); // Update stats
        
    } catch (error) {
        console.error('[Admin] Error approving application:', error);
        alert(`❌ Error: ${error.message || 'Network error occurred'}`);
    }
}

// 6. Reject application
async function rejectApplication(id) {
    if (!confirm('Reject this application?')) {
        return;
    }
    
    try {
        console.log(`[Admin] Rejecting application ${id}...`);
        
        const response = await fetch(`/api/admin/reject-partner/${id}`, {
            method: 'POST',
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            console.error(`[Admin] Reject error: ${response.status}`, errorData);
            alert('❌ Error: ' + (errorData.detail || 'Failed to reject application'));
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Reject response:', data);
        
        if (data.success) {
            alert('❌ Application rejected');
            loadPartnerApplications(); // Refresh list
        } else {
            alert('❌ Error: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('[Admin] Error rejecting application:', error);
        alert('❌ Error: ' + error.message);
    }
}

// 7. Update all stats
async function updateAllStats() {
    try {
        // Calculations
        const calcResponse = await fetch('/api/admin/calculations-today', {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        const calcData = await calcResponse.json();
        safe.text('calculationsToday', calcData.calculations_today || '0');
        
        // Revenue and other stats
        safe.text('todayRevenue', '$0');
        safe.text('activeCustomers', '0');
        safe.text('pendingPayouts', '$0');
        
        console.log('[Admin] Stats updated');
        
    } catch (error) {
        console.log('[Admin] Stats error:', error);
    }
}

// 7b. Update Live Analytics
async function updateLiveAnalytics() {
    try {
        console.log('[Admin] Fetching Live Analytics from /api/analytics/today...');
        
        const response = await fetch('/api/analytics/today');
        
        if (!response.ok) {
            console.error(`[Admin] Analytics API error: ${response.status}`);
            safe.text('pvToday', '—');
            safe.text('uvToday', '—');
            safe.text('calcToday', '—');
            safe.text('paidToday', '—');
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Live Analytics data:', data);
        
        // Update Live Analytics section
        safe.text('pvToday', data.pv || '0');
        safe.text('uvToday', data.uv || '0');
        safe.text('calcToday', data.calc || '0');
        safe.text('paidToday', data.paid ? `$${parseFloat(data.paid).toFixed(2)}` : '$0');
        
        console.log('[Admin] Live Analytics updated');
        
    } catch (error) {
        console.error('[Admin] Error updating Live Analytics:', error);
        safe.text('pvToday', '—');
        safe.text('uvToday', '—');
        safe.text('calcToday', '—');
        safe.text('paidToday', '—');
    }
}

// 7c. Update Email Conversion section
async function updateEmailConversion() {
    try {
        console.log('[Admin] Fetching Email Conversion data from /api/admin/live-stats...');
        
        const response = await fetch('/api/admin/live-stats', {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            console.error(`[Admin] Live Stats API error: ${response.status}`);
            safe.text('totalCalcs', '0');
            safe.text('emailCaptures', '0');
            safe.text('upgradeClicks', '0');
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Email Conversion data:', data);
        
        // Update Email Conversion section
        const totalCalcs = data.total_calculations || data.calculations_today || 0;
        const emailCaptures = data.email_captures || 0;
        const upgradeClicks = data.upgrade_clicks || 0;
        
        safe.text('totalCalcs', totalCalcs.toString());
        safe.text('emailCaptures', emailCaptures.toString());
        safe.text('upgradeClicks', upgradeClicks.toString());
        
        // Update progress bars
        const calcBar = safe.get('calcBar');
        const emailBar = safe.get('emailBar');
        const upgradeBar = safe.get('upgradeBar');
        
        if (calcBar && totalCalcs > 0) {
            // Set bar width based on some max value (e.g., 100)
            const maxCalcs = 100;
            const calcPercent = Math.min((totalCalcs / maxCalcs) * 100, 100);
            calcBar.style.width = `${calcPercent}%`;
        }
        
        if (emailBar && totalCalcs > 0) {
            // Email conversion rate
            const emailPercent = (emailCaptures / totalCalcs) * 100;
            emailBar.style.width = `${Math.min(emailPercent, 100)}%`;
        }
        
        if (upgradeBar && totalCalcs > 0) {
            // Upgrade click rate
            const upgradePercent = (upgradeClicks / totalCalcs) * 100;
            upgradeBar.style.width = `${Math.min(upgradePercent, 100)}%`;
        }
        
        console.log('[Admin] Email Conversion updated');
        
    } catch (error) {
        console.error('[Admin] Error updating Email Conversion:', error);
        safe.text('totalCalcs', '0');
        safe.text('emailCaptures', '0');
        safe.text('upgradeClicks', '0');
    }
}

// 8. Initialize
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing dashboard...');
    
    // Hide elements that might not exist
    safe.hide('pendingBrokersList');
    safe.hide('flaggedReferralsList');
    safe.hide('testKeysList');
    safe.hide('pendingPayoutsList');
    
    // Load data
    loadPartnerApplications();
    loadActiveBrokers();
    loadReadyToPay();
    loadPaymentHistory();
    updateAllStats();
    updateLiveAnalytics();
    updateEmailConversion();
    loadComprehensiveAnalytics();
    
    // Auto-refresh
    setInterval(() => {
        loadPartnerApplications();
        loadActiveBrokers();
        loadReadyToPay();
        loadPaymentHistory();
        updateAllStats();
        updateLiveAnalytics();
        updateEmailConversion();
        loadComprehensiveAnalytics();
    }, 60000); // Refresh every 60 seconds
    
    console.log('✅ Dashboard ready');
});

// 8b. Load Active Brokers
async function loadActiveBrokers() {
    try {
        console.log('[Admin] Loading active brokers from /api/admin/brokers...');
        
        const response = await fetch('/api/admin/brokers', {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            console.error(`[Admin] Brokers API error: ${response.status}`);
            safe.hide('brokersList');
            safe.show('noBrokers');
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Brokers data:', data);
        
        // Handle different response formats
        const brokers = data.brokers || data || [];
        
        const brokersList = safe.get('brokersList');
        const noBrokers = safe.get('noBrokers');
        
        if (!brokers || brokers.length === 0) {
            safe.hide('brokersList');
            safe.show('noBrokers');
            safe.text('brokerCount', '0');
            return;
        }
        
        safe.hide('noBrokers');
        safe.show('brokersList');
        
        // Render brokers as table rows
        const html = brokers.map(broker => {
            const commissionBadge = broker.commission_model === 'bounty' || broker.model === 'bounty'
                ? '<span class="px-2 py-1 rounded text-xs bg-purple-100 text-purple-800">$500 Bounty</span>'
                : '<span class="px-2 py-1 rounded text-xs bg-green-100 text-green-800">$50/month</span>';
            
            // Payment method badge
            const paymentMethod = broker.payment_method || '';
            let paymentBadge = '<span class="px-2 py-1 rounded text-xs bg-gray-100 text-gray-600">Not Set ❌</span>';
            if (paymentMethod) {
                const methodIcons = {
                    'paypal': '💰',
                    'wise': '💸',
                    'revolut': '💳',
                    'sepa': '🇪🇺',
                    'swift': '🌍',
                    'crypto': '₿'
                };
                const icon = methodIcons[paymentMethod.toLowerCase()] || '💰';
                const methodNames = {
                    'paypal': 'PayPal',
                    'wise': 'Wise',
                    'revolut': 'Revolut',
                    'sepa': 'SEPA',
                    'swift': 'SWIFT',
                    'crypto': 'Crypto'
                };
                const name = methodNames[paymentMethod.toLowerCase()] || paymentMethod;
                paymentBadge = `<span class="px-2 py-1 rounded text-xs bg-blue-100 text-blue-800">${name} ${icon}</span>`;
            }
            
            // Payment status badge
            let paymentStatusBadge = '<span class="px-2 py-1 rounded text-xs bg-yellow-100 text-yellow-800">Pending</span>';
            if (broker.payment_status === 'active') {
                paymentStatusBadge = '<span class="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Active</span>';
            } else if (broker.payment_status === 'suspended') {
                paymentStatusBadge = '<span class="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Suspended</span>';
            } else if (broker.payment_status === 'pending_first_payment') {
                paymentStatusBadge = '<span class="px-2 py-1 rounded text-xs bg-blue-100 text-blue-800">First Payment</span>';
            }
            
            // Last payment date
            const lastPaymentDate = broker.last_payment_date 
                ? new Date(broker.last_payment_date).toLocaleDateString()
                : 'Never';
            
            // Total paid
            const totalPaid = broker.total_paid ? `$${parseFloat(broker.total_paid).toFixed(2)}` : '$0.00';
            
            return `
                <tr class="hover:bg-gray-50">
                    <td class="py-3 px-6 text-sm font-medium text-gray-900">${broker.name || 'Unknown'}</td>
                    <td class="py-3 px-6 text-sm text-gray-600">${broker.email || 'N/A'}</td>
                    <td class="py-3 px-6 text-sm">${commissionBadge}</td>
                    <td class="py-3 px-6 text-sm">${paymentBadge}</td>
                    <td class="py-3 px-6 text-sm">${paymentStatusBadge}</td>
                    <td class="py-3 px-6 text-sm text-gray-600">${lastPaymentDate}</td>
                    <td class="py-3 px-6 text-sm font-semibold text-green-600">${totalPaid}</td>
                    <td class="py-3 px-6 text-sm">
                        <div class="flex gap-2">
                            <button onclick="viewBrokerPaymentInfo(${broker.id}, '${(broker.name || 'Unknown').replace(/'/g, "\\'")}', '${(broker.email || '').replace(/'/g, "\\'")}')" class="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-xs">
                                View
                            </button>
                            <button onclick="deleteActiveBroker(${broker.id})" class="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 text-xs">
                                Delete
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        
        safe.html('brokersList', html);
        safe.text('brokerCount', brokers.length.toString());
        
        console.log(`✅ Loaded ${brokers.length} brokers`);
        
    } catch (error) {
        console.error('[Admin] Error loading brokers:', error);
        safe.hide('brokersList');
        safe.show('noBrokers');
    }
}

// 8c. Delete active broker
async function deleteActiveBroker(brokerId) {
    if (!confirm('Delete this broker? This will also delete all their referrals and commission data. This cannot be undone.')) {
        return;
    }
    
    try {
        console.log(`[Admin] Deleting broker ${brokerId}...`);
        
        const response = await fetch(`/api/admin/delete-broker/${brokerId}`, {
            method: 'DELETE',
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            console.error(`[Admin] Delete broker error: ${response.status}`, errorData);
            alert('❌ Error: ' + (errorData.detail || 'Failed to delete broker'));
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Delete broker response:', data);
        
        if (data.success) {
            alert('✅ Broker deleted successfully');
            loadActiveBrokers(); // Refresh list
        } else {
            alert('❌ Error: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('[Admin] Error deleting broker:', error);
        alert('❌ Error: ' + error.message);
    }
}

// 8d. Delete application
async function deleteApplication(id) {
    if (!confirm('Permanently delete this application? This cannot be undone.')) {
        return;
    }
    
    try {
        console.log(`[Admin] Deleting application ${id}...`);
        
        const response = await fetch(`/api/admin/delete-partner/${id}`, {
            method: 'DELETE',
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            console.error(`[Admin] Delete error: ${response.status}`, errorData);
            alert('❌ Error: ' + (errorData.detail || 'Failed to delete application'));
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Delete response:', data);
        
        if (data.success) {
            alert('✅ Application deleted successfully');
            loadPartnerApplications(); // Refresh list
        } else {
            alert('❌ Error: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('[Admin] Error deleting application:', error);
        alert('❌ Error: ' + error.message);
    }
}

// 8e. Load Comprehensive Analytics
async function loadComprehensiveAnalytics() {
    try {
        console.log('[Admin] Loading comprehensive analytics...');
        
        const response = await fetch('/api/admin/analytics/comprehensive', {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            console.error(`[Admin] Analytics API error: ${response.status}`);
            return;
        }
        
        const stats = await response.json();
        console.log('[Admin] Comprehensive analytics:', stats);
        
        // Update UI with stats
        updateAnalyticsDisplay(stats);
        
    } catch (error) {
        console.error('[Admin] Error loading comprehensive analytics:', error);
    }
}

function updateAnalyticsDisplay(stats) {
    // Find or create analytics container
    let analyticsContainer = document.getElementById('comprehensiveAnalytics');
    
    if (!analyticsContainer) {
        // Create container if it doesn't exist
        analyticsContainer = document.createElement('div');
        analyticsContainer.id = 'comprehensiveAnalytics';
        analyticsContainer.className = 'mb-8';
        
        // Insert after QUICK STATS ROW
        const quickStats = document.querySelector('.grid.grid-cols-1.sm\\:grid-cols-2.lg\\:grid-cols-4');
        if (quickStats && quickStats.parentElement) {
            quickStats.parentElement.insertBefore(analyticsContainer, quickStats.nextSibling);
        } else {
            // Fallback: insert at top of main content
            const mainContent = document.querySelector('.p-6');
            if (mainContent) {
                mainContent.insertBefore(analyticsContainer, mainContent.firstChild);
            }
        }
    }
    
    // Create comprehensive analytics HTML
    const analyticsHTML = `
        <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-8">
            <h2 class="text-xl font-bold mb-6 text-gray-900">📊 Comprehensive Analytics</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <!-- Calculations Card -->
                <div class="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4 text-gray-800">📊 Calculations</h3>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span class="text-gray-600">Today:</span>
                            <span class="font-semibold">${stats.calculations_today || 0}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">This Week:</span>
                            <span class="font-semibold">${stats.calculations_week || 0}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">This Month:</span>
                            <span class="font-semibold">${stats.calculations_month || 0}</span>
                        </div>
                        <div class="flex justify-between border-t border-blue-300 pt-2 mt-2">
                            <span class="text-gray-800 font-medium">All Time:</span>
                            <span class="font-bold text-blue-600">${stats.calculations_all || 0}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Revenue Card -->
                <div class="bg-gradient-to-br from-green-50 to-green-100 rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4 text-gray-800">💰 Revenue</h3>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span class="text-gray-600">Today:</span>
                            <span class="font-semibold">$${(stats.revenue_today || 0).toFixed(2)}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">This Week:</span>
                            <span class="font-semibold">$${(stats.revenue_week || 0).toFixed(2)}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">This Month:</span>
                            <span class="font-semibold">$${(stats.revenue_month || 0).toFixed(2)}</span>
                        </div>
                        <div class="flex justify-between border-t border-green-300 pt-2 mt-2">
                            <span class="text-gray-800 font-medium">All Time:</span>
                            <span class="font-bold text-green-600">$${(stats.revenue_all || 0).toFixed(2)}</span>
                        </div>
                    </div>
                </div>
                
                <!-- Email Captures Card -->
                <div class="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg shadow p-6">
                    <h3 class="text-lg font-semibold mb-4 text-gray-800">📧 Email Captures</h3>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span class="text-gray-600">Today:</span>
                            <span class="font-semibold">${stats.emails_today || 0}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">This Week:</span>
                            <span class="font-semibold">${stats.emails_week || 0}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-gray-600">This Month:</span>
                            <span class="font-semibold">${stats.emails_month || 0}</span>
                        </div>
                        <div class="flex justify-between border-t border-purple-300 pt-2 mt-2">
                            <span class="text-gray-800 font-medium">All Time:</span>
                            <span class="font-bold text-purple-600">${stats.emails_all || 0}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Additional Stats Row -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
                <div class="bg-gray-50 rounded-lg p-4">
                    <div class="flex justify-between items-center">
                        <span class="text-gray-700 font-medium">Active Partners:</span>
                        <span class="text-2xl font-bold text-blue-600">${stats.partners_total || 0}</span>
                    </div>
                </div>
                <div class="bg-gray-50 rounded-lg p-4">
                    <div class="flex justify-between items-center">
                        <span class="text-gray-700 font-medium">Pending Applications:</span>
                        <span class="text-2xl font-bold text-yellow-600">${stats.applications_pending || 0}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    analyticsContainer.innerHTML = analyticsHTML;
}

// 9. View Broker Payment Info
async function viewBrokerPaymentInfo(brokerId, brokerName, brokerEmail) {
    try {
        console.log(`[Admin] Loading payment info for broker ${brokerId}...`);
        
        const response = await fetch(`/api/admin/broker-payment-info/${brokerId}`, {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            alert('❌ Error loading payment info: ' + response.status);
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Payment info:', data);
        
        const paymentInfo = data.payment_info || {};
        const broker = data.broker || {};
        
        // Format payment method name
        const methodNames = {
            'paypal': 'PayPal',
            'wise': 'Wise (TransferWise)',
            'revolut': 'Revolut',
            'sepa': 'SEPA Transfer (Europe)',
            'swift': 'SWIFT/Wire Transfer',
            'crypto': 'Cryptocurrency'
        };
        const paymentMethod = methodNames[paymentInfo.payment_method?.toLowerCase()] || paymentInfo.payment_method || 'Not Set';
        
        // Build payment details HTML
        let paymentDetailsHTML = '';
        
        if (paymentInfo.payment_method === 'paypal' || paymentInfo.payment_method === 'wise' || paymentInfo.payment_method === 'revolut') {
            paymentDetailsHTML = `
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Payment Email:</label>
                    <p class="text-gray-900 font-mono">${paymentInfo.payment_email || 'Not provided'}</p>
                </div>
            `;
        } else if (paymentInfo.payment_method === 'sepa') {
            paymentDetailsHTML = `
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">IBAN:</label>
                    <p class="text-gray-900 font-mono">${paymentInfo.iban || 'Not provided'}</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">BIC/SWIFT Code:</label>
                    <p class="text-gray-900 font-mono">${paymentInfo.swift_code || 'Not provided'}</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Bank Name:</label>
                    <p class="text-gray-900">${paymentInfo.bank_name || 'Not provided'}</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Account Holder Name:</label>
                    <p class="text-gray-900">${paymentInfo.account_holder_name || 'Not provided'}</p>
                </div>
            `;
        } else if (paymentInfo.payment_method === 'swift') {
            paymentDetailsHTML = `
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">SWIFT/BIC Code:</label>
                    <p class="text-gray-900 font-mono">${paymentInfo.swift_code || 'Not provided'}</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Bank Name:</label>
                    <p class="text-gray-900">${paymentInfo.bank_name || 'Not provided'}</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Bank Address:</label>
                    <p class="text-gray-900">${paymentInfo.bank_address || 'Not provided'}</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Account Holder Name:</label>
                    <p class="text-gray-900">${paymentInfo.account_holder_name || 'Not provided'}</p>
                </div>
            `;
        } else if (paymentInfo.payment_method === 'crypto') {
            paymentDetailsHTML = `
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Wallet Address:</label>
                    <p class="text-gray-900 font-mono break-all">${paymentInfo.crypto_wallet || 'Not provided'}</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Currency:</label>
                    <p class="text-gray-900">${paymentInfo.crypto_currency || 'Not provided'}</p>
                </div>
            `;
        }
        
        const contentHTML = `
            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Broker Name:</label>
                    <p class="text-gray-900 font-semibold">${broker.name || brokerName || 'Unknown'}</p>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Email:</label>
                    <p class="text-gray-900">${broker.email || brokerEmail || 'Not provided'}</p>
                </div>
                <div class="border-t pt-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Payment Method:</label>
                    <p class="text-gray-900 font-semibold text-lg">${paymentMethod}</p>
                </div>
                ${paymentDetailsHTML}
                <div class="border-t pt-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Tax ID:</label>
                    <p class="text-gray-900">${paymentInfo.tax_id || 'Not provided'}</p>
                </div>
            </div>
        `;
        
        safe.html('payment-info-content', contentHTML);
        safe.show('paymentInfoModal');
        document.getElementById('paymentInfoModal').classList.remove('hidden');
        
    } catch (error) {
        console.error('[Admin] Error loading payment info:', error);
        alert('❌ Error: ' + error.message);
    }
}

// 10. Load Payment History
async function loadPaymentHistory() {
    try {
        const filter = document.getElementById('payment-filter')?.value || 'all';
        console.log(`[Admin] Loading payment history (filter: ${filter})...`);
        
        const response = await fetch(`/api/admin/payment-history?time_filter=${filter}`, {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            console.error(`[Admin] Payment history API error: ${response.status}`);
            safe.hide('payment-history-table');
            safe.show('no-payment-history');
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Payment history:', data);
        
        const payments = data.payments || [];
        
        if (payments.length === 0) {
            safe.hide('payment-history-table');
            safe.show('no-payment-history');
            return;
        }
        
        safe.hide('no-payment-history');
        safe.show('payment-history-table');
        
        const html = payments.map(payment => {
            const date = new Date(payment.paid_at || payment.created_at);
            const dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
            
            const statusBadge = payment.status === 'completed'
                ? '<span class="px-2 py-1 rounded text-xs bg-green-100 text-green-800">Completed</span>'
                : payment.status === 'failed'
                ? '<span class="px-2 py-1 rounded text-xs bg-red-100 text-red-800">Failed</span>'
                : '<span class="px-2 py-1 rounded text-xs bg-yellow-100 text-yellow-800">Pending</span>';
            
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
            
            return `
                <tr class="hover:bg-gray-50">
                    <td class="py-3 px-6 text-sm text-gray-900">${dateStr}</td>
                    <td class="py-3 px-6 text-sm text-gray-900">${payment.broker_name || 'Unknown'}</td>
                    <td class="py-3 px-6 text-sm font-semibold text-gray-900">$${parseFloat(payment.amount || 0).toFixed(2)}</td>
                    <td class="py-3 px-6 text-sm text-gray-600">${methodName}</td>
                    <td class="py-3 px-6 text-sm text-gray-600 font-mono">${payment.transaction_id || 'N/A'}</td>
                    <td class="py-3 px-6">${statusBadge}</td>
                </tr>
            `;
        }).join('');
        
        safe.html('payment-history-table', html);
        
    } catch (error) {
        console.error('[Admin] Error loading payment history:', error);
        safe.hide('payment-history-table');
        safe.show('no-payment-history');
    }
}

// 11. Export Payment History to CSV
async function exportPaymentHistory() {
    try {
        const filter = document.getElementById('payment-filter')?.value || 'all';
        console.log(`[Admin] Exporting payment history (filter: ${filter})...`);
        
        const response = await fetch(`/api/admin/payment-history/export?time_filter=${filter}`, {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            alert('❌ Error exporting payment history: ' + response.status);
            return;
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `payment-history-${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        console.log('✅ Payment history exported');
        
    } catch (error) {
        console.error('[Admin] Error exporting payment history:', error);
        alert('❌ Error: ' + error.message);
    }
}

// 12. Close Modal
function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
    }
}

// 13. Handle Mark as Paid
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
    
    try {
        const response = await fetch('/api/admin/mark-paid', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            },
            credentials: "include",
            body: JSON.stringify({
                broker_id: brokerId,
                amount: parseFloat(amount),
                payment_method: paymentMethod,
                transaction_id: transactionId,
                notes: notes
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            alert('❌ Error: ' + (error.message || 'Failed to mark payment as paid'));
            return;
        }
        
        const data = await response.json();
        alert('✅ Payment marked as paid successfully');
        
        // Close modal and refresh
        closeModal('markPaidModal');
        loadPaymentHistory();
        
        // Reset form
        document.getElementById('mark-paid-form').reset();
        
    } catch (error) {
        console.error('[Admin] Error marking payment as paid:', error);
        alert('❌ Error: ' + error.message);
    }
}

// 14. Show Mark as Paid Modal
function showMarkPaidModal(brokerId, amount) {
    document.getElementById('paid-broker-id').value = brokerId;
    if (amount) {
        document.getElementById('paid-amount').value = amount.toFixed(2);
    }
    document.getElementById('markPaidModal').classList.remove('hidden');
}

// 15. Load Ready to Pay Brokers
async function loadReadyToPay() {
    try {
        console.log('[Admin] Loading brokers ready to pay...');
        
        const response = await fetch('/api/admin/brokers-ready-to-pay', {
            credentials: "include",
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (!response.ok) {
            console.error(`[Admin] Ready to pay API error: ${response.status}`);
            const container = document.getElementById('ready-to-pay-list');
            if (container) {
                container.innerHTML = '<p class="text-gray-500 py-4">Error loading brokers ready to pay</p>';
            }
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Brokers ready to pay:', data);
        
        const brokers = data.brokers || [];
        const container = document.getElementById('ready-to-pay-list');
        
        if (!container) {
            console.warn('[Admin] ready-to-pay-list container not found');
            return;
        }
        
        if (brokers.length === 0) {
            container.innerHTML = '';
            const emptyState = document.getElementById('no-ready-to-pay');
            if (emptyState) {
                emptyState.classList.remove('hidden');
            }
            const section = document.getElementById('readyToPaySection');
            if (section) {
                section.classList.add('hidden');
            }
            return;
        }
        
        // Hide empty state
        const emptyState = document.getElementById('no-ready-to-pay');
        if (emptyState) {
            emptyState.classList.add('hidden');
        }
        
        // Sort by days overdue (most overdue first)
        brokers.sort((a, b) => (b.days_overdue || 0) - (a.days_overdue || 0));
        
        // Generate HTML for each broker
        const html = brokers.map(broker => {
            const isOverdue = broker.days_overdue > 0;
            const overdueClass = isOverdue ? 'border-red-300 bg-red-50' : 'border-gray-200 bg-white';
            const overdueBadge = isOverdue 
                ? `<span class="px-2 py-1 rounded text-xs bg-red-100 text-red-800 font-semibold">${broker.days_overdue} days overdue</span>`
                : '';
            const firstPaymentBadge = broker.is_first_payment 
                ? '<span class="px-2 py-1 rounded text-xs bg-blue-100 text-blue-800 font-semibold">First Payment</span>'
                : '';
            
            const methodNames = {
                'paypal': 'PayPal',
                'wise': 'Wise',
                'revolut': 'Revolut',
                'sepa': 'SEPA',
                'swift': 'SWIFT',
                'crypto': 'Crypto'
            };
            const paymentMethod = methodNames[broker.payment_method?.toLowerCase()] || broker.payment_method || 'Not Set';
            
            return `
                <tr class="hover:bg-gray-50 ${overdueClass}">
                    <td class="py-3 px-6 text-sm font-medium text-gray-900">${broker.name || 'Unknown'}</td>
                    <td class="py-3 px-6 text-sm text-gray-600">${broker.email || 'N/A'}</td>
                    <td class="py-3 px-6 text-sm font-semibold text-green-600">$${parseFloat(broker.commission_owed || 0).toFixed(2)}</td>
                    <td class="py-3 px-6 text-sm text-gray-600">${paymentMethod}</td>
                    <td class="py-3 px-6 text-sm text-gray-600">${broker.payment_address || 'N/A'}</td>
                    <td class="py-3 px-6 text-sm text-gray-600">${broker.next_payment_due ? new Date(broker.next_payment_due).toLocaleDateString() : 'N/A'}</td>
                    <td class="py-3 px-6">
                        <div class="flex flex-wrap gap-2">
                            ${overdueBadge}
                            ${firstPaymentBadge}
                        </div>
                    </td>
                    <td class="py-3 px-6">
                        <div class="flex gap-2">
                            <button onclick="viewBrokerPaymentInfo(${broker.id}, '${(broker.name || '').replace(/'/g, "\\'")}', '${(broker.email || '').replace(/'/g, "\\'")}')" class="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-xs view-payment-btn">
                                View Info
                            </button>
                            <button onclick="showMarkPaidModal(${broker.id}, ${parseFloat(broker.commission_owed || 0).toFixed(2)})" class="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-xs mark-paid-btn">
                                Mark as Paid
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
        
        container.innerHTML = html;
        
        // Update count
        const countElement = document.getElementById('readyToPayCount');
        if (countElement) {
            countElement.textContent = brokers.length;
        }
        
        // Show the section if it was hidden
        const section = document.getElementById('readyToPaySection');
        if (section) {
            section.classList.remove('hidden');
        }
        
    } catch (error) {
        console.error('[Admin] Error loading ready to pay:', error);
        const container = document.getElementById('ready-to-pay-list');
        if (container) {
            container.innerHTML = '<p class="text-red-500 py-4">Error loading brokers: ' + error.message + '</p>';
        }
    }
}

// 9. Global functions
window.approveApplication = approveApplication;
window.rejectApplication = rejectApplication;
window.deleteApplication = deleteApplication;
window.deleteActiveBroker = deleteActiveBroker;
window.loadPartnerApplications = loadPartnerApplications;
window.loadActiveBrokers = loadActiveBrokers;
window.loadComprehensiveAnalytics = loadComprehensiveAnalytics;
window.viewBrokerPaymentInfo = viewBrokerPaymentInfo;
window.loadPaymentHistory = loadPaymentHistory;
window.exportPaymentHistory = exportPaymentHistory;
window.loadReadyToPay = loadReadyToPay;
window.closeModal = closeModal;
window.handleMarkPaid = handleMarkPaid;
window.showMarkPaidModal = showMarkPaidModal;
