# Partner Welcome Email Structure

## Overview
The partner welcome email is sent when a broker/partner application is approved. There are two functions in the codebase, but `send_welcome_email_background` appears to be the primary one used.

## Function: `send_welcome_email_background`

**Location:** `api/services/email.py` (lines 579-733)

**Parameters:**
- `email`: Partner's email address
- `referral_link`: Their unique referral link (e.g., Tolt link)
- `name`: Partner's name
- `referral_code`: Their referral code (optional)
- `commission_model`: Always "recurring" now (legacy parameter)
- `temp_password`: Temporary password if account creation requires it (optional)

## Email Structure

### 1. Header Section
- **Background:** White card on gray background
- **Logo/Title:** "📋 LienDeadline" with "Partner Program" subtitle
- **Styling:** Centered, professional blue/gray color scheme

### 2. Welcome Message
- **Greeting:** "Welcome, {name}!"
- **Message:** Congratulations on approval, ready to start earning

### 3. Referral Link Box
- **Background:** Light gray box with border
- **Content:** 
  - Label: "Your Referral Link"
  - Link: Clickable referral link (monospace font)
  - Helper text: "Share this link to start earning commissions"

### 4. Commission Structure Section
- **Background:** Light blue box with blue left border
- **Title:** "Your Commission Structure"
- **Content:**
  - **30% Monthly Recurring Commission**
  - Earn 30% of every $299/month subscription ($89.70 per client per month)
  - Commission held for 30 days after customer payment to prevent fraud, then paid monthly
  - Build long-term passive income as long as clients stay active
  - Track all referrals and earnings in your partner dashboard

### 5. How It Works Section
- **Title:** "How it works"
- **Steps:**
  1. Share your referral link with construction companies and contractors
  2. When they sign up and make their first payment, you earn commission
  3. Track all referrals and earnings in your partner dashboard

### 6. CTA Button
- **Button:** "Access Partner Dashboard"
- **Link:** `https://liendeadline.tolt.io/login`
- **Login Info:** Shows email address for login
- **Optional:** Temporary password box (if `temp_password` provided)

### 7. Footer
- **Support:** Questions? Reply to email or contact partners@liendeadline.com
- **Copyright:** © 2025 LienDeadline. All rights reserved.

## Alternative Function: `send_broker_welcome_email`

**Location:** `api/services/email.py` (lines 110-230)

**Simpler version** with:
- Blue header with "📋 LienDeadline Partner Program"
- Welcome message
- Referral details box (code + link)
- Commission structure box (30% recurring)
- "How It Works" numbered list
- Dashboard CTA button
- Footer with contact info

**Note:** This function appears to be the updated one with correct 30% commission structure.

## Current Status

✅ **Updated:** `send_broker_welcome_email` - Has correct 30% commission structure
✅ **Updated:** `send_welcome_email_background` - Just updated to 30% commission structure

Both functions now correctly show:
- 30% monthly recurring commission
- $89.70 per client per month
- 30-day hold period
- Link to Tolt dashboard: `https://liendeadline.tolt.io/login`

## Email Sending

Both functions use `send_email_sync()` which:
1. Tries Resend API first (if available)
2. Falls back to SMTP if Resend unavailable
3. Returns success/failure status

## Subject Line
- `send_broker_welcome_email`: "🎉 Welcome to LienDeadline Partner Program!"
- `send_welcome_email_background`: "Welcome to LienDeadline Partner Program! 🎉"

