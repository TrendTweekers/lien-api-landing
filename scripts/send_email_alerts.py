#!/usr/bin/env python3
"""
Scheduled email alert sender for LienDeadline.

Sends deadline reminders (7, 3, 1 days before) to users who have enabled email alerts.

Run this script daily (e.g., via Railway cron or scheduled job):
    railway run python scripts/send_email_alerts.py

Or manually:
    python scripts/send_email_alerts.py
"""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path so we can import api modules
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

# Import email sender from api/services/email.py
try:
    from api.services.email import send_email_sync
except ImportError as e:
    print(f"ERROR: Could not import email sender: {e}")
    print("Make sure api/services/email.py exists and send_email_sync function is available")
    sys.exit(1)


def get_conn():
    """Get PostgreSQL database connection"""
    db_url = os.environ.get("DATABASE_URL", "")
    if not (db_url.startswith("postgres://") or db_url.startswith("postgresql://")):
        raise RuntimeError(
            "send_email_alerts.py must run against Postgres production DATABASE_URL. "
            f"Got: {db_url[:30] if db_url else 'None'}..."
        )
    return psycopg2.connect(db_url)


def main():
    """Main function to send email alerts for upcoming deadlines"""
    conn = get_conn()
    conn.autocommit = True

    today = date.today()
    windows = [7, 3, 1]  # Days before deadline to send reminders

    emails_sent = 0
    errors = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Fetch users who enabled email alerts and have an email set
        cur.execute(
            """
            SELECT id, email, alert_email
            FROM users
            WHERE email_alerts_enabled = TRUE
              AND alert_email IS NOT NULL
              AND alert_email <> ''
            """
        )
        users = cur.fetchall()

        if not users:
            print("No users with email alerts enabled")
            return 0

        print(f"Found {len(users)} users with email alerts enabled")

        for u in users:
            user_id = u["id"]
            user_email = u["email"]  # For joining with calculations table
            alert_email = u["alert_email"]  # Where to send alerts

            for days_before in windows:
                target = today + timedelta(days=days_before)

                # Pull projects whose deadlines match target date
                # Note: calculations table uses user_email, not user_id
                # We match on both prelim_deadline and lien_deadline
                cur.execute(
                    """
                    SELECT 
                        id, 
                        project_name, 
                        state_code as state,
                        prelim_deadline, 
                        lien_deadline
                    FROM calculations
                    WHERE user_email = %s
                      AND (
                        prelim_deadline = %s
                        OR lien_deadline = %s
                      )
                    ORDER BY lien_deadline ASC, prelim_deadline ASC
                    """,
                    (user_email, target, target),
                )
                projects = cur.fetchall()

                for p in projects:
                    # For each deadline type hit today, send one email (deduped via email_alert_sends)
                    for dtype, col in [("prelim", "prelim_deadline"), ("lien", "lien_deadline")]:
                        deadline_date = p.get(col)
                        if deadline_date != target:
                            continue

                        # Dedup guard - check if we already sent this reminder
                        try:
                            cur.execute(
                                """
                                INSERT INTO email_alert_sends (
                                    user_id, project_id, deadline_type, days_before, deadline_date
                                )
                                VALUES (%s, %s, %s, %s, %s)
                                """,
                                (user_id, p["id"], dtype, days_before, target),
                            )
                        except psycopg2.IntegrityError:
                            # Duplicate -> already sent, skip
                            continue
                        except Exception as e:
                            errors.append(f"Error inserting dedup record: {e}")
                            continue

                        # Build email content
                        project_name = p.get("project_name") or "Untitled Project"
                        state = p.get("state") or "-"
                        
                        subject = f"LienDeadline Reminder: {dtype.upper()} deadline in {days_before} day(s)"
                        
                        # Plain text email body
                        body_text = f"""Reminder: {dtype.upper()} deadline is in {days_before} day(s).

Project: {project_name}
State: {state}
Due date: {target.isoformat()}

Open dashboard: https://liendeadline.com/dashboard

---
This is an automated reminder from LienDeadline.
"""

                        # Send email
                        try:
                            success = send_email_sync(
                                to_email=alert_email,
                                subject=subject,
                                content=body_text,
                                is_html=False,  # Plain text for simplicity
                            )
                            
                            if success:
                                emails_sent += 1
                                print(f"✅ Sent {dtype} reminder to {alert_email} for project '{project_name}' ({days_before} days before)")
                            else:
                                errors.append(f"Failed to send email to {alert_email} for project {p['id']}")
                        except Exception as e:
                            errors.append(f"Exception sending email to {alert_email}: {e}")

    conn.close()
    
    print(f"\n✅ Email alerts processed: {emails_sent} emails sent")
    if errors:
        print(f"⚠️ Errors encountered: {len(errors)}")
        for error in errors[:10]:  # Print first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")
    
    return emails_sent


if __name__ == "__main__":
    try:
        emails_sent = main()
        sys.exit(0 if emails_sent >= 0 else 1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

