import os
import smtplib
import ssl
import logging
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any

# Configure logger
logger = logging.getLogger(__name__)

# Try to import resend
try:
    import resend
    RESEND_AVAILABLE = True
except ImportError:
    resend = None
    RESEND_AVAILABLE = False
    logger.warning("⚠️ Resend package not available - email features may be limited")

def send_email_sync(to_email: str, subject: str, content: str, is_html: bool = True):
    """
    Unified synchronous email sending function.
    Tries Resend first, falls back to SMTP.
    
    Args:
        to_email: Recipient email
        subject: Email subject
        content: Email body (HTML or plain text)
        is_html: Whether content is HTML (default: True)
    """
    # 1. Try Resend
    try:
        resend_key = os.environ.get("RESEND_API_KEY")
        if resend_key and RESEND_AVAILABLE:
            print(f"📧 ATTEMPTING RESEND to {to_email}...")
            resend.api_key = resend_key
            from_email = os.environ.get("SMTP_FROM_EMAIL", "onboarding@resend.dev")
            
            params = {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
            }
            
            if is_html:
                params["html"] = content
            else:
                params["text"] = content
                
            response = resend.Emails.send(params)
            print(f"✅ RESEND SUCCESS: {response}")
            logger.info(f"✅ Email sent via Resend to {to_email}: {response.get('id', 'N/A')}")
            return True
    except Exception as e:
        print(f"⚠️ RESEND FAILED: {e}. Falling back to SMTP...")
        logger.warning(f"⚠️ Resend failed, trying SMTP: {e}")

    # 2. Fallback to SMTP
    try:
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_user = os.getenv("SMTP_USER") or os.getenv("SMTP_EMAIL")
        smtp_password = (os.getenv("SMTP_PASSWORD") or "").replace(" ", "")
        
        # Use explicit From address if set, otherwise default to user
        smtp_from = os.getenv("SMTP_FROM_EMAIL") or smtp_user

        print(f"📧 ATTEMPTING SMTP to {to_email} via {smtp_server}:{smtp_port}...")
        print(f"📧 From: {smtp_from}")

        if not smtp_user or not smtp_password:
            logger.warning("⚠️ SMTP credentials not configured")
            return False

        msg = MIMEMultipart('alternative')
        msg["From"] = smtp_from
        msg["To"] = to_email
        msg["Subject"] = subject
        
        if is_html:
            msg.attach(MIMEText(content, "html"))
        else:
            msg.attach(MIMEText(content, "plain"))

        print("📧 Connecting to SMTP server...")
        with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
            server.ehlo()
            print("📧 SMTP EHLO success.")
            server.starttls(context=ssl.create_default_context())
            print("📧 SMTP STARTTLS success.")
            server.ehlo()
            print(f"📧 Logging in as {smtp_user}...")
            server.login(smtp_user, smtp_password)
            print("📧 SMTP Login success. Sending message...")
            server.send_message(msg)
            print("✅ SMTP SEND_MESSAGE success.")
            
        print("✅ EMAIL SENT SUCCESSFULLY.")
        logger.info(f"✅ Email sent via SMTP to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Email sending failed (Resend & SMTP): {e}")
        traceback.print_exc()
        return False

def send_broker_welcome_email(email: str, name: str, link: str, code: str):
    """Send broker welcome email with referral link"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color:#f3f4f6; line-height:1.6;">
        
        <!-- Main Container -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6; padding:40px 20px;">
            <tr>
                <td align="center">
                    
                    <!-- Email Card -->
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:white; border-radius:8px; box-shadow:0 4px 6px rgba(0,0,0,0.1); overflow:hidden;">
                        
                        <!-- Header -->
                        <tr>
                            <td style="background-color:#1e3a8a; padding:35px 30px; text-align:center;">
                                <h1 style="margin:0; color:white; font-size:28px; font-weight:700; letter-spacing:-0.5px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                    📋 LienDeadline Partner Program
                                </h1>
                                <p style="margin:10px 0 0 0; color:#e0e7ff; font-size:16px; font-weight:500;">
                                    Welcome! Start earning commissions today 🎉
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Welcome Message -->
                        <tr>
                            <td style="padding:40px 30px;">
                                <h2 style="margin:0 0 20px 0; font-size:24px; font-weight:600; color:#1f2937; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; letter-spacing:-0.3px;">
                                    Congratulations, {name}!
                                </h2>
                                <p style="margin:0 0 28px 0; font-size:16px; color:#4b5563; line-height:1.7;">
                                    Your partner account is now active. Share your referral link with construction clients and start earning commissions.
                                </p>
                                
                                <!-- Referral Details Box -->
                                <div style="background-color:#f9fafb; border:2px solid #e5e7eb; border-radius:8px; padding:24px; margin-bottom:30px;">
                                    <h3 style="margin:0 0 18px 0; font-size:18px; font-weight:600; color:#1e3a8a; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        Your Referral Details
                                    </h3>
                                    <table width="100%" cellpadding="10" cellspacing="0" style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; width:140px; font-size:14px; padding:10px 0; vertical-align:top;">Referral Code:</td>
                                            <td style="padding:10px 0;"><code style="background:#f1f5f9; padding:8px 12px; border-radius:6px; font-size:16px; font-family:'Courier New', 'Monaco', monospace; font-weight:700; letter-spacing:1px; color:#1f2937;">{code}</code></td>
                                        </tr>
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; font-size:14px; padding:10px 0; vertical-align:top;">Referral Link:</td>
                                            <td style="padding:10px 0;"><a href="{link}" style="color:#1e3a8a; word-break:break-all; text-decoration:none; font-weight:500;">{link}</a></td>
                                        </tr>
                                    </table>
                                </div>
                                
                                <!-- Commission Structure Box -->
                                <div style="background-color:#fef3c7; border-left:4px solid #f59e0b; border-radius:4px; padding:20px; margin-bottom:30px;">
                                    <h3 style="margin:0 0 14px 0; font-size:18px; font-weight:600; color:#92400e; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        💰 Commission Structure
                                    </h3>
                                    <ul style="margin:0; padding-left:24px; color:#92400e; line-height:1.8; font-size:15px;">
                                        <li style="margin-bottom:8px; padding-left:4px;"><strong style="font-weight:600;">30% Monthly Recurring Commission</strong></li>
                                        <li style="margin-bottom:8px; padding-left:4px;">Earn $89.70 per month for every active client ($299/mo subscription)</li>
                                        <li style="margin-bottom:0; padding-left:4px;">30-day hold period for fraud prevention</li>
                                    </ul>
                                </div>
                                
                                <!-- How It Works -->
                                <div style="margin-bottom:30px;">
                                    <h3 style="margin:0 0 18px 0; font-size:20px; font-weight:600; color:#1f2937; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; letter-spacing:-0.2px;">
                                        How It Works
                                    </h3>
                                    <ol style="margin:0; padding-left:24px; color:#4b5563; line-height:1.8; font-size:15px;">
                                        <li style="margin-bottom:14px; padding-left:4px;">Share your referral link with construction clients</li>
                                        <li style="margin-bottom:14px; padding-left:4px;">When they sign up for LienDeadline Pro ($299/month), you earn a commission</li>
                                        <li style="margin-bottom:14px; padding-left:4px;">Track all referrals in your dashboard</li>
                                        <li style="margin-bottom:0; padding-left:4px;">Get paid monthly via PayPal or bank transfer</li>
                                    </ol>
                                </div>
                                
                                <!-- CTA Button -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                                    <tr>
                                        <td align="center" style="padding:12px 0;">
                                            <a href="https://liendeadline.tolt.io/login" 
                                               style="display:inline-block; background-color:#1e3a8a; color:#ffffff; text-decoration:none; padding:18px 36px; border-radius:8px; font-weight:700; font-size:16px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; box-shadow:0 4px 12px rgba(30,58,138,0.3); letter-spacing:0.3px;">
                                                View Your Dashboard →
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color:#f9fafb; padding:25px 30px; border-top:1px solid #e5e7eb;">
                                <p style="margin:0 0 12px 0; font-size:14px; color:#4b5563; text-align:center; line-height:1.6;">
                                    Questions? Reply to this email or contact 
                                    <a href="mailto:partners@liendeadline.com" style="color:#1e3a8a; text-decoration:none; font-weight:600;">partners@liendeadline.com</a>
                                </p>
                                <p style="margin:0; font-size:12px; color:#9ca3af; text-align:center;">
                                    © {datetime.now().year} LienDeadline. All rights reserved.
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
    
    return send_email_sync(email, "🎉 Welcome to LienDeadline Partner Program!", html)

def send_welcome_email(email: str, temp_password: str):
    """Send welcome email with login credentials - Improved version"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color:#f3f4f6; line-height:1.6;">
        
        <!-- Main Container -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6; padding:40px 20px;">
            <tr>
                <td align="center">
                    
                    <!-- Email Card -->
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:white; border-radius:8px; box-shadow:0 4px 6px rgba(0,0,0,0.1); overflow:hidden;">
                        
                        <!-- LienDeadline Branding Header -->
                        <tr>
                            <td style="background-color:#1e3a8a; padding:35px 30px; text-align:center;">
                                <h1 style="margin:0; color:white; font-size:28px; font-weight:700; letter-spacing:-0.5px;">
                                    📋 LienDeadline
                                </h1>
                                <p style="margin:10px 0 0 0; color:#e0e7ff; font-size:16px; font-weight:500;">
                                    Welcome! Your account is ready 🎉
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Welcome Message -->
                        <tr>
                            <td style="padding:40px 30px;">
                                <h2 style="margin:0 0 20px 0; font-size:24px; font-weight:600; color:#1f2937; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; letter-spacing:-0.3px;">
                                    Welcome to LienDeadline!
                                </h2>
                                <p style="margin:0 0 28px 0; font-size:16px; color:#4b5563; line-height:1.7; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                    Thank you for joining LienDeadline. Your account is now active and ready to help you protect your receivables with automated lien deadline tracking.
                                </p>
                                
                                <!-- Login Credentials Box -->
                                <div style="background-color:#f9fafb; border:2px solid #e5e7eb; border-radius:8px; padding:24px; margin-bottom:30px;">
                                    <h3 style="margin:0 0 18px 0; font-size:18px; font-weight:600; color:#1e3a8a; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        Your Login Credentials
                                    </h3>
                                    <table width="100%" cellpadding="10" cellspacing="0" style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; width:120px; font-size:14px; padding:10px 0; vertical-align:top;">Email:</td>
                                            <td style="color:#111827; font-size:14px; padding:10px 0;">{email}</td>
                                        </tr>
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; font-size:14px; padding:10px 0; vertical-align:top;">Password:</td>
                                            <td style="color:#111827; font-size:16px; font-family:'Courier New', 'Monaco', monospace; font-weight:700; letter-spacing:1px; padding:10px 0;">{temp_password}</td>
                                        </tr>
                                    </table>
                                    <p style="margin:24px 0 0 0; text-align:center;">
                                        <a href="https://liendeadline.com/login.html" 
                                           style="display:inline-block; background-color:#1e3a8a; color:#ffffff; text-decoration:none; padding:18px 36px; border-radius:8px; font-weight:700; font-size:16px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; box-shadow:0 4px 12px rgba(30,58,138,0.3); letter-spacing:0.3px;">
                                            Login to Dashboard →
                                        </a>
                                    </p>
                                </div>
                                
                                <!-- Next Steps Section -->
                                <div style="margin-bottom:30px;">
                                    <h3 style="margin:0 0 20px 0; font-size:20px; font-weight:600; color:#1f2937; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; letter-spacing:-0.2px;">
                                        What's Next?
                                    </h3>
                                    <div style="background-color:#eff6ff; border-left:4px solid #2563eb; border-radius:4px; padding:20px; margin-bottom:20px;">
                                        <h4 style="margin:0 0 14px 0; font-size:16px; font-weight:600; color:#1e40af; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                            1. Connect QuickBooks (Recommended)
                                        </h4>
                                        <p style="margin:0; font-size:14px; color:#1e40af; line-height:1.7; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                            Automatically import invoices and track deadlines. Connect in your dashboard under "Integrations".
                                        </p>
                                    </div>
                                    <ul style="margin:0; padding-left:24px; color:#4b5563; font-size:15px; line-height:1.8; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        <li style="margin-bottom:14px; padding-left:4px;">Change your password in Account Settings for security</li>
                                        <li style="margin-bottom:14px; padding-left:4px;">Create your first project and set up deadline reminders</li>
                                        <li style="margin-bottom:14px; padding-left:4px;">Run <strong style="color:#1f2937; font-weight:600;">unlimited</strong> lien deadline calculations</li>
                                        <li style="margin-bottom:14px; padding-left:4px;">Download PDF reports for your records</li>
                                    </ul>
                                </div>
                                
                                <!-- Pro Tip -->
                                <div style="background-color:#fef3c7; border-left:4px solid #f59e0b; border-radius:4px; padding:16px; margin-bottom:30px;">
                                    <p style="margin:0; color:#92400e; font-size:14px; line-height:1.7; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        <strong style="font-weight:600;">💡 Pro Tip:</strong> Bookmark your dashboard for instant access. Set up email reminders to never miss a deadline.
                                    </p>
                                </div>
                                
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color:#f9fafb; padding:25px 30px; border-top:1px solid #e5e7eb;">
                                <p style="margin:0 0 12px 0; font-size:14px; color:#4b5563; text-align:center; line-height:1.6;">
                                    <strong>Need Help?</strong> We're here for you!<br>
                                    Email: <a href="mailto:support@liendeadline.com" style="color:#1e3a8a; text-decoration:none; font-weight:600;">support@liendeadline.com</a><br>
                                    Or simply reply to this email.
                                </p>
                                <p style="margin:0; font-size:12px; color:#9ca3af; text-align:center;">
                                    © {datetime.now().year} LienDeadline. All rights reserved.<br>
                                    <a href="https://liendeadline.com" style="color:#6b7280; text-decoration:none;">liendeadline.com</a>
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
    
    return send_email_sync(email, "Welcome to LienDeadline - Your Account is Ready", html)

def send_broker_notification(broker_email: str, customer_email: str):
    """Notify broker of new referral"""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color:#f3f4f6; line-height:1.6;">
        
        <!-- Main Container -->
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f3f4f6; padding:40px 20px;">
            <tr>
                <td align="center">
                    
                    <!-- Email Card -->
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color:white; border-radius:8px; box-shadow:0 4px 6px rgba(0,0,0,0.1); overflow:hidden;">
                        
                        <!-- Success Header -->
                        <tr>
                            <td style="background-color:#059669; padding:35px 30px; text-align:center;">
                                <h1 style="margin:0; color:white; font-size:28px; font-weight:700; letter-spacing:-0.5px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                    💰 New Referral! 🎉
                                </h1>
                                <p style="margin:10px 0 0 0; color:#d1fae5; font-size:16px; font-weight:500;">
                                    You just earned a commission
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Congratulations Message -->
                        <tr>
                            <td style="padding:40px 30px;">
                                <h2 style="margin:0 0 20px 0; font-size:24px; font-weight:600; color:#1f2937; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; letter-spacing:-0.3px;">
                                    Congratulations!
                                </h2>
                                <p style="margin:0 0 28px 0; font-size:16px; color:#4b5563; line-height:1.7;">
                                    Your referral just signed up for LienDeadline Pro.
                                </p>
                                
                                <!-- Referral Details Box -->
                                <div style="background-color:#f9fafb; border:2px solid #e5e7eb; border-radius:8px; padding:24px; margin-bottom:30px;">
                                    <h3 style="margin:0 0 18px 0; font-size:18px; font-weight:600; color:#1e3a8a; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        Referral Details
                                    </h3>
                                    <table width="100%" cellpadding="10" cellspacing="0" style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; width:160px; font-size:14px; padding:10px 0; vertical-align:top;">Customer Email:</td>
                                            <td style="color:#111827; font-size:14px; padding:10px 0;">{customer_email}</td>
                                        </tr>
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; font-size:14px; padding:10px 0; vertical-align:top;">Plan:</td>
                                            <td style="color:#111827; font-size:14px; padding:10px 0;">Professional ($299/month)</td>
                                        </tr>
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; font-size:14px; padding:10px 0; vertical-align:top;">Commission Status:</td>
                                            <td style="color:#f59e0b; font-weight:700; font-size:14px; padding:10px 0;">Pending (30-day holding period)</td>
                                        </tr>
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; font-size:14px; padding:10px 0; vertical-align:top;">Commission Amount:</td>
                                            <td style="color:#059669; font-size:20px; font-weight:700; padding:10px 0; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">$500 <span style="color:#6b7280; font-size:14px; font-weight:500;">(one-time bounty)</span></td>
                                        </tr>
                                    </table>
                                </div>
                                
                                <!-- Payment Timeline Box -->
                                <div style="background-color:#fef3c7; border-left:4px solid #f59e0b; border-radius:4px; padding:20px; margin-bottom:30px;">
                                    <p style="margin:0; color:#92400e; font-size:14px; line-height:1.7; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
                                        <strong style="font-weight:600;">⏰ Payment Timeline:</strong> Commission held for 30 days after customer payment to prevent fraud, then paid monthly. You'll receive an email when payment is processed.
                                    </p>
                                </div>
                                
                                <!-- CTA Button -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                                    <tr>
                                        <td align="center" style="padding:12px 0;">
                                            <a href="https://liendeadline.tolt.io/login" 
                                               style="display:inline-block; background-color:#059669; color:#ffffff; text-decoration:none; padding:18px 36px; border-radius:8px; font-weight:700; font-size:16px; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; box-shadow:0 4px 12px rgba(5,150,105,0.3); letter-spacing:0.3px;">
                                                View Your Dashboard →
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color:#f9fafb; padding:25px 30px; border-top:1px solid #e5e7eb;">
                                <p style="margin:0 0 12px 0; font-size:14px; color:#4b5563; text-align:center; line-height:1.6;">
                                    Questions? Reply to this email or contact 
                                    <a href="mailto:partners@liendeadline.com" style="color:#1e3a8a; text-decoration:none; font-weight:600;">partners@liendeadline.com</a>
                                </p>
                                <p style="margin:0; font-size:12px; color:#9ca3af; text-align:center;">
                                    © {datetime.now().year} LienDeadline. All rights reserved.
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
    
    return send_email_sync(broker_email, "💰 New Referral - $500 Commission Earned!", html)

def send_admin_fraud_alert(broker_email: str, customer_email: str, flags: list, risk_score: int):
    """Send admin alert for flagged referrals"""
    # Currently just logs to console, but could be enhanced to email admin
    print(f"""
    🚨 FRAUD ALERT 🚨
    Broker: {broker_email}
    Customer: {customer_email}
    Risk Score: {risk_score}
    Flags: {', '.join(flags)}
    
    Review at: https://liendeadline.com/admin-dashboard
    """)
    # TODO: Send email/Slack notification in production

def send_password_reset_email(email: str, reset_link: str):
    """Send password reset email"""
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #1e293b; color: white; padding: 20px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0;">Password Reset Request</h1>
        </div>
        
        <div style="padding: 30px 0;">
            <p>You requested a password reset for your LienDeadline account.</p>
            
            <p>Click the button below to reset your password:</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" style="display: inline-block; background: #c1554e; color: white; padding: 15px 30px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                    Reset Password
                </a>
            </div>
            
            <p style="color: #64748b; font-size: 14px;">
                This link expires in 24 hours. If you didn't request this, ignore this email.
            </p>
            
            <p style="color: #64748b; font-size: 14px;">
                Or copy and paste this link:<br>
                {reset_link}
            </p>
        </div>
    </body>
    </html>
    """
    
    return send_email_sync(email, "Reset Your LienDeadline Password", html_content)

def send_broker_password_reset_email(email: str, name: str, reset_link: str):
    """Send password reset email to broker"""
    subject = "Reset Your LienDeadline Partner Password"
    
    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f9fafb;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                    <tr>
                        <td style="padding: 40px 40px 30px; text-align: center; border-bottom: 1px solid #e5e7eb;">
                            <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #1f2937;">
                                📋 LienDeadline
                            </h1>
                            <p style="margin: 12px 0 0; font-size: 16px; color: #6b7280;">
                                Partner Program
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 40px 20px;">
                            <h2 style="margin: 0 0 16px; font-size: 24px; font-weight: 600; color: #1f2937;">
                                Password Reset Request
                            </h2>
                            <p style="margin: 0 0 24px; font-size: 16px; color: #4b5563; line-height: 1.6;">
                                Hi {name},
                            </p>
                            <p style="margin: 0 0 24px; font-size: 16px; color: #4b5563; line-height: 1.6;">
                                You requested a password reset for your LienDeadline Partner account. Click the button below to reset your password:
                            </p>
                            <div style="text-align: center; margin: 30px 0;">
                                <a href="{reset_link}" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; padding: 14px 32px; border-radius: 6px;">
                                    Reset Password
                                </a>
                            </div>
                            <p style="margin: 24px 0 0; font-size: 14px; color: #6b7280;">
                                This link will expire in 24 hours. If you didn't request this, please ignore this email.
                            </p>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 32px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                                © 2025 LienDeadline. All rights reserved.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
    
    return send_email_sync(email, subject, body_html)

def send_welcome_email_background(email: str, referral_link: str, name: str = "", referral_code: str = "", commission_model: str = "bounty", temp_password: str = ""):
    """Background email function for partner approval"""
    # Use professional link format if referral_link is provided, otherwise fallback to via format
    if not referral_link:
        referral_link = f"https://liendeadline.com/?via={referral_code}"
        
    dashboard_url = "https://partners.liendeadline.com/login"
    
    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Welcome to LienDeadline Partner Program</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #1f2937;">
    <!-- Email wrapper -->
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="width: 100%; max-width: 650px; background-color: #f9fafb;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Main content container -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="650" style="width: 100%; max-width: 650px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                    
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 30px; text-align: center; border-bottom: 1px solid #e5e7eb;">
                            <h1 style="margin: 0; font-size: 28px; font-weight: 700; color: #1f2937; letter-spacing: -0.5px;">
                                📋 LienDeadline
                            </h1>
                            <p style="margin: 12px 0 0; font-size: 16px; color: #6b7280; font-weight: 500;">
                                Partner Program
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Welcome message -->
                    <tr>
                        <td style="padding: 40px 40px 20px;">
                            <h2 style="margin: 0 0 16px; font-size: 24px; font-weight: 600; color: #1f2937; line-height: 1.3;">
                                Welcome, {name}!
                            </h2>
                            <p style="margin: 0 0 24px; font-size: 16px; color: #4b5563; line-height: 1.6;">
                                Congratulations! Your application to join the LienDeadline Partner Program has been approved. You're now ready to start earning commissions.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Referral link box -->
                    <tr>
                        <td style="padding: 0 40px 30px;">
                            <div style="background-color: #f3f4f6; border: 2px solid #e5e7eb; border-radius: 8px; padding: 24px; text-align: center;">
                                <p style="margin: 0 0 12px; font-size: 13px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">
                                    Your Referral Link
                                </p>
                                <p style="margin: 0; font-size: 18px; font-weight: 600; color: #2563eb; word-break: break-all; font-family: 'Courier New', monospace;">
                                    <a href="{referral_link}" style="color: #2563eb; text-decoration: none;">{referral_link}</a>
                                </p>
                                <p style="margin: 16px 0 0; font-size: 13px; color: #6b7280;">
                                    Share this link to start earning commissions
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Commission info -->
                    <tr>
                        <td style="padding: 0 40px 30px;">
                            <div style="background-color: #eff6ff; border-left: 4px solid #2563eb; border-radius: 4px; padding: 20px;">
                                <h3 style="margin: 0 0 12px; font-size: 16px; font-weight: 600; color: #1e40af;">
                                    Your Commission Structure
                                </h3>
                                <p style="margin: 0 0 12px; font-size: 15px; color: #1f2937; line-height: 1.6;">
                                    Your account is approved under one of the following commission models:
                                </p>
                                <p style="margin: 0 0 12px; font-size: 15px; color: #1f2937; line-height: 1.6;">
                                    <strong>30% Monthly Recurring Commission</strong>
                                </p>
                                <ul style="margin: 0 0 12px; padding-left: 20px; color: #1f2937; font-size: 15px; line-height: 1.8;">
                                    <li style="margin-bottom: 8px;">Earn 30% of every $299/month subscription ($89.70 per client per month)</li>
                                    <li style="margin-bottom: 8px;">Commission held for 30 days after customer payment to prevent fraud, then paid monthly</li>
                                    <li style="margin-bottom: 0;">Build long-term passive income as long as clients stay active</li>
                                </ul>
                                <p style="margin: 0; font-size: 13px; color: #6b7280; font-style: italic;">
                                    Track all referrals and earnings in your partner dashboard.
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- How it works -->
                    <tr>
                        <td style="padding: 0 40px 30px;">
                            <h3 style="margin: 0 0 16px; font-size: 18px; font-weight: 600; color: #1f2937;">
                                How it works
                            </h3>
                            <ol style="margin: 0; padding-left: 20px; color: #4b5563; font-size: 15px;">
                                <li style="margin-bottom: 12px; line-height: 1.6;">
                                    Share your referral link with construction companies and contractors
                                </li>
                                <li style="margin-bottom: 12px; line-height: 1.6;">
                                    When they sign up and make their first payment, you earn commission
                                </li>
                                <li style="margin-bottom: 0; line-height: 1.6;">
                                    Track all referrals and earnings in your partner dashboard
                                </li>
                            </ol>
                        </td>
                    </tr>
                    
                    <!-- CTA Button -->
                    <tr>
                        <td style="padding: 0 40px 40px; text-align: center;">
                            <a href="{dashboard_url}" style="display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; font-weight: 600; font-size: 16px; padding: 14px 32px; border-radius: 6px; box-shadow: 0 1px 3px rgba(37, 99, 235, 0.3);">
                                Access Partner Dashboard
                            </a>
                            <p style="margin: 16px 0 0; font-size: 14px; color: #6b7280;">
                                Login with: <strong style="color: #1f2937;">{email}</strong>
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="padding: 32px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0 0 12px; font-size: 14px; color: #4b5563; line-height: 1.6;">
                                Questions? Reply to this email or contact us at <a href="mailto:partners@liendeadline.com" style="color: #2563eb; text-decoration: none;">partners@liendeadline.com</a>
                            </p>
                            <p style="margin: 0; font-size: 12px; color: #9ca3af;">
                                © 2025 LienDeadline. All rights reserved.<br>
                                <a href="https://liendeadline.com" style="color: #6b7280; text-decoration: none;">liendeadline.com</a>
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

    return send_email_sync(email, "Welcome to LienDeadline Partner Program! 🎉", body_html)
