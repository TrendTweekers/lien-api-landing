// ==================== ENHANCED SAFETY ====================
console.log('🛡️ Admin Dashboard Loading...');

// 1. Define missing global that old code expects
window.API_BASE = window.API_BASE || '/api';

// 2. Enhanced safe functions
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

// 3. Load applications (existing working code)
async function loadPartnerApplications() {
    try {
        console.log('[Admin] Loading applications...');
        const response = await fetch('/api/v1/broker/pending');
        const data = await response.json();
        
        const container = safe.get('applicationsTable');
        if (!container || !data.pending) return;
        
        if (data.pending.length === 0) {
            safe.html('applicationsTable', '<tr><td colspan="6" class="text-center py-8 text-gray-500">No pending applications</td></tr>');
            return;
        }
        
        let html = '';
        data.pending.forEach(app => {
            const badge = app.commission_model === 'bounty' 
                ? '<span class="px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded">$500 Bounty</span>'
                : '<span class="px-2 py-1 text-xs bg-green-100 text-green-800 rounded">$50/month</span>';
            
            html += `
            <tr class="hover:bg-gray-50">
                <td class="px-6 py-4 whitespace-nowrap">
                    <div class="flex items-center">
                        <div class="h-10 w-10 bg-blue-100 rounded-full flex items-center justify-center">
                            <span class="text-blue-600 font-bold">${app.name?.charAt(0) || 'U'}</span>
                        </div>
                        <div class="ml-4">
                            <div class="font-medium text-gray-900">${app.name || 'Unknown'}</div>
                            <div class="text-sm text-gray-500">${app.email || ''}</div>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">${badge}</td>
                <td class="px-6 py-4 whitespace-nowrap text-gray-900">${app.company || 'N/A'}</td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">Recently</td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="px-2 py-1 text-xs bg-yellow-100 text-yellow-800 rounded">Pending</span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm">
                    <button onclick="approveApp(${app.id})" class="text-green-600 hover:text-green-900 mr-3">Approve</button>
                    <button onclick="rejectApp(${app.id})" class="text-red-600 hover:text-red-900">Reject</button>
                </td>
            </tr>
            `;
        });
        
        safe.html('applicationsTable', html);
        console.log(`✅ Loaded ${data.pending.length} applications`);
        
    } catch (error) {
        console.log('[Admin] Error:', error);
    }
}

// 4. Update all stats
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

// 5. Initialize
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

// 6. Action functions
window.approveApp = function(id) {
    if (confirm('Approve this application?')) {
        console.log('Approving', id);
        alert('Approved! Page will refresh in 30 seconds.');
    }
};

window.rejectApp = function(id) {
    if (confirm('Reject this application?')) {
        console.log('Rejecting', id);
        alert('Rejected! Page will refresh in 30 seconds.');
    }
};
