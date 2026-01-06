# Railway Cron Job Setup for Email Reminders

This document explains how to configure Railway to run the daily email reminder cron job.

## Overview

The email alerts cron job runs automatically on application startup when Railway sets the `RAILWAY_CRON_RUN=true` environment variable. This is the cleanest approach - no HTTP endpoints or secrets needed. Railway automatically injects this environment variable during cron runs.

## How It Works

When Railway runs a cron job, it sets `RAILWAY_CRON_RUN=true`. The FastAPI application detects this on startup and automatically executes the email alerts job before starting the web server.

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
       python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT
       ```
     - **Note**: Railway automatically sets `RAILWAY_CRON_RUN=true` when running cron jobs, which triggers the email alerts job on startup
   - Click **"Save"** or **"Create"**

### Method 2: Railway CLI (Alternative)

If Railway CLI supports cron configuration:

```bash
railway cron add \
  --name "Send Email Reminders" \
  --schedule "0 9 * * *" \
  --command "python -m uvicorn api.main:app --host 0.0.0.0 --port \$PORT"
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

## Monitoring

### Check Logs

Railway logs will show cron job execution:
- Look for: `🕐 Railway cron run detected - executing email alerts job...`
- Success: `✅ Email alerts job completed: X emails sent`
- Failure: `❌ Email alerts job failed: [error message]`

### Expected Output

When the cron job runs successfully, you should see:
```
🚀 Starting application...
🕐 Railway cron run detected - executing email alerts job...
✅ Email alerts job completed: 5 emails sent
✅ Application startup complete
```

## Troubleshooting

**Cron job not running:**
- Verify the schedule syntax is correct
- Check that the command matches your app's startup command
- Ensure Railway is setting `RAILWAY_CRON_RUN=true` (check logs)
- Check Railway logs for cron execution errors

**Emails not sending:**
- Verify `RESEND_API_KEY` is set correctly in Railway environment variables
- Check `DATABASE_URL` is set correctly
- Review error logs in Railway dashboard
- Check Resend dashboard for email delivery status

**Database connection errors:**
- Verify `DATABASE_URL` is set correctly
- Check database is accessible from Railway
- Review connection logs

**Job runs but no emails sent:**
- Check that users have `email_alerts_enabled = TRUE` in the database
- Verify users have `alert_email` set
- Check that there are projects with deadlines matching the reminder windows (7, 3, 1 days)

## Testing Locally

To test the cron job locally, simulate Railway's behavior:

```bash
# Set RAILWAY_CRON_RUN environment variable
export RAILWAY_CRON_RUN=true

# Run the app (it will execute the email job on startup)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

You should see the email alerts job execute during startup.

## Manual Trigger (Admin)

Admins can also trigger email alerts manually via the admin dashboard:
- Navigate to `/admin-dashboard-v2`
- Use the "Run email alerts now" button (if available)
- This uses the HTTP endpoint `/api/admin/run-email-alerts` (requires CRON_SECRET header)

## Alternative: HTTP Endpoint Method

If you prefer to use HTTP endpoints instead of startup detection, you can use the `/api/admin/run-email-alerts` endpoint with `X-CRON-SECRET` header authentication. See the git history for the previous implementation.
