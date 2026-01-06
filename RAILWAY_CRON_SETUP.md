# Railway Cron Job Setup for Email Reminders

This document explains how to configure Railway to run the daily email reminder cron job using HTTP endpoint authentication.

## Overview

The email alerts cron job is triggered via an HTTP POST request to `/api/admin/run-email-alerts`. Authentication is handled via the `X-CRON-SECRET` header, which must match the `CRON_SECRET` environment variable.

## Prerequisites

1. **Set CRON_SECRET Environment Variable**
   - In Railway dashboard, go to your service → **Variables** tab
   - Add a new variable: `CRON_SECRET`
   - Set a strong, random secret value (e.g., generate with: `openssl rand -hex 32`)
   - **Important**: Keep this secret secure and never commit it to git

## Railway Cron Configuration

### Method 1: Railway Web Interface (Recommended)

1. **Go to Railway Dashboard**
   - Navigate to [railway.app](https://railway.app)
   - Log in to your account
   - Select your project

2. **Navigate to Service Settings**
   - Click on your service (the one running your FastAPI app)
   - Go to the **"Settings"** tab
   - Scroll down to find the **"Cron"** section

3. **Add New Cron Job**
   - Click **"New Cron Job"** or **"Add Cron Job"**
   - Configure the following:
     - **Name**: `Send Email Reminders`
     - **Schedule**: `0 9 * * *` (9:00 AM UTC daily)
     - **Command**: 
       ```bash
       curl -sS -X POST https://liendeadline.com/api/admin/run-email-alerts -H "X-CRON-SECRET: $CRON_SECRET"
       ```
     - **Note**: Railway automatically provides environment variables to cron jobs, so `$CRON_SECRET` will be replaced with the actual value
   - Click **"Save"** or **"Create"**

### Method 2: Railway CLI (Alternative)

If Railway CLI supports cron configuration:

```bash
railway cron add \
  --name "Send Email Reminders" \
  --schedule "0 9 * * *" \
  --command "curl -sS -X POST https://liendeadline.com/api/admin/run-email-alerts -H \"X-CRON-SECRET: \$CRON_SECRET\""
```

## Schedule Format

The cron schedule uses standard cron syntax:
- `0 9 * * *` = Every day at 9:00 AM UTC
- `0 14 * * *` = Every day at 2:00 PM UTC (9:00 AM EST)
- `*/5 * * * *` = Every 5 minutes (for testing)

## Timezone Notes

- Railway cron jobs run in **UTC** timezone
- To run at 9:00 AM EST (UTC-5), use `0 14 * * *` (2:00 PM UTC)
- To run at 9:00 AM PST (UTC-8), use `0 17 * * *` (5:00 PM UTC)

## Authentication

The cron endpoint uses header-based authentication:

- **Header Name**: `X-CRON-SECRET`
- **Value**: Must match the `CRON_SECRET` environment variable
- **Comparison**: Uses constant-time comparison (`hmac.compare_digest`) to prevent timing attacks

### Security Notes

- If `CRON_SECRET` is not set, the endpoint returns `503 Service Unavailable`
- Invalid or missing secrets return `401 Unauthorized`
- All authentication attempts are logged with IP addresses

## Monitoring

### Check Logs

- Railway logs will show cron job execution
- Look for log lines:
  - `CRON_OK route=/api/admin/run-email-alerts ip=...` (success)
  - `CRON_DENY route=/api/admin/run-email-alerts ip=... reason=...` (failure)

### Response Format

Successful response:
```json
{
  "ok": true,
  "code": 0,
  "emails_sent": 5,
  "stdout": "...",
  "stderr": "",
  "message": "Email alerts script executed"
}
```

## Troubleshooting

**Cron job returns 503:**
- Verify `CRON_SECRET` environment variable is set in Railway
- Check that the variable name is exactly `CRON_SECRET` (case-sensitive)

**Cron job returns 401:**
- Verify the `X-CRON-SECRET` header is being sent correctly
- Check that the header value matches the `CRON_SECRET` environment variable exactly
- Ensure there are no extra spaces or newlines in the secret

**Cron job not running:**
- Verify the schedule syntax is correct
- Check that the curl command is correct
- Ensure `curl` is available in the Railway cron environment
- Check Railway logs for cron execution errors

**Emails not sending:**
- Verify `RESEND_API_KEY` is set correctly
- Check `DATABASE_URL` is set correctly
- Review the `stdout` and `stderr` fields in the response
- Check Resend dashboard for email delivery status

**Database connection errors:**
- Verify `DATABASE_URL` is set correctly
- Check database is accessible from Railway
- Review connection logs

## Testing Locally

To test the cron endpoint locally:

```bash
# Set CRON_SECRET environment variable
export CRON_SECRET="your-secret-here"

# Test the endpoint
curl -X POST http://localhost:8000/api/admin/run-email-alerts \
  -H "X-CRON-SECRET: your-secret-here"
```

## Manual Trigger (Admin)

Admins can also trigger email alerts manually via the admin dashboard:
- Navigate to `/admin-dashboard-v2`
- Use the "Run email alerts now" button (if available)
- This uses session-based authentication, not CRON_SECRET
