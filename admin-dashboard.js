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

// Unified event delegation handler (capture phase) - prevents cancellation
document.addEventListener("click", async (e) => {
    const btn =
        e.target.closest(".approve-btn") ||
        e.target.closest(".reject-btn") ||
        e.target.closest(".delete-btn") ||
        e.target.closest(".delete-broker-btn");

    if (!btn) return;

    e.preventDefault();
    e.stopPropagation();
    e.stopImmediatePropagation();

    const id = btn.dataset.appId || btn.dataset.brokerId;
    if (!id) {
        alert("Missing id on button");
        return;
    }

    // IMPORTANT: always include auth + credentials so it never "half works"
    const authHeader = window.ADMIN_BASIC_AUTH
        ? { Authorization: window.ADMIN_BASIC_AUTH }
        : { Authorization: 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`) };

    try {
        if (btn.classList.contains("approve-btn")) {
            const r = await fetch(`/api/admin/approve-partner/${id}`, {
                method: "POST",
                credentials: "include",
                headers: { ...authHeader }
            });
            const text = await r.text();
            if (!r.ok) throw new Error(text || `HTTP ${r.status}`);
            alert("Approved ✅");
        }

        if (btn.classList.contains("reject-btn")) {
            const r = await fetch(`/api/admin/reject-partner/${id}`, {
                method: "POST",
                credentials: "include",
                headers: { ...authHeader }
            });
            const text = await r.text();
            if (!r.ok) throw new Error(text || `HTTP ${r.status}`);
            alert("Rejected ✅");
        }

        if (btn.classList.contains("delete-btn")) {
            const r = await fetch(`/api/admin/delete-partner/${id}`, {
                method: "DELETE",
                credentials: "include",
                headers: { ...authHeader }
            });
            const text = await r.text();
            if (!r.ok) throw new Error(text || `HTTP ${r.status}`);
            alert("Deleted ✅");
        }

        if (btn.classList.contains("delete-broker-btn")) {
            const r = await fetch(`/api/admin/delete-broker/${id}`, {
                method: "DELETE",
                credentials: "include",
                headers: { ...authHeader }
            });
            const text = await r.text();
            if (!r.ok) throw new Error(text || `HTTP ${r.status}`);
            alert("Broker deleted ✅");
        }

        // refresh UI after any action
        if (typeof loadPartnerApplications === "function") loadPartnerApplications();
        if (typeof loadActiveBrokers === "function") loadActiveBrokers();
    } catch (err) {
        alert(`Action failed: ${err.message}`);
        console.error(err);
    }
}, true); // <-- capture phase matters

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
    updateAllStats();
    updateLiveAnalytics();
    updateEmailConversion();
    loadComprehensiveAnalytics();
    
    // Auto-refresh
    setInterval(() => {
        loadPartnerApplications();
        loadActiveBrokers();
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
        
        // Render brokers
        const html = brokers.map(broker => {
            const commissionBadge = broker.commission_model === 'bounty' || broker.model === 'bounty'
                ? '<span class="px-2 py-1 rounded text-xs bg-purple-100 text-purple-800">$500 Bounty</span>'
                : '<span class="px-2 py-1 rounded text-xs bg-green-100 text-green-800">$50/month</span>';
            
            return `
                <div class="p-4 hover:bg-gray-50">
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-3">
                            <div class="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                                <span class="text-blue-600 font-semibold">${(broker.name || 'B').charAt(0).toUpperCase()}</span>
                            </div>
                            <div>
                                <div class="font-semibold text-gray-900">${broker.name || 'Unknown'}</div>
                                <div class="text-sm text-gray-600">${broker.email || ''}</div>
                            </div>
                        </div>
                        <div class="flex items-center gap-3">
                            <div class="text-right">
                                <div class="text-sm text-gray-600">${commissionBadge}</div>
                                <div class="text-xs text-gray-500 mt-1">Ref: ${broker.referral_code || 'N/A'}</div>
                            </div>
                            <button type="button"
                                class="delete-broker-btn px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-sm"
                                data-broker-id="${broker.id}"
                                title="Delete broker">
                                Delete
                            </button>
                        </div>
                    </div>
                </div>
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

// 9. Global functions
window.approveApplication = approveApplication;
window.rejectApplication = rejectApplication;
window.deleteApplication = deleteApplication;
window.deleteActiveBroker = deleteActiveBroker;
window.loadPartnerApplications = loadPartnerApplications;
window.loadActiveBrokers = loadActiveBrokers;
window.loadComprehensiveAnalytics = loadComprehensiveAnalytics;
