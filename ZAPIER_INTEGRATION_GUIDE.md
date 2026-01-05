# Zapier Integration Frontend - Implementation Guide

## Overview

The Zapier integration frontend has been successfully added to `customer-dashboard.html`. It provides a user-friendly interface for users to access their webhook URLs and set up Zapier automations.

## Files Created/Modified

### 1. **New Files Created:**
- `zapier-integration.html` - Standalone HTML snippet (for reference)
- `zapier-integration.js` - Standalone JavaScript file (for reference)
- `ZAPIER_INTEGRATION_GUIDE.md` - This guide

### 2. **Modified Files:**
- `lien-api-landing/customer-dashboard.html` - Added Zapier section and JavaScript functions

## Implementation Details

### HTML Section Location

The Zapier integration card has been added **after the Projects table** (Calculation History section), before the main script tag:

```html
<!-- Location: After line 1711 (after </div> closing the calculation history section) -->
<!-- Zapier Automations Integration Section -->
<div class="bg-orange-50 border border-orange-200 rounded-lg p-6 mb-8" id="zapier-section">
    <!-- Full card content -->
</div>
```

### JavaScript Functions Added

The following functions were added to the dashboard:

1. **`loadZapierUrls()`** - Dynamically loads webhook URLs based on current domain
2. **`setDefaultZapierUrls()`** - Fallback function to set default URLs
3. **`copyToClipboard(inputId)`** - Copies URL to clipboard with visual feedback

### Styling

The Zapier card matches the existing integration cards:
- **Background**: `bg-orange-50` with `border-orange-200` (orange theme)
- **Icon**: Orange rounded square with Zapier-style icon
- **Buttons**: Orange primary button, white secondary button
- **Inputs**: Read-only inputs with copy buttons
- **Responsive**: Works on mobile and desktop

## Features

### 1. Dynamic URL Loading
- URLs are automatically constructed from `window.location.origin`
- Webhook URL: `/api/zapier/webhook/invoice`
- Trigger URL: `/api/zapier/trigger/upcoming?limit=10`

### 2. Copy to Clipboard
- One-click copy functionality
- Visual feedback (button changes to "✓ Copied!" with green styling)
- Fallback alert if clipboard API fails

### 3. External Links
- **View Popular Zaps**: Links to `https://zapier.com/apps/liendeadline/integrations`
- **Zapier Setup Guide**: Links to Zapier's help documentation
- **Report Issue**: Uses existing `reportIntegrationIssue()` function

## Usage Instructions

### For Users:

1. **Access the Integration**
   - Navigate to the customer dashboard
   - Scroll down to "Zapier Automations" section (below Projects table)
   - Webhook URLs are automatically loaded

2. **Copy Webhook URLs**
   - Click the "📋 Copy" button next to any URL
   - URL is copied to clipboard
   - Paste into Zapier webhook configuration

3. **Set Up Zapier Workflows**
   - Use "Webhook URL (Create Invoice)" for POST requests
   - Use "Trigger URL (Upcoming Deadlines)" for polling triggers
   - Click "View Popular Zaps" to see example workflows

### For Developers:

#### Testing the Integration:

1. **Load Dashboard**
   ```bash
   # Start your local server
   # Navigate to /customer-dashboard.html
   ```

2. **Check Console**
   - Open browser DevTools
   - Look for: `✅ Zapier URLs loaded successfully`
   - Verify URLs are correct

3. **Test Copy Function**
   - Click "Copy" button
   - Verify clipboard contains correct URL
   - Check visual feedback (button changes)

#### Customization:

**Change Colors:**
- Edit `bg-orange-50`, `border-orange-200`, `bg-orange-600` classes
- Replace with your preferred color scheme

**Add More Endpoints:**
- Add new input fields following the same pattern
- Update `loadZapierUrls()` function to populate them

**Modify URLs:**
- Edit the URL construction in `loadZapierUrls()`
- Add query parameters or modify paths as needed

## API Endpoints Used

### POST `/api/zapier/webhook/invoice`
- **Purpose**: Create project from invoice data
- **Auth**: Bearer token required
- **Body**: JSON with invoice_date, state, project_name, etc.

### GET `/api/zapier/trigger/upcoming`
- **Purpose**: Get upcoming projects (lien_deadline > today)
- **Auth**: Bearer token required
- **Query Params**: `limit` (default: 10)

## Security Notes

- ✅ All endpoints require authentication (Bearer token)
- ✅ URLs are user-specific (extracted from token)
- ✅ Rate limiting applied (10/min POST, 30/min GET)
- ✅ Input validation on backend
- ✅ SQL injection protection via parameterized queries

## Troubleshooting

### URLs Show "Loading..."
- **Cause**: JavaScript not executing or token missing
- **Fix**: Check browser console for errors, verify `session_token` in localStorage

### Copy Button Doesn't Work
- **Cause**: Clipboard API not available or browser security restrictions
- **Fix**: User can manually select and copy text

### URLs Are Wrong Domain
- **Cause**: `window.location.origin` returning incorrect value
- **Fix**: Hardcode base URL or use environment variable

## Next Steps

1. **Test in Production**
   - Deploy to staging/production
   - Verify URLs work correctly
   - Test with actual Zapier workflows

2. **Add Documentation**
   - Create Zapier app page (if applicable)
   - Document request/response formats
   - Add example Zap templates

3. **Monitor Usage**
   - Track webhook calls in logs
   - Monitor error rates
   - Collect user feedback

## Example Zapier Workflow

### Workflow 1: Auto-Create Project from QuickBooks Invoice

1. **Trigger**: New Invoice in QuickBooks
2. **Action**: Webhook POST to `/api/zapier/webhook/invoice`
3. **Data Mapping**:
   ```json
   {
     "invoice_date": "{{Invoice Date}}",
     "state": "{{Customer State}}",
     "project_name": "{{Invoice Number}}",
     "client_name": "{{Customer Name}}",
     "invoice_amount": {{Total Amount}}
   }
   ```

### Workflow 2: Daily Deadline Reminders

1. **Trigger**: Schedule (Daily at 9 AM)
2. **Action**: Webhook GET `/api/zapier/trigger/upcoming?limit=10`
3. **Action**: Send email/SMS for each project with upcoming deadline

## Support

For issues or questions:
- Check browser console for errors
- Verify authentication token is valid
- Test endpoints directly with curl/Postman
- Contact support@liendeadline.com

