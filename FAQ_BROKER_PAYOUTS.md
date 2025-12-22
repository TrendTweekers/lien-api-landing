# Broker Payouts & Commissions FAQ

## Overview
This document describes where the broker payouts FAQ was added and how to verify it's working correctly.

## Location
**File:** `broker-dashboard.html`
**Section:** "Broker Payouts & Commissions" FAQ section
**Position:** After the "Your Referrals" table, before the closing `</div>` of the dashboard

## Implementation Details

### FAQ Items Added
1. **How do broker commissions work?** - Explains $500 one-time vs $50/month recurring models
2. **When do I get paid?** - Explains 60-day hold period and payout eligibility
3. **What happens if a customer refunds, disputes, or cancels?** - Explains refund/chargeback/cancellation handling
4. **What can I see in my broker dashboard vs what only admin sees?** - Clarifies visibility differences
5. **Why is my commission showing "On Hold"?** - Explains hold status
6. **How do payouts get processed?** - Explains batch payment processing

### Technical Implementation
- **Accordion Pattern:** Simple JavaScript toggle function (`toggleBrokerFaq`) that opens/closes FAQ items
- **Styling:** Tailwind CSS classes with minimal custom CSS for accordion transitions
- **Schema Markup:** FAQPage JSON-LD schema added to `<head>` section for SEO
- **No Framework Dependencies:** Pure JavaScript, no external libraries required

### CSS Scoping
- All FAQ styles use `.broker-faq-` prefix to avoid global CSS collisions
- Styles are scoped to the broker dashboard page only
- Uses existing Tailwind utility classes where possible

## Verification Steps

### 1. Visual Check
- [ ] Navigate to `/broker-dashboard.html` and log in as a broker
- [ ] Scroll down past the referrals table
- [ ] Verify "Broker Payouts & Commissions" section appears
- [ ] Verify all 6 FAQ items are visible with questions displayed

### 2. Accordion Functionality
- [ ] Click on first FAQ question - should expand to show answer
- [ ] Click on second FAQ question - first should close, second should open
- [ ] Verify only one FAQ item can be open at a time
- [ ] Verify chevron icon rotates when FAQ item opens/closes
- [ ] Verify hover states work on FAQ triggers

### 3. Content Verification
- [ ] Verify FAQ 1 mentions both commission models ($500 one-time and $50/month)
- [ ] Verify FAQ 2 mentions "60 days" hold period
- [ ] Verify FAQ 3 mentions refunds, chargebacks, and cancellations
- [ ] Verify FAQ 4 lists broker-visible vs admin-only information
- [ ] Verify FAQ 5 explains "On Hold" status
- [ ] Verify FAQ 6 mentions "payout batches"

### 4. Schema Markup Verification
- [ ] View page source (Ctrl+U or Cmd+U)
- [ ] Search for `application/ld+json`
- [ ] Verify FAQPage schema is present
- [ ] Verify all 6 questions are included in schema
- [ ] Use Google Rich Results Test: https://search.google.com/test/rich-results
- [ ] Paste broker-dashboard.html URL and verify FAQPage schema validates

### 5. Mobile Responsiveness
- [ ] Resize browser to mobile width (< 768px)
- [ ] Verify FAQ section is readable and not cut off
- [ ] Verify accordion buttons are easily tappable
- [ ] Verify text doesn't overflow containers

### 6. Browser Compatibility
- [ ] Test in Chrome (latest)
- [ ] Test in Firefox (latest)
- [ ] Test in Safari (latest)
- [ ] Test in Edge (latest)
- [ ] Verify no JavaScript console errors

## Expected Behavior

### Accordion Behavior
- **Default State:** All FAQ items closed (`data-state="closed"`)
- **On Click:** Clicked item opens (`data-state="open"`), all others close
- **Visual Feedback:** 
  - Open item has orange border (`border-color: #f97316`)
  - Chevron icon rotates 180 degrees when open
  - Content slides down smoothly

### Content Display
- Questions are bold and left-aligned
- Answers appear below questions when expanded
- Answers use normal text weight and gray color
- Lists use bullet points for readability

## Files Modified
- `broker-dashboard.html` - Added FAQ section HTML, JavaScript toggle function, CSS styles, and JSON-LD schema

## Files Created
- `FAQ_BROKER_PAYOUTS.md` - This documentation file

## Notes
- FAQ section is only visible to authenticated brokers (after login)
- FAQ content is static HTML (not dynamically loaded)
- Schema markup is valid JSON-LD and follows Schema.org FAQPage format
- No API endpoints were modified or created
- No authentication logic was changed
- All existing HTML IDs remain unchanged

## Future Enhancements
- Could add anchor links to each FAQ item for direct linking
- Could add search/filter functionality if FAQ list grows
- Could add analytics tracking for FAQ item clicks
- Could add "Was this helpful?" feedback buttons

