# Footer Pages Testing Checklist

This document provides a testing checklist for all footer links and the pages they point to.

## Test Environment
- **Base URL:** https://liendeadline.com (or your test environment)
- **Browser:** Test in Chrome, Firefox, Safari, and Edge
- **Mobile:** Test on mobile devices or browser dev tools

## Footer Links to Test

### Product Section
- [ ] `/api.html` - API Documentation
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Authentication section present
  - [ ] Status codes table present
  - [ ] Rate limits section present
  - [ ] Code examples (cURL, JS, Python) present
  - [ ] Valid state codes listed
  - [ ] Valid role values listed
  - [ ] Mobile responsive

- [ ] `/#pricing` - Pricing (anchor link)
  - [ ] Scrolls to pricing section
  - [ ] Pricing information displays correctly

- [ ] `/vs-levelset.html` - Levelset Alternative
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Mobile responsive

- [ ] `/changelog.html` - Changelog
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Version history displays
  - [ ] "Coming Soon" section present
  - [ ] Mobile responsive

### Company Section
- [ ] `/about.html` - About
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Mission statement present
  - [ ] "What We Do" section present
  - [ ] Disclaimer section present
  - [ ] Mobile responsive

- [ ] `/contact.html` - Contact
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Support email link works
  - [ ] Partner program link works
  - [ ] Sales email link works
  - [ ] Legal email link works
  - [ ] Help resources links work
  - [ ] Mobile responsive

### Legal Section
- [ ] `/privacy.html` - Privacy Policy
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Privacy policy content present
  - [ ] Mobile responsive

- [ ] `/terms.html` - Terms of Service
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Broker payout terms section present
  - [ ] 60-day hold period mentioned
  - [ ] Commission models explained ($500 one-time vs $50/month)
  - [ ] Refund/chargeback policy present
  - [ ] Governing law clause present
  - [ ] Termination/data retention section present
  - [ ] Links to privacy policy work
  - [ ] Mobile responsive

- [ ] `/security.html` - Security
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Data encryption section present
  - [ ] Infrastructure security section present
  - [ ] Authentication section present
  - [ ] Payment security section present
  - [ ] Mobile responsive

### Resources Section
- [ ] `/help.html` - Help Center
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Getting Started section present
  - [ ] API Integration section present
  - [ ] Broker Program & Payouts section present
  - [ ] Broker payout FAQ items present:
    - [ ] How do broker commissions work?
    - [ ] When do I get paid?
    - [ ] What happens if a customer refunds/disputes/cancels?
    - [ ] Why is my commission showing "On Hold"?
    - [ ] How do payouts get processed?
  - [ ] Billing & Subscriptions section present
  - [ ] Contact Support section present
  - [ ] Mobile responsive

- [ ] `/#partners` - Partner Program (anchor link)
  - [ ] Scrolls to partners section
  - [ ] Partner information displays correctly

- [ ] `/state-coverage.html` - State Coverage
  - [ ] Page loads without 404
  - [ ] Header/navigation matches homepage style
  - [ ] Footer matches homepage style
  - [ ] Stats display (28 states, 75% coverage)
  - [ ] All 28 states listed with links
  - [ ] State links work (e.g., `/lien-deadlines/texas.html`)
  - [ ] "Request New State" section present
  - [ ] Mobile responsive

## Footer Bottom Links
- [ ] `/privacy.html` - Privacy Policy (bottom link)
  - [ ] Link works (same as Legal section)

- [ ] `/terms.html` - Terms of Service (bottom link)
  - [ ] Link works (same as Legal section)

- [ ] `/partners.html` - Become a Partner (bottom link)
  - [ ] Link works
  - [ ] Page loads without 404

## Removed Links (Should NOT appear)
- [ ] `/blog.html` - Should NOT be in footer
  - [ ] Verify link removed from Company section
  - [ ] If page exists, it should not be linked

- [ ] `/careers.html` - Should NOT be in footer
  - [ ] Verify link removed from Company section
  - [ ] If page exists, it should not be linked

## Cross-Page Consistency Checks

### Header Consistency
For each page, verify:
- [ ] Logo links to homepage (`/`)
- [ ] Navigation items match homepage navigation
- [ ] Mobile menu works
- [ ] "Start Free Trial" button present and functional

### Footer Consistency
For each page, verify:
- [ ] Footer structure matches homepage footer
- [ ] All footer links work
- [ ] Copyright notice present
- [ ] Footer links organized in same sections

### Styling Consistency
For each page, verify:
- [ ] Uses same Tailwind config colors
- [ ] Uses same font families (serif for headings)
- [ ] Uses same spacing/padding
- [ ] Uses same border styles
- [ ] Uses same button styles
- [ ] Mobile responsive breakpoints consistent

## Error Handling

### 404 Errors
- [ ] No footer links return 404 errors
- [ ] All internal links resolve correctly
- [ ] External links (if any) are valid

### Broken Links
- [ ] All anchor links (`#calculator`, `#pricing`, `#partners`) work
- [ ] All relative links (`/api.html`) work
- [ ] All absolute links work

## Mobile Testing

For each page:
- [ ] Mobile menu opens/closes correctly
- [ ] Content is readable on mobile
- [ ] Links are tappable (not too small)
- [ ] Footer is accessible and scrollable
- [ ] No horizontal scrolling required
- [ ] Forms (if any) are mobile-friendly

## Browser Compatibility

Test each page in:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (latest)
- [ ] Edge (latest)

## Performance

- [ ] Pages load in < 3 seconds
- [ ] No console errors
- [ ] No broken images
- [ ] CSS loads correctly
- [ ] JavaScript (if any) works

## Content Verification

### API Documentation (`/api.html`)
- [ ] Authentication section explains API keys
- [ ] Request/response examples are accurate
- [ ] Status codes match actual API behavior
- [ ] Rate limits match actual limits
- [ ] Code examples are copy-paste ready
- [ ] State codes list is complete (28 states)
- [ ] Role values are correct

### Terms of Service (`/terms.html`)
- [ ] Broker payout terms section present
- [ ] 60-day hold period clearly stated
- [ ] Commission models explained
- [ ] Refund/chargeback policy clear
- [ ] Governing law clause present
- [ ] Termination clause present
- [ ] Data retention policy present
- [ ] Links to privacy policy work

### Help Center (`/help.html`)
- [ ] Broker Program section present
- [ ] All 6 broker payout FAQ items present
- [ ] Answers match broker dashboard FAQ
- [ ] Getting Started section helpful
- [ ] API Integration section helpful
- [ ] Contact information correct

## Accessibility

- [ ] All images have alt text
- [ ] Links have descriptive text
- [ ] Headings are properly nested (h1 → h2 → h3)
- [ ] Color contrast meets WCAG AA standards
- [ ] Keyboard navigation works
- [ ] Screen reader friendly (test with NVDA/JAWS)

## SEO

- [ ] Each page has unique `<title>` tag
- [ ] Each page has unique `<meta name="description">`
- [ ] Headings use proper hierarchy
- [ ] Internal links use descriptive anchor text
- [ ] No duplicate content issues

## Summary

After completing all checks:
- [ ] All footer links work (no 404s)
- [ ] All pages have consistent header/footer
- [ ] All pages are mobile responsive
- [ ] All content is accurate and up-to-date
- [ ] No broken links or errors
- [ ] Blog and Careers links removed from footer

## Notes

- If any page fails a check, note the issue and fix it
- Test on both desktop and mobile
- Verify in multiple browsers
- Check console for JavaScript errors
- Verify all email links work (mailto: links)

