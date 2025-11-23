# Dashboard Architecture - Complete Guide

## 🎯 The 3-Dashboard System

You now have **3 separate dashboards** for different user types:

### 1. Admin Dashboard (`admin-dashboard.html`)
**URL**: `app.lien-api.com/admin`  
**Who**: You (the business owner)  
**Purpose**: Control everything

**Features**:
- ✅ Customer management (view, cancel, export)
- ✅ Broker management (approve, view stats)
- ✅ Generate test API keys for prospects
- ✅ Payout queue (approve/reject payments)
- ✅ Analytics (revenue, expenses, growth)
- ✅ Manual overrides

### 2. Customer Dashboard (`customer-dashboard.html`)
**URL**: `app.lien-api.com`  
**Who**: API customers (contractors/suppliers)  
**Purpose**: Manage API access

**Features**:
- ✅ View API key (show/hide/copy)
- ✅ Regenerate API key
- ✅ Usage statistics
- ✅ Billing management (Stripe portal)
- ✅ View invoices
- ✅ Cancel subscription

### 3. Broker Dashboard (`broker-dashboard.html`)
**URL**: `partners.lien-api.com`  
**Who**: Referral partners (insurance brokers)  
**Purpose**: Track referrals and earnings

**Features**:
- ✅ Referral link + copy button
- ✅ Email template copy
- ✅ Referral list (active customers)
- ✅ Earnings display (total + monthly)
- ✅ Upgrade option (bounty → recurring)
- ✅ Payout history

## 🔐 Authentication

### Current State (Demo)
- No authentication yet
- All dashboards are accessible
- Sample data displayed

### Production Setup
You'll need to add:

1. **Admin Auth**:
   - Simple password protection
   - Or JWT tokens
   - Or Supabase Auth

2. **Customer Auth**:
   - Stripe Customer Portal (handles auth)
   - Or custom login with email/password

3. **Broker Auth**:
   - Email + password
   - Or magic link
   - Or Stripe Connect (if using)

## 💳 Payment Control System

### How It Works

**Automated Queueing** (95%):
- System calculates payouts automatically
- Checks 30-day churn protection
- Queues ready payouts in admin dashboard

**Manual Approval** (5%):
- You review each payout
- Click "Approve" or "Reject"
- Stripe Connect executes transfer

### Why This Approach?

✅ **Fast** - Most work is automated  
✅ **Secure** - You control final approval  
✅ **Flexible** - Can override when needed  
✅ **Auditable** - Every payout is reviewed  

## 📊 Data Flow

### Customer Signup Flow

```
1. Customer clicks: lien-api.com?ref=broker_john
   ↓
2. Landing page saves referral code to localStorage
   ↓
3. Customer clicks "Get API Key"
   ↓
4. Stripe Checkout includes metadata: { referral: 'broker_john' }
   ↓
5. Stripe webhook fires → Your backend saves:
   - Customer record
   - Referral link (broker_john)
   - Subscription status
   ↓
6. Admin dashboard shows new customer
   ↓
7. Broker dashboard updates (if broker logged in)
```

### Payout Flow

```
Day 1: Customer signs up
   ↓
Day 30: Cron job checks if customer still active
   ↓
IF active → Queue $500 payout in admin dashboard
IF cancelled → No payout
   ↓
Day 31: You see payout in admin dashboard
   ↓
You click "Approve"
   ↓
Stripe Connect transfers $500 to broker
   ↓
Broker receives email notification
   ↓
Broker dashboard shows payout in history
```

## 🛠️ Tech Stack (Recommended)

### Current (Static HTML)
- ✅ Fast to build
- ✅ Easy to demo
- ✅ Works immediately

### Production (Upgrade Path)

**Frontend**:
- React + Next.js (for dynamic dashboards)
- Or keep HTML + add API calls

**Backend**:
- FastAPI (Python) - Already created in `api/`
- PostgreSQL database
- Stripe + Stripe Connect

**Hosting**:
- Vercel (frontend)
- Railway (backend)
- Supabase (database + auth) - Optional

## 📁 File Structure

```
/
├── index.html              # Landing page
├── partners.html           # Partner program page
├── terms.html              # Terms of Service
│
├── admin-dashboard.html    # Admin dashboard
├── admin-dashboard.js      # Admin functionality
│
├── customer-dashboard.html # Customer dashboard
│
├── broker-dashboard.html   # Broker dashboard (updated)
│
├── api/
│   ├── main.py             # FastAPI backend
│   └── requirements.txt    # Python dependencies
│
└── docs/
    ├── DASHBOARD_ARCHITECTURE.md  # This file
    ├── PAYMENT_CONTROL.md          # Payment system
    └── REFERRAL_TRACKING.md        # Referral tracking
```

## 🚀 Next Steps

### Week 1: Connect to Backend
1. ✅ Dashboards created (HTML)
2. ⏳ Connect to FastAPI backend
3. ⏳ Add authentication
4. ⏳ Replace sample data with real API calls

### Week 2: Payment Integration
1. ⏳ Set up Stripe Connect
2. ⏳ Implement payout queue
3. ⏳ Add approval workflow
4. ⏳ Test end-to-end flow

### Week 3: Polish
1. ⏳ Add real-time updates (WebSocket)
2. ⏳ Email notifications
3. ⏳ Export features (CSV)
4. ⏳ Analytics charts

## 🔗 Integration Points

### Admin Dashboard → Backend

```javascript
// Replace sample data with API calls
fetch('/api/admin/customers')
  .then(res => res.json())
  .then(data => loadCustomers(data));

fetch('/api/admin/payouts/pending')
  .then(res => res.json())
  .then(data => loadPayouts(data));
```

### Customer Dashboard → Backend

```javascript
// Get customer's API key
fetch('/api/customer/api-key', {
  headers: { 'Authorization': `Bearer ${token}` }
})
  .then(res => res.json())
  .then(data => displayApiKey(data.key));
```

### Broker Dashboard → Backend

```javascript
// Get broker's referrals
fetch('/api/broker/referrals', {
  headers: { 'Authorization': `Bearer ${token}` }
})
  .then(res => res.json())
  .then(data => updateDashboard(data));
```

## 📝 Summary

You now have:

✅ **3 Complete Dashboards** - Admin, Customer, Broker  
✅ **Payment Control System** - Automated queueing + manual approval  
✅ **Test API Key Generator** - For prospects  
✅ **Broker Upgrade Flow** - Bounty → Recurring  
✅ **Complete Documentation** - How everything works  

**Next**: Connect dashboards to your FastAPI backend and add authentication!

All dashboards are ready to connect to your backend API. 🎯

