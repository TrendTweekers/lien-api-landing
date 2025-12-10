// ==================== SAFETY WRAPPERS ====================
console.log('[Admin Dashboard] Loading...');

// Safe element getter
function getEl(id) {
    const el = document.getElementById(id);
    if (!el) {
        console.warn(`[Admin] ⚠️ Element #${id} not found in DOM`);
        return null;
    }
    return el;
}

// Safe text setter
function setText(id, text) {
    const el = getEl(id);
    if (el) {
        el.textContent = text;
    }
}

// Safe HTML setter
function setHtml(id, html) {
    const el = getEl(id);
    if (el) {
        el.innerHTML = html;
    }
}

// Safe function call
function safeCall(fn, name = 'anonymous') {
    try {
        return fn();
    } catch (error) {
        console.error(`[Admin] Error in ${name}:`, error);
        return null;
    }
}

// Check if should run function
function shouldRun(elementId, functionName) {
    if (!getEl(elementId)) {
        console.log(`[Admin] Skipping ${functionName} - element #${elementId} not found`);
        return false;
    }
    return true;
}

// ==================== END SAFETY WRAPPERS ====================

// ==================== CORE FUNCTIONS ====================
async function fetchPartnerApplications() {
    if (!shouldRun('applicationsTable', 'fetchPartnerApplications')) return;
    
    try {
        console.log('[Admin] Fetching partner applications...');
        const response = await fetch('/api/admin/partner-applications');
        console.log(`[Admin] Response status: ${response.status}`);
        
        const data = await response.json();
        console.log('[Admin] Received data:', data);
        
        renderApplications(data.applications || []);
        
    } catch (error) {
        console.error('[Admin] Error fetching applications:', error);
    }
}

function renderApplications(applications) {
    const container = getEl('applicationsTable');
    if (!container) return;
    
    if (!applications || applications.length === 0) {
        setHtml('applicationsTable', `
            <tr>
                <td colspan="6" class="px-6 py-12 text-center text-gray-500">
                    No partner applications yet
                </td>
            </tr>
        `);
        return;
    }
    
    let html = '';
    applications.forEach(app => {
        const commissionBadge = app.commission_model === 'bounty' 
            ? '<span class="px-2 py-1 text-xs font-medium bg-purple-100 text-purple-800 rounded">$500 Bounty</span>'
            : '<span class="px-2 py-1 text-xs font-medium bg-green-100 text-green-800 rounded">$50/month</span>';
        
        html += `
        <tr class="hover:bg-gray-50">
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center">
                    <div class="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                        <span class="text-blue-600 font-bold">${app.name?.charAt(0) || 'U'}</span>
                    </div>
                    <div class="ml-4">
                        <div class="text-sm font-medium text-gray-900">${app.name || 'Unknown'}</div>
                        <div class="text-sm text-gray-500">${app.email || ''}</div>
                    </div>
                </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                ${commissionBadge}
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">${app.company || 'N/A'}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${formatTimeAgo(app.applied_at)}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2 py-1 text-xs font-medium ${app.status === 'pending' ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'} rounded">
                    ${app.status || 'unknown'}
                </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button onclick="approveApplication('${app.id}', '${app.commission_model}')" class="text-green-600 hover:text-green-900 mr-3">Approve</button>
                <button onclick="rejectApplication('${app.id}')" class="text-red-600 hover:text-red-900">Reject</button>
            </td>
        </tr>
        `;
    });
    
    setHtml('applicationsTable', html);
    console.log(`[Admin] ✅ Applications rendered: ${applications.length}`);
}

async function updateCalculationsCounter() {
    if (!shouldRun('calculationsToday', 'updateCalculationsCounter')) return;
    
    try {
        const response = await fetch('/api/admin/calculations-today');
        if (!response.ok) {
            console.warn('[Admin] Failed to fetch calculations');
            return;
        }
        
        const data = await response.json();
        console.log('[Admin] Calculations data:', data);
        
        setText('calculationsToday', data.calculations_today || '0');
        
    } catch (error) {
        console.error('[Admin] Error updating calculations:', error);
    }
}

// Helper function
function formatTimeAgo(timestamp) {
    if (!timestamp) return 'Recently';
    // Simple implementation
    return 'Recently';
}

// Update all stats
async function updateAllStats() {
    safeCall(updateCalculationsCounter, 'updateCalculationsCounter');
    
    // Update other stats here
    try {
        const response = await fetch('/api/admin/today-stats');
        if (response.ok) {
            const data = await response.json();
            setText('todayRevenue', `$${data.revenue_today || 0}`);
            setText('activeCustomers', data.active_customers || '0');
            setText('pendingPayouts', `$${data.pending_payouts || 0}`);
        }
    } catch (error) {
        console.error('[Admin] Error updating stats:', error);
    }
}

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', function() {
    console.log('[Admin] DOM loaded - initializing...');
    
    // Load data
    safeCall(fetchPartnerApplications, 'fetchPartnerApplications');
    safeCall(updateAllStats, 'updateAllStats');
    
    // Set up auto-refresh (every 30 seconds)
    setInterval(() => {
        safeCall(updateAllStats, 'updateAllStats');
    }, 30000);
    
    console.log('[Admin] Initialization complete');
});

// Make functions available globally
window.approveApplication = async function(id, commissionModel) {
    if (!confirm(`Approve this partner with ${commissionModel === 'bounty' ? '$500 bounty' : '$50/month recurring'}?`)) return;
    
    try {
        const response = await fetch(`/api/admin/approve-partner/${id}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Application approved!');
            fetchPartnerApplications();
            updateAllStats();
        }
    } catch (error) {
        console.error('Error approving:', error);
        alert('Error approving application');
    }
};

window.rejectApplication = async function(id) {
    if (!confirm('Reject this application?')) return;
    
    try {
        const response = await fetch(`/api/admin/reject-partner/${id}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            alert('Application rejected');
            fetchPartnerApplications();
        }
    } catch (error) {
        console.error('Error rejecting:', error);
        alert('Error rejecting application');
    }
};
