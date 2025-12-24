# Dashboard Structure & Functions Documentation

## Overview
LienDeadline.com has three distinct dashboards:
1. **Customer Dashboard** - For paying customers using the API/calculator
2. **Broker Dashboard** - For referral partners earning commissions
3. **Admin Dashboard** - For internal management (V1 and V2)

---

## 1. CUSTOMER DASHBOARD (`customer-dashboard.html`)

### Authentication
- **Session-based**: Uses `localStorage.session_token` (Bearer token)
- **Auto-redirect**: If no token or invalid session → redirects to `/dashboard`
- **Verification**: Calls `/api/verify-session` on page load
- **Logout**: Clears token and redirects to `/dashboard`

### Main Sections

#### A. Account Overview Card
- **Plan**: Shows current subscription ($299/month)
- **Status**: Active/Cancelled with next billing date
- **API Calls**: Monthly usage count (unlimited plan)

#### B. Calculator Section
**Form Fields:**
- Invoice Date (date picker)
- State (dropdown - all 51 states + DC)
- Role (supplier/subcontractor)

**Functionality:**
- Submits to `/api/v1/calculate-deadline` with Bearer token
- Displays results in cards:
  - Preliminary Notice deadline
  - Lien Filing deadline
  - Days from now with urgency colors (critical/warning/normal)
- Saves to localStorage history
- Tracks GA4 event: `calculator_submit`

#### C. Calculation Results Display
- **Preliminary Notice Card**: Deadline, days remaining, urgency indicator
- **Lien Filing Card**: Deadline, days remaining, urgency indicator
- Color-coded borders: Red (critical), Yellow (warning), Green (normal)

#### D. Calculation History Table
**Columns:**
- Date (calculation timestamp)
- Invoice Date
- State
- Prelim Deadline
- Lien Deadline
- Actions (PDF download, Delete)

**Features:**
- Loads from localStorage (last 100 calculations)
- Export to CSV button
- PDF generation using jsPDF library
- Delete individual calculations
- Empty state message

#### E. API Key Management
**Display:**
- Masked API key (shows prefix + ellipsis + last 4 chars)
- Toggle reveal/hide button
- Copy to clipboard button
- Regenerate button (with confirmation)

**Security:**
- Key is masked by default
- Copy always copies full key (even if masked)
- Regeneration requires confirmation

#### F. Usage Stats Card
- **Total API Calls**: Last 30 days count
- **States Used**: Badge display of states (TX, CA, FL, etc.)

#### G. Billing Section
- **Current Plan**: $299/month (Unlimited)
- **Manage Billing**: Opens Stripe Customer Portal
- **Payment Method**: Shows masked card (•••• 4242)
- **Next Charge**: Date and amount
- **View Invoices**: Link to invoice history

#### H. API Documentation Link
- Links to `/test-api` page

### JavaScript Functions

#### Core Functions
- `checkAuth()` - Verifies session token on load
- `logout()` - Clears session and redirects
- `getSessionToken()` - Retrieves token from localStorage
- `displayDashboardResults(data)` - Renders calculation results
- `saveCalculation(data)` - Saves to localStorage history
- `loadHistory()` - Populates history table
- `deleteCalculation(id)` - Removes from history
- `downloadHistoryPDF(id)` - Generates PDF from saved calculation
- `generatePDF(data)` - Creates PDF using jsPDF
- `exportCSV()` - Exports history to CSV file

#### Utility Functions
- `getUrgencyColor(urgency)` - Returns border color class
- `getUrgencyTextColor(urgency)` - Returns text color class
- `formatDate(dateStr)` - Formats date for display
- `getUrgencyPDFColor(urgency)` - Returns RGB for PDF
- `formatServing(requirement)` - Formats serving requirements

#### API Key Functions
- `maskApiKey()` - Masks API key display
- `toggleApiKey()` - Shows/hides full key
- `copyApiKey()` - Copies to clipboard
- `regenerateApiKey()` - Generates new key (with confirmation)

#### Billing Functions
- `openStripePortal()` - Opens Stripe billing portal
- `updatePayment()` - Updates payment method
- `viewInvoices()` - Views invoice history

---

## 2. BROKER DASHBOARD (`broker-dashboard.html`)

### Authentication
- **Login Form**: Email + password
- **Token Storage**: `localStorage.brokerToken` and `localStorage.brokerEmail`
- **Endpoints**: 
  - `POST /api/v1/broker/login`
  - `POST /api/v1/broker/request-password-reset`
  - `POST /api/v1/broker/change-password`
- **Auto-load**: If token exists, loads dashboard on page load

### Main Sections

#### A. Stats Cards (Top Row)
- **Total Referrals**: Count of referred customers
- **Pending Commissions**: Amount on hold (yellow badge)
- **Paid Commissions**: Total paid out (green badge)

#### B. Referral Link Section
- **Referral Link**: Full URL with referral code
- **Copy Button**: Copies link to clipboard
- **Commission Model Display**: 
  - "$500 one-time per customer" (bounty)
  - "$50 per month per active customer" (recurring)
- **Note**: 60-day hold period explanation

#### C. Payment Settings
**Payment Methods Supported:**
- PayPal (email)
- Wise/TransferWise (email)
- Revolut (email)
- SEPA Transfer (IBAN, BIC/SWIFT, bank name, account holder)
- SWIFT/Wire Transfer (SWIFT code, bank name, address, account holder)
- Cryptocurrency (wallet address, currency: BTC/USDT/ETH)

**Features:**
- Update payment info button
- Masked display (email: p***@email.com)
- Encrypted storage note
- Tax ID field (optional, required for $600+/year)

#### D. Marketing Materials Section
**Email Template:**
- Pre-filled subject and body
- Includes referral link
- Copy to clipboard button
- "Email a Client" mailto link

**LinkedIn Post:**
- 280 character limit
- Character counter
- Copy to clipboard button
- Share on LinkedIn button (opens LinkedIn share dialog)

**SMS Template:**
- 160 character limit
- Character counter
- Copy to clipboard button

**Auto-population:**
- Templates auto-fill with broker name and referral link
- All templates include referral link

#### E. Referrals Table
**Columns:**
- Customer Email
- Date (referral created date)
- Amount (customer subscription amount)
- Your Commission (broker payout amount)
- Status (PAID/PENDING badge)

**Data Source:** `/api/v1/broker/dashboard?email={email}`

#### F. Broker Payouts & Commissions FAQ
**6 FAQ Items:**
1. How do broker commissions work?
2. When do I get paid?
3. What happens if customer refunds/disputes/cancels?
4. What can I see vs admin-only?
5. Why is commission showing "On Hold"?
6. How do payouts get processed?

**Accordion UI:**
- Click to expand/collapse
- Only one open at a time
- Smooth animations

### JavaScript Functions

#### Authentication Functions
- `login(e)` - Handles login form submission
- `logout()` - Clears tokens and reloads page
- `showForgotPassword()` - Shows password reset form
- `showLogin()` - Returns to login form
- `requestPasswordReset(e)` - Sends reset email
- `showChangePassword()` - Shows change password form
- `hideChangePassword()` - Hides change password form
- `changePassword(e)` - Updates password

#### Dashboard Functions
- `loadDashboard()` - Loads broker data from API
- `loadPaymentInfo()` - Loads payment settings
- `updatePaymentInfoDisplay(info)` - Updates payment display
- `savePaymentInfo(e)` - Saves payment information
- `togglePaymentFields()` - Shows/hides payment method fields
- `showPaymentSettings(e)` - Opens payment settings form
- `hidePaymentSettings()` - Closes payment settings form

#### Marketing Functions
- `populateMarketingMaterials(name, link, code)` - Fills templates
- `copyEmail()` - Copies email template
- `copyLinkedIn()` - Copies LinkedIn post
- `copySMS()` - Copies SMS text
- `emailClient(e)` - Opens email client

#### Utility Functions
- `copyLink()` - Copies referral link
- `toggleBrokerFaq(button)` - Toggles FAQ accordion

### API Endpoints Used
- `POST /api/v1/broker/login`
- `GET /api/v1/broker/dashboard?email={email}`
- `GET /api/v1/broker/payment-info?email={email}`
- `POST /api/v1/broker/payment-info`
- `POST /api/v1/broker/request-password-reset`
- `POST /api/v1/broker/change-password`

---

## 3. ADMIN DASHBOARD

### Two Versions
- **V1**: `admin-dashboard.html` (Original)
- **V2**: `admin-dashboard-v2.html` (Enhanced UI)

### Authentication
- Admin-only access (requires admin credentials)
- Session-based authentication
- Logout function clears session

### V1 Structure (`admin-dashboard.html`)

#### A. Top Navigation
- Site title and description
- Links: "View Site", "Switch to V2", "Logout"

#### B. Payouts Section (Tabbed Interface)
**Tabs:**
1. **Pending** - Brokers ready for payment
2. **Paid** - Payment history
3. **Batches** - Payment batches (coming soon)

**Pending Tab:**
- Table of brokers ready to pay
- Columns: Name, Email, Amount Owed, Payment Method, Payment Address, Next Payment Due, Status, Actions
- "Mark as Paid" button for each broker
- Empty state message

**Paid Tab:**
- Payment history table
- Filter dropdown (All/This Month/This Week)
- Export CSV button
- Columns: Date, Broker, Amount, Method, Transaction ID, Status, Notes

**Batches Tab:**
- Placeholder for batch payment functionality
- Note: "Coming soon"

#### C. Quick Stats Row (6 Cards)
1. **Today's Revenue**: $ amount
2. **Active Customers**: Count
3. **Calculations Today**: Count
4. **Pending Payouts**: Count
5. **Total Paid (All Time)**: $ amount
6. **Overdue Payments**: Count

#### D. Partner Applications Section
**Table Columns:**
- Applicant (name)
- Commission Model (bounty/recurring)
- Company
- Applied (date)
- Status (pending/approved/rejected)
- Actions (Approve/Reject buttons)

**Features:**
- Pending count badge
- Export CSV button
- Empty state message

#### E. Active Brokers Section
**Table Columns:**
- Name
- Email
- Commission (model type)
- Payment Method
- Payment Status
- Last Payment (date)
- Total Paid ($)
- Actions (View Payment Info, Mark as Paid)

#### F. Customers Section
- List of all customers
- Customer details display

#### G. System & Quick Actions Panel (Right Column)
**System Health:**
- API: Online/Offline status
- Database: Healthy status
- Email: Connected status
- Stripe: Active status

**Quick Action Buttons:**
- Approve All Pending
- Pay All Ready
- Generate Test Key
- Run Backup Now

**Pending Counts:**
- Partner Applications count
- Ready to Pay amount
- Flagged Referrals count

#### H. Recent Activity Feed
- Activity log display
- Refresh button
- Empty state message

#### I. Email Conversion Metrics
- Total Calculations Today (with progress bar)
- Email Captures (with progress bar)
- Upgrade Clicks (with progress bar)

#### J. Live Analytics Embed
- Plausible Analytics iframe
- Page views, unique visitors, calculations, paid today

### V2 Structure (`admin-dashboard-v2.html`)

#### Enhanced Features Over V1:
- **Better UI**: Scoped styles, improved cards, cleaner tables
- **More Analytics**: Comprehensive analytics section
- **Payout Debug Panel**: Collapsible debug panel with:
  - Last 20 Referrals table
  - Last 20 Broker Payments table
  - Last 20 Payout Batches table
- **Broker Ledger Modal**: Detailed breakdown modal with:
  - Per-customer breakdown
  - Earning events table
  - Batch selection for payments
  - Summary totals (Earned/Paid/Due/Hold)

#### A. KPI Cards (6 Cards - Same as V1)
- Today's Revenue
- Active Customers
- Calculations Today
- Pending Payouts
- Total Paid (All Time)
- Overdue Payments

#### B. Comprehensive Analytics Section
**3 Cards:**
1. **Calculations**: Today/Week/Month/All Time
2. **Revenue**: Today/Week/Month/All Time
3. **Email Captures**: Today/Week/Month/All Time

#### C. Partner Stats Row
- Active Partners count
- Pending Applications count

#### D. Partner Applications + System Panel
- Same as V1 but with improved styling
- System Health panel on right

#### E. Payout Debug Panel (Collapsible)
**Last 20 Referrals Table:**
- ID, Broker ID, Customer Email, Stripe ID, Subscription ID, Status, Payment Date, Payout, Type, Created, Paid At, Batch ID

**Last 20 Broker Payments Table:**
- ID, Broker ID, Broker Name, Broker Email, Amount, Method, Transaction ID, Status, Created, Paid At

**Last 20 Payout Batches Table:**
- ID, Broker ID, Broker Name, Broker Email, Total Amount, Method, Transaction ID, Status, Created, Paid At

#### F. Broker Payouts Section (Enhanced)
**4 Tabs:**
1. **Due to Pay** - Brokers with eligible commissions
2. **On Hold** - Commissions in 60-day hold period
3. **Paid** - Payment history
4. **Batches** - Payout batches

**Due to Pay Tab:**
- Table with broker details
- "View Breakdown" button → Opens Ledger Modal
- "Mark as Paid" button

**On Hold Tab:**
- Shows commissions still in hold period
- Days until eligible display

**Paid Tab:**
- Same as V1 but enhanced styling
- Filter and export buttons

**Batches Tab:**
- List of all payout batches
- Batch details and status

#### G. Broker Ledger Breakdown Modal
**Broker Info Section:**
- Broker Name, Email, Commission Model, Next Payout Date

**Summary Totals:**
- Total Earned
- Total Paid
- Total Due Now
- Total On Hold

**Per-Customer Breakdown Table:**
- Customer, Model, Last Payment, Earned, Paid, Due Now, On Hold, Status

**Earning Events Table:**
- Checkbox for batch selection
- Customer, Amount, Payment Date, Eligible At, Paid, Paid Date, Status
- "Select All DUE" button
- "Create Batch + Mark Paid" button (appears when events selected)

#### H. Active Brokers Section
- Same as V1 with enhanced styling

#### I. Live Analytics Bar
- Page Views Today
- Unique Visitors Today
- Calculations Today
- Paid All Time

### Modals (Both V1 and V2)

#### 1. Generate Test API Key Modal
- Email input
- Expiry dropdown (7/14/30 days)
- Call limit input
- Generate/Cancel buttons

#### 2. Approve Broker Modal
- Email input
- Name input
- Commission Model dropdown
- Approve/Cancel buttons

#### 3. View Payment Info Modal
- Displays broker payment information
- Masked sensitive data
- Close button

#### 4. Mark as Paid Modal
- Payment Method dropdown
- Transaction ID input
- Amount Paid input
- Notes textarea
- Confirmation checkbox
- Mark as Paid/Cancel buttons

#### 5. Broker Ledger Modal (V2 Only)
- Comprehensive breakdown (see above)

### JavaScript Functions (Admin Dashboard)

#### Core Functions
- `loadDashboard()` - Loads all dashboard data
- `loadPartnerApplications()` - Loads pending applications
- `loadBrokers()` - Loads active brokers list
- `loadReadyToPay()` - Loads brokers ready for payment
- `loadPaymentHistory()` - Loads payment history
- `loadStats()` - Loads KPI stats
- `logout()` - Clears admin session

#### Partner Application Functions
- `approveApplication(id)` - Approves partner application
- `rejectApplication(id)` - Rejects partner application
- `approveAllPending()` - Approves all pending applications
- `exportApplications()` - Exports applications to CSV

#### Payout Functions
- `markAsPaid(brokerId)` - Opens mark as paid modal
- `handleMarkPaid(e)` - Processes payment
- `viewPaymentInfo(brokerId)` - Opens payment info modal
- `viewBreakdown(brokerId)` - Opens ledger breakdown modal (V2)
- `createBatchFromSelection()` - Creates batch from selected events (V2)
- `selectAllDueEvents()` - Selects all DUE events (V2)
- `toggleAllEvents(checked)` - Toggles all event checkboxes (V2)
- `exportPaymentHistory()` - Exports payment history to CSV
- `payAllReady()` - Processes all ready payments

#### Tab Functions
- `switchPayoutTab(tabName)` - Switches payout tabs
- `toggleDebugPanel()` - Toggles debug panel (V2)

#### Modal Functions
- `closeModal(modalId)` - Closes any modal
- `openModal(modalId)` - Opens any modal

#### Utility Functions
- `generateTestKey()` - Generates test API key
- `runBackup()` - Triggers database backup
- `refreshActivity()` - Refreshes activity feed
- `exportApplications()` - Exports to CSV
- `exportPaymentHistory()` - Exports payments to CSV

### API Endpoints Used (Admin)
- `GET /api/admin/stats` - Dashboard statistics
- `GET /api/admin/partner-applications` - Partner applications list
- `POST /api/admin/approve-partner/{id}` - Approve application
- `POST /api/admin/reject-partner/{id}` - Reject application
- `GET /api/admin/brokers-ready-to-pay` - Brokers ready for payment
- `GET /api/admin/broker/{id}/ledger` - Broker ledger breakdown (V2)
- `POST /api/admin/mark-paid` - Mark payment as paid
- `GET /api/admin/payment-history` - Payment history
- `GET /api/admin/brokers` - Active brokers list
- `GET /api/admin/customers` - Customers list
- `POST /api/admin/generate-test-key` - Generate test API key
- `POST /api/admin/backup` - Run backup

---

## Database Tables Referenced

### Customer Dashboard
- `users` - User accounts
- `customers` - Customer subscriptions
- `calculations` - Calculation history (stored in localStorage, not DB)

### Broker Dashboard
- `brokers` - Broker accounts
- `referrals` - Referral records
- `broker_payment_info` - Payment settings
- `broker_payments` - Payment history

### Admin Dashboard
- `partner_applications` - Partner applications
- `brokers` - All brokers
- `referrals` - All referrals
- `broker_payments` - All payments
- `payout_batches` - Payout batches
- `customers` - All customers
- `users` - All users

---

## Security Features

### Customer Dashboard
- Bearer token authentication
- Session verification on page load
- API key masking
- Secure logout

### Broker Dashboard
- Email/password authentication
- Token-based session
- Password reset functionality
- Secure payment info storage

### Admin Dashboard
- Admin-only access
- Session-based authentication
- Secure API endpoints
- Audit logging capabilities

---

## Analytics Integration

### All Dashboards
- **Google Analytics (GA4)**: `G-KYZG0TN07Z`
- **Umami Analytics**: `02250d35-ee17-41be-845d-2fe0f7f15e63`

### Admin Dashboard Only
- **Plausible Analytics**: Embedded iframe for live stats

---

## File Structure

```
├── customer-dashboard.html      # Customer dashboard
├── broker-dashboard.html        # Broker dashboard
├── admin-dashboard.html         # Admin dashboard V1
├── admin-dashboard-v2.html     # Admin dashboard V2
├── admin-dashboard.js          # Admin V1 JavaScript
├── admin-dashboard-v2.js       # Admin V2 JavaScript
└── styles.css                  # Shared styles
```

---

## Key Differences Summary

| Feature | Customer | Broker | Admin |
|---------|----------|--------|-------|
| **Primary Use** | Calculate deadlines, manage API | Track referrals, get paid | Manage platform |
| **Authentication** | Session token | Email/password | Admin credentials |
| **Main Function** | Calculator + History | Referral tracking | Payout management |
| **Payment** | Stripe subscription | Commission payouts | Process payouts |
| **API Access** | Yes (API key) | No | Yes (test keys) |
| **Analytics** | GA4 + Umami | GA4 + Umami | GA4 + Umami + Plausible |

---

## Future Enhancements

### Customer Dashboard
- Server-side calculation history storage
- Team management
- API usage analytics
- Webhook configuration

### Broker Dashboard
- Commission history charts
- Referral performance analytics
- Automated marketing tools
- Payment history export

### Admin Dashboard
- Batch payment processing
- Advanced analytics dashboard
- Automated payout scheduling
- Email campaign management
- Customer support tools

