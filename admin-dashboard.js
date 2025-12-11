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
        
        // Fetch with authentication
        const response = await fetch('/api/admin/partner-applications?status=all', {
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
        
        // Handle different response formats
        const applications = data.applications || data || [];
        
        if (!Array.isArray(applications) || applications.length === 0) {
            safe.html('applicationsTable', `
                <tr>
                    <td colspan="6" class="text-center py-8 text-gray-500">
                        <div class="flex flex-col items-center gap-2">
                            <svg class="w-12 h-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                            <p>No partner applications yet</p>
                        </div>
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
                <button onclick="approveApplication(${app.id}, '${app.email}', '${app.name || 'Unknown'}', '${app.commission_model || 'bounty'}')" 
                        class="px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg text-sm mr-2">
                    Approve
                </button>
                <button onclick="rejectApplication(${app.id})" 
                        class="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg text-sm">
                    Reject
                </button>
            ` : `
                <span class="text-gray-500 text-sm">${app.status === 'approved' ? '✅ Approved' : '❌ Rejected'}</span>
            `;
            
            return `
                <tr class="border-b hover:bg-gray-50">
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

// 5. Approve application
async function approveApplication(id, email, name, commissionModel) {
    if (!confirm(`Approve ${name} (${email}) with ${commissionModel === 'bounty' ? '$500 bounty' : '$50/month recurring'} commission?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/approve-partner/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            },
            body: JSON.stringify({
                commission_model: commissionModel || 'bounty'
            })
        });
        
        if (response.ok) {
            alert('✅ Application approved! Referral code sent to broker.');
            loadPartnerApplications(); // Refresh
            updateAllStats(); // Update stats
        } else {
            const error = await response.json();
            alert('❌ Error: ' + (error.detail || 'Failed to approve application'));
        }
    } catch (error) {
        console.error('Error approving application:', error);
        alert('❌ Error approving application: ' + error.message);
    }
}

// 6. Reject application
async function rejectApplication(id) {
    if (!confirm('Reject this application?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/reject-partner/${id}`, {
            method: 'POST',
            headers: {
                'Authorization': 'Basic ' + btoa(`${ADMIN_USER}:${ADMIN_PASS}`)
            }
        });
        
        if (response.ok) {
            alert('❌ Application rejected');
            loadPartnerApplications(); // Refresh
        } else {
            alert('❌ Error rejecting application');
        }
    } catch (error) {
        console.error('Error rejecting application:', error);
        alert('❌ Error: ' + error.message);
    }
}

// 7. Update all stats
async function updateAllStats() {
    try {
        // Calculations
        const calcResponse = await fetch('/api/admin/calculations-today');
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
    updateAllStats();
    
    // Auto-refresh
    setInterval(() => {
        loadPartnerApplications();
        updateAllStats();
    }, 30000);
    
    console.log('✅ Dashboard ready');
});

// 9. Global functions
window.approveApplication = approveApplication;
window.rejectApplication = rejectApplication;
window.loadPartnerApplications = loadPartnerApplications;
