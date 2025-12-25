# Railway Cron Job Setup for Email Reminders

This document explains how to configure Railway to run the daily email reminder cron job.

## Method 1: Railway Web Interface (Recommended)

Railway cron jobs are typically configured through their web dashboard:

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
     - **Command**: `python api/cron_send_reminders.py`
   - Click **"Save"** or **"Create"**

4. **Verify Environment Variables**
   - Ensure these environment variables are set in Railway:
     - `RESEND_API_KEY` - Your Resend API key for sending emails
     - `DATABASE_URL` - Your PostgreSQL connection string

5. **Test the Cron Job**
   - You can test by temporarily changing the schedule to `*/5 * * * *` (every 5 minutes)
   - Check the logs to verify emails are being sent
   - Change back to `0 9 * * *` once confirmed working

## Method 2: Railway CLI (Alternative)

If Railway CLI supports cron configuration:

```bash
railway cron add \
  --name "Send Email Reminders" \
  --schedule "0 9 * * *" \
  --command "python api/cron_send_reminders.py"
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

- Check Railway logs to see cron job execution
- Look for output starting with `🔔 RUNNING EMAIL REMINDER CRON JOB`
- Verify emails are being sent successfully
- Check for any error messages in the logs

## Troubleshooting

**Cron job not running:**
- Verify the schedule syntax is correct
- Check that the command path is correct
- Ensure environment variables are set

**Emails not sending:**
- Verify `RESEND_API_KEY` is set correctly
- Check Resend dashboard for email delivery status
- Review error logs in Railway

**Database connection errors:**
- Verify `DATABASE_URL` is set correctly
- Check database is accessible from Railway
- Review connection logs

