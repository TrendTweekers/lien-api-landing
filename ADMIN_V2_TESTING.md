# Admin Dashboard V2 Testing Checklist

## Overview
This document provides a comprehensive testing checklist to verify that:
1. The new V2 admin dashboard works correctly
2. The existing V1 admin dashboard remains fully functional
3. No breaking changes were introduced
4. All API endpoints work as expected

## Pre-Testing Setup

### 1. Access Both Dashboards
- [ ] **Default (V2)**: Navigate to `/admin-dashboard` (serves V2 by default, requires HTTP Basic Auth)
- [ ] **V1 Dashboard**: Navigate to `/admin-dashboard?ui=v1` (requires HTTP Basic Auth)
- [ ] **V2 Dashboard**: Navigate to `/admin-dashboard?ui=v2` or `/admin-dashboard-v2` (requires HTTP Basic Auth)
- [ ] Verify all dashboard URLs load without errors
- [ ] Check browser console for any JavaScript errors
- [ ] Verify "Switch to V1" link in V2 header works
- [ ] Verify "Switch to V2" link in V1 header works

### 2. Authentication
- [ ] Both dashboards require HTTP Basic Auth (username: `admin`, password: `LienAPI2025`)
- [ ] Invalid credentials are rejected on both dashboards
- [ ] Logout button works on both dashboards

## V1 Dashboard Functionality (Must Not Break)

### Partner Applications
- [ ] Partner applications table loads correctly
- [ ] Pending count badge displays correct number
- [ ] "Approve" button works and creates broker account
- [ ] "Reject" button works and updates application status
- [ ] "Delete" button works and removes application
- [ ] "Export CSV" button works (if implemented)
- [ ] Empty state displays when no applications exist

### Active Brokers
- [ ] Active brokers table loads correctly
- [ ] Broker count displays correctly
- [ ] Payment method badges display correctly
- [ ] Payment status badges display correctly
- [ ] "View Payment Info" button opens modal with correct data
- [ ] "Delete" button works and removes broker
- [ ] Empty state displays when no brokers exist

### Ready to Pay Section
- [ ] Brokers ready to pay table loads correctly
- [ ] Overdue badges display correctly
- [ ] "First Payment" badges display correctly
- [ ] "View Info" button opens payment info modal
- [ ] "Mark as Paid" button opens mark paid modal
- [ ] Empty state displays when no brokers are ready

### Payment History
- [ ] Payment history table loads correctly
- [ ] Filter dropdown (All/Month/Week) works
- [ ] "Export CSV" button downloads CSV file
- [ ] Empty state displays when no payments exist

### Statistics & Analytics
- [ ] Today's Revenue displays (or "—" if unavailable)
- [ ] Active Customers displays (or "—" if unavailable)
- [ ] Calculations Today displays correctly
- [ ] Pending Payouts count updates correctly
- [ ] Total Paid (All Time) displays correctly
- [ ] Overdue Payments count updates correctly

### Modals
- [ ] Payment Info Modal opens and displays correct data
- [ ] Mark as Paid Modal opens with pre-filled broker ID and amount
- [ ] Mark as Paid form submission works
- [ ] Modals close correctly when clicking close button or outside

## V2 Dashboard Functionality (New Features)

### UI Layout
- [ ] V2 dashboard uses Lovable design system (scoped under `#admin-v2`)
- [ ] All CSS is scoped and doesn't affect other pages
- [ ] Responsive design works on mobile/tablet/desktop
- [ ] Navigation header includes "V2 Dashboard" link

### KPI Cards
- [ ] All 6 KPI cards display correctly
- [ ] Icons and colors match Lovable design
- [ ] Values update correctly or show "—" if unavailable

### Comprehensive Analytics
- [ ] Calculations card shows Today/Week/Month/All Time
- [ ] Revenue card shows Today/Week/Month/All Time
- [ ] Email Captures card shows Today/Week/Month/All Time
- [ ] All values display correctly or show "—" if unavailable

### Partner Applications Table
- [ ] Table loads and displays applications correctly
- [ ] Badges (Pending/Monthly/Bounty) display correctly
- [ ] Action buttons (Approve/Reject/Delete) work correctly
- [ ] Empty state displays correctly

### Broker Payouts Section
- [ ] Tabs (Due to Pay / On Hold / Paid / Batches) switch correctly
- [ ] "Due to Pay" tab shows brokers with `total_due_now > 0` (from ledger)
- [ ] "On Hold" tab shows brokers with `total_on_hold > 0` (from ledger)
- [ ] "Paid" tab shows payment history from `/api/admin/payment-history`
- [ ] "Batches" tab shows placeholder message
- [ ] Badge counts update correctly
- [ ] "View Breakdown" button opens ledger modal with per-customer and per-event details
- [ ] "Mark Paid" button works correctly and shows referrals marked count
- [ ] Export buttons work correctly

### Payout Ledger Integration
- [ ] `/api/admin/brokers-ready-to-pay` endpoint returns ledger data with `brokers` array
- [ ] `/api/admin/broker-ledger/{broker_id}` endpoint returns full ledger breakdown
- [ ] `/api/admin/mark-paid` marks referral IDs and returns `paid_referral_ids` and `referrals_marked`
- [ ] Ledger modal shows accurate totals (earned, paid, due, hold)
- [ ] Ledger modal shows per-customer breakdown with status badges
- [ ] Ledger modal shows earning events with status (HELD / DUE / PAID / REFUNDED / CHARGEBACK / PAST_DUE / CANCELED)
- [ ] Missing fields render "—" instead of crashing
- [ ] Empty states show friendly messages

### Ledger Flow Testing
- [ ] **New Payment**: Broker appears in "On Hold" immediately after customer payment
- [ ] **60-Day Hold**: After 60 days, broker moves from "On Hold" to "Due to Pay"
  - *Note: To test quickly, manually adjust `payment_date` in DB or use dev override*
- [ ] **Mark Paid**: After marking paid, broker disappears from "Due to Pay" and appears in "Paid" history
- [ ] **Breakdown Modal**: Shows accurate per-customer totals and individual earning events

### Active Brokers Table
- [ ] Table loads and displays brokers correctly
- [ ] All columns display correctly
- [ ] Action buttons work correctly
- [ ] Empty state displays correctly

### Live Analytics Bar
- [ ] Page Views Today displays (or "—")
- [ ] Unique Visitors Today displays (or "—")
- [ ] Calculations Today displays (or "—")
- [ ] Paid All Time displays (or "—")

## API Endpoint Verification

### Verify No Changes to Backend
- [ ] `/api/admin/partner-applications` returns same format
- [ ] `/api/admin/brokers` returns same format
- [ ] `/api/admin/brokers-ready-to-pay` returns same format
- [ ] `/api/admin/payment-history` returns same format
- [ ] `/api/admin/mark-paid` accepts same request format
- [ ] `/api/admin/broker-payment-info/{id}` returns same format
- [ ] `/api/admin/analytics/comprehensive` returns same format
- [ ] `/api/admin/payment-history/export` returns CSV correctly

### Verify Authentication
- [ ] All admin endpoints require HTTP Basic Auth
- [ ] Invalid credentials return 401 Unauthorized
- [ ] Valid credentials allow access

## Error Handling

### Missing Data
- [ ] Dashboard shows "—" for missing/null metrics (never crashes)
- [ ] Empty states display correctly
- [ ] Error messages are user-friendly

### Network Errors
- [ ] Failed API calls show error messages
- [ ] Dashboard continues to function with partial data
- [ ] No JavaScript errors crash the page

## Performance

### Loading
- [ ] Dashboard loads within reasonable time (< 3 seconds)
- [ ] Auto-refresh works correctly (every 60 seconds)
- [ ] No memory leaks during auto-refresh

### Browser Compatibility
- [ ] Works in Chrome (latest)
- [ ] Works in Firefox (latest)
- [ ] Works in Safari (latest)
- [ ] Works in Edge (latest)

## Security

### Authentication
- [ ] Both dashboards require authentication
- [ ] Authentication credentials are not exposed in client-side code
- [ ] Logout clears session correctly

### Data Protection
- [ ] Sensitive payment data is masked in tables
- [ ] Full payment details only shown in modals
- [ ] No sensitive data in browser console logs

## Regression Testing

### V1 Dashboard Still Works
- [ ] All V1 features work exactly as before
- [ ] No visual changes to V1 dashboard
- [ ] No functional changes to V1 dashboard
- [ ] All V1 buttons and forms work correctly

### V2 Dashboard Works Independently
- [ ] V2 dashboard works without V1 being loaded
- [ ] V2 CSS doesn't affect V1 dashboard
- [ ] V2 JavaScript doesn't conflict with V1

## Edge Cases

### Empty States
- [ ] No applications → Empty state displays
- [ ] No brokers → Empty state displays
- [ ] No payments → Empty state displays
- [ ] No ready to pay → Empty state displays

### Large Data Sets
- [ ] Dashboard handles 100+ applications
- [ ] Dashboard handles 100+ brokers
- [ ] Dashboard handles 1000+ payment records
- [ ] Tables scroll correctly
- [ ] Performance remains acceptable

### Special Characters
- [ ] Broker names with special characters display correctly
- [ ] Email addresses with special characters work correctly
- [ ] Payment addresses with special characters display correctly

## Integration Testing

### Cross-Dashboard Navigation
- [ ] "Switch to V2" link in V1 header works (links to `/admin-dashboard?ui=v2`)
- [ ] "Switch to V1" link in V2 header works (links to `/admin-dashboard?ui=v1`)
- [ ] Default `/admin-dashboard` serves V2 (no query param needed)
- [ ] `/admin-dashboard?ui=v1` serves V1 dashboard
- [ ] `/admin-dashboard?ui=v2` serves V2 dashboard
- [ ] `/admin-dashboard-v2` still works (backward compatibility)
- [ ] Navigation doesn't break authentication
- [ ] Navigation preserves state (if applicable)

### Data Consistency
- [ ] Approving application in V1 updates V2 immediately (after refresh)
- [ ] Marking payment as paid in V1 updates V2 immediately (after refresh)
- [ ] Deleting broker in V1 updates V2 immediately (after refresh)

## Documentation

### Code Comments
- [ ] V2 code is well-commented
- [ ] API endpoint usage is documented
- [ ] Function purposes are clear

### User Documentation
- [ ] **Default URL**: `/admin-dashboard` serves V2 dashboard
- [ ] **V1 URL**: `/admin-dashboard?ui=v1` serves V1 dashboard
- [ ] **V2 URL**: `/admin-dashboard?ui=v2` or `/admin-dashboard-v2` serves V2 dashboard
- [ ] Both dashboards use same authentication
- [ ] Header links allow switching between V1 and V2

## Final Checklist

- [ ] All tests pass
- [ ] No console errors
- [ ] No breaking changes to V1
- [ ] V2 works as expected
- [ ] Documentation is complete
- [ ] Ready for production deployment

## Notes

### Known Limitations
- Batch payments feature is placeholder (shows "coming soon" message)
- Some quick action buttons (Approve All, Pay All Ready) show "coming soon" alerts
- CSV export for applications may need endpoint implementation

### Future Enhancements
- Implement batch payment processing
- Add bulk approve/reject functionality
- Add advanced filtering and search
- Add export functionality for all tables

## Test Results

**Date:** _______________
**Tester:** _______________
**Environment:** _______________

**V1 Dashboard:** ✅ Pass / ❌ Fail
**V2 Dashboard:** ✅ Pass / ❌ Fail
**API Endpoints:** ✅ Pass / ❌ Fail
**Security:** ✅ Pass / ❌ Fail

**Issues Found:**
1. 
2. 
3. 

**Resolution:**
1. 
2. 
3. 

