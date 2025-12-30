import os
import sys
from pathlib import Path
from datetime import datetime, date

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.email import send_email_sync, RESEND_AVAILABLE

def get_db_connection():
    """Get database connection (PostgreSQL or SQLite)"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        # PostgreSQL
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(DATABASE_URL)
        return conn, RealDictCursor, 'postgresql'
    else:
        # SQLite fallback
        import sqlite3
        from api.database import BASE_DIR
        db_path = BASE_DIR / "liendeadline.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn, None, 'sqlite'

def send_daily_reminders():
    """
    Daily cron job to send email reminders
    Run this at 9:00 AM every day
    """
    
    print(f"\n{'='*60}")
    print(f"🔔 RUNNING EMAIL REMINDER CRON JOB")
    print(f"{'='*60}")
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not RESEND_AVAILABLE:
        print("❌ Resend library not available. Cannot send emails.")
        return
    
    if not os.getenv('RESEND_API_KEY'):
        print("❌ RESEND_API_KEY not set. Cannot send emails.")
        return
    
    try:
        # Connect to database
        conn, cursor_factory, db_type = get_db_connection()
        
        if db_type == 'postgresql':
            cursor = conn.cursor(cursor_factory=cursor_factory)
        else:
            cursor = conn.cursor()
        
        # Find reminders that should be sent today
        today = date.today()
        
        if db_type == 'postgresql':
            cursor.execute("""
                SELECT 
                    r.id,
                    r.user_email,
                    r.project_name,
                    r.client_name,
                    r.invoice_amount,
                    r.state,
                    r.notes,
                    r.deadline_type,
                    r.deadline_date,
                    r.days_before,
                    c.state_code,
                    c.invoice_date
                FROM email_reminders r
                JOIN calculations c ON r.calculation_id = c.id
                WHERE r.send_date = %s
                AND r.alert_sent = FALSE
                ORDER BY r.deadline_date ASC
            """, (today,))
        else:
            # SQLite
            cursor.execute("""
                SELECT 
                    r.id,
                    r.user_email,
                    r.project_name,
                    r.client_name,
                    r.invoice_amount,
                    r.state,
                    r.notes,
                    r.deadline_type,
                    r.deadline_date,
                    r.days_before,
                    c.state_code,
                    c.invoice_date
                FROM email_reminders r
                JOIN calculations c ON r.calculation_id = c.id
                WHERE r.send_date = ?
                AND r.alert_sent = 0
                ORDER BY r.deadline_date ASC
            """, (today.strftime('%Y-%m-%d'),))
        
        reminders = cursor.fetchall()
        
        # Convert SQLite rows to dict-like objects
        if db_type == 'sqlite':
            reminders = [dict(row) for row in reminders]
        
        print(f"📧 Found {len(reminders)} reminders to send today")
        
        if len(reminders) == 0:
            print("✅ No reminders to send today")
            cursor.close()
            conn.close()
            return
        
        sent_count = 0
        failed_count = 0
        
        for reminder in reminders:
            try:
                # Send the email
                send_reminder_email(reminder)
                
                # Mark as sent
                if db_type == 'postgresql':
                    cursor.execute("""
                        UPDATE email_reminders 
                        SET alert_sent = TRUE, sent_at = %s 
                        WHERE id = %s
                    """, (datetime.now(), reminder['id']))
                else:
                    cursor.execute("""
                        UPDATE email_reminders 
                        SET alert_sent = 1, sent_at = ? 
                        WHERE id = ?
                    """, (datetime.now().isoformat(), reminder['id']))
                
                conn.commit()
                sent_count += 1
                
                print(f"  ✅ Sent: {reminder['project_name']} → {reminder['user_email']}")
                
            except Exception as e:
                failed_count += 1
                print(f"  ❌ Failed: {reminder['project_name']} → {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Try to log the error to database (don't fail if this fails)
                try:
                    if db_type == 'postgresql':
                        cursor.execute("""
                            INSERT INTO error_logs (
                                error_type, 
                                error_message, 
                                context, 
                                created_at
                            ) VALUES (%s, %s, %s, %s)
                        """, (
                            'email_reminder_failed',
                            str(e),
                            f"Reminder ID: {reminder['id']}, Project: {reminder['project_name']}",
                            datetime.now()
                        ))
                    else:
                        # SQLite - create table if needed
                        cursor.execute("""
                            CREATE TABLE IF NOT EXISTS error_logs (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                error_type TEXT,
                                error_message TEXT,
                                context TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        cursor.execute("""
                            INSERT INTO error_logs (
                                error_type, 
                                error_message, 
                                context, 
                                created_at
                            ) VALUES (?, ?, ?, ?)
                        """, (
                            'email_reminder_failed',
                            str(e),
                            f"Reminder ID: {reminder['id']}, Project: {reminder['project_name']}",
                            datetime.now().isoformat()
                        ))
                    conn.commit()
                except Exception as log_error:
                    print(f"  ⚠️ Could not log error: {log_error}")
        
        cursor.close()
        conn.close()
        
        print(f"\n{'='*60}")
        print(f"📊 SUMMARY:")
        print(f"   Total reminders: {len(reminders)}")
        print(f"   ✅ Sent successfully: {sent_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

def send_reminder_email(reminder):
    """Send a single reminder email with project details"""
    
    if not RESEND_AVAILABLE:
        raise Exception("Resend library not available")
    
    # Format the deadline date
    deadline_date = datetime.strptime(str(reminder['deadline_date']), '%Y-%m-%d')
    formatted_deadline = deadline_date.strftime('%B %d, %Y')
    day_of_week = deadline_date.strftime('%A')
    
    # Calculate urgency
    days_until = (deadline_date.date() - date.today()).days
    
    if days_until < 0:
        urgency = "⚠️ OVERDUE"
        urgency_color = "#dc2626"
    elif days_until <= 1:
        urgency = "🔴 URGENT"
        urgency_color = "#ea580c"
    elif days_until <= 7:
        urgency = "🟡 SOON"
        urgency_color = "#f59e0b"
    else:
        urgency = "🟢 UPCOMING"
        urgency_color = "#16a34a"
    
    # Format deadline type
    deadline_type_display = "Preliminary Notice" if reminder['deadline_type'] == 'preliminary' else "Lien Filing"
    
    # Format invoice amount
    amount_display = f"${reminder['invoice_amount']:,.2f}" if reminder['invoice_amount'] else "Not specified"
    
    # Create email HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color:#f3f4f6;">
        
        <!-- Main Container -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6; padding:20px 0;">
            <tr>
                <td align="center">
                    
                    <!-- Email Card -->
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:white; border-radius:8px; box-shadow:0 4px 6px rgba(0,0,0,0.1); overflow:hidden;">
                        
                        <!-- Header -->
                        <tr>
                            <td style="background-color:#1e3a8a; padding:30px; text-align:center;">
                                <h1 style="margin:0; color:white; font-size:24px; font-weight:600;">
                                    ⚠️ Lien Deadline Reminder
                                </h1>
                                <p style="margin:10px 0 0 0; color:#e0e7ff; font-size:14px;">
                                    {urgency} - {abs(days_until)} day{'s' if abs(days_until) != 1 else ''} {'overdue' if days_until < 0 else 'remaining'}
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Body -->
                        <tr>
                            <td style="padding:40px 30px;">
                                
                                <!-- Greeting -->
                                <p style="margin:0 0 20px 0; font-size:16px; color:#374151;">
                                    Your <strong>{deadline_type_display}</strong> deadline is coming up:
                                </p>
                                
                                <!-- Project Details Box -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f9fafb; border:2px solid #e5e7eb; border-radius:8px; margin-bottom:30px;">
                                    <tr>
                                        <td style="padding:20px;">
                                            <h2 style="margin:0 0 15px 0; font-size:18px; color:#1e3a8a;">
                                                📋 Project Details
                                            </h2>
                                            
                                            <table width="100%" cellpadding="8" cellspacing="0">
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600; width:140px;">Project:</td>
                                                    <td style="color:#111827; font-weight:600;">{reminder['project_name']}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Client:</td>
                                                    <td style="color:#111827;">{reminder['client_name']}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Amount:</td>
                                                    <td style="color:#111827;">{amount_display}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">State:</td>
                                                    <td style="color:#111827;">{reminder['state']}</td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                                
                                <!-- Deadline Info Box -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#fef2f2; border:2px solid {urgency_color}; border-radius:8px; margin-bottom:30px;">
                                    <tr>
                                        <td style="padding:20px;">
                                            <h2 style="margin:0 0 15px 0; font-size:18px; color:{urgency_color};">
                                                ⏰ Deadline Information
                                            </h2>
                                            
                                            <table width="100%" cellpadding="8" cellspacing="0">
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600; width:140px;">Deadline Type:</td>
                                                    <td style="color:#111827; font-weight:600;">{deadline_type_display}</td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Due Date:</td>
                                                    <td style="color:{urgency_color}; font-weight:700; font-size:18px;">
                                                        {formatted_deadline} ({day_of_week})
                                                    </td>
                                                </tr>
                                                <tr>
                                                    <td style="color:#6b7280; font-weight:600;">Days Left:</td>
                                                    <td style="color:{urgency_color}; font-weight:700; font-size:18px;">
                                                        {abs(days_until)} day{'s' if abs(days_until) != 1 else ''} {'overdue' if days_until < 0 else ''}
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                                
                                {f'''
                                <!-- Notes -->
                                <div style="background-color:#fffbeb; border-left:4px solid #f59e0b; padding:15px; margin-bottom:30px;">
                                    <p style="margin:0; color:#92400e; font-size:14px;">
                                        <strong>📝 Your Notes:</strong><br>
                                        {reminder['notes']}
                                    </p>
                                </div>
                                ''' if reminder.get('notes') else ''}
                                
                                <!-- Action Buttons -->
                                <table width="100%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="padding:20px 0;">
                                            <a href="https://liendeadline.com/customer-dashboard" 
                                               style="display:inline-block; background-color:#f97316; color:white; text-decoration:none; padding:14px 28px; border-radius:6px; font-weight:600; font-size:16px; margin:0 5px;">
                                                View Dashboard
                                            </a>
                                            <a href="https://liendeadline.com/api/v1/guide/{reminder['state_code']}/pdf?invoice_date={reminder['invoice_date']}&state_name={reminder['state']}" 
                                               style="display:inline-block; background-color:#3b82f6; color:white; text-decoration:none; padding:14px 28px; border-radius:6px; font-weight:600; font-size:16px; margin:0 5px;">
                                                Download PDF Guide
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color:#f9fafb; padding:20px 30px; border-top:1px solid #e5e7eb;">
                                <p style="margin:0 0 10px 0; font-size:12px; color:#6b7280; text-align:center;">
                                    Questions? Reply to this email or visit 
                                    <a href="https://liendeadline.com/help" style="color:#f97316;">our help center</a>
                                </p>
                                <p style="margin:0; font-size:11px; color:#9ca3af; text-align:center;">
                                    You're receiving this because you set a reminder at LienDeadline.com<br>
                                    <a href="https://liendeadline.com/customer-dashboard" style="color:#9ca3af;">Manage your reminders</a>
                                </p>
                            </td>
                        </tr>
                        
                    </table>
                    
                </td>
            </tr>
        </table>
        
    </body>
    </html>
    """
    
    # Format subject line
    if days_until < 0:
        subject = f"⚠️ OVERDUE: {deadline_type_display} Deadline for {reminder['project_name']}"
    else:
        subject = f"⚠️ {deadline_type_display} Deadline in {days_until} Day{'s' if days_until != 1 else ''}: {reminder['project_name']}"
    
    # Send via centralized service
    send_email_sync(
        to_email=reminder['user_email'],
        subject=subject,
        content=html_content
    )

def update_referral_statuses():
    """
    Update referrals that have passed their hold period
    Move from 'on_hold' to 'pending' (ready for payout)
    """
    print(f"\n{'='*60}")
    print(f"💰 UPDATING REFERRAL STATUSES")
    print(f"{'='*60}")
    
    try:
        conn, cursor_factory, db_type = get_db_connection()
        if db_type == 'postgresql':
            cursor = conn.cursor(cursor_factory=cursor_factory)
        else:
            cursor = conn.cursor()
            
        today_str = date.today().isoformat()
        
        # Select referrals to update for logging
        if db_type == 'postgresql':
            cursor.execute("""
                SELECT id, broker_id, customer_email 
                FROM referrals 
                WHERE status = 'on_hold' 
                AND hold_until <= %s
            """, (today_str,))
        else:
            cursor.execute("""
                SELECT id, broker_id, customer_email 
                FROM referrals 
                WHERE status = 'on_hold' 
                AND hold_until <= ?
            """, (today_str,))
            
        referrals = cursor.fetchall()
        
        if not referrals:
            print("No referrals to update.")
            return
            
        print(f"Found {len(referrals)} referrals ready for release:")
        for r in referrals:
            print(f"- Referral {r['id']} (Broker: {r['broker_id']}, Customer: {r['customer_email']})")
            
        # Update status
        if db_type == 'postgresql':
            cursor.execute("""
                UPDATE referrals 
                SET status = 'pending' 
                WHERE status = 'on_hold' 
                AND hold_until <= %s
            """, (today_str,))
        else:
            cursor.execute("""
                UPDATE referrals 
                SET status = 'pending' 
                WHERE status = 'on_hold' 
                AND hold_until <= ?
            """, (today_str,))
            
        conn.commit()
        print(f"✅ Successfully updated {cursor.rowcount} referrals to 'pending' status.")
        
    except Exception as e:
        print(f"❌ Error updating referral statuses: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == "__main__":
    send_daily_reminders()
    update_referral_statuses()

