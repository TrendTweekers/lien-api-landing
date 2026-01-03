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
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0;">Welcome to LienDeadline Partner Program! 🎉</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">Start earning commissions today</p>
        </div>
        
        <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h2 style="color: #1e293b; margin-top: 0;">Congratulations, {name}!</h2>
            <p style="color: #475569; line-height: 1.8;">Your partner account is now active. Share your referral link with construction clients and start earning commissions.</p>
        </div>
        
        <div style="background: white; border: 2px solid #e2e8f0; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #1e293b; margin-top: 0;">Your Referral Details</h3>
            <p style="margin: 10px 0;"><strong>Referral Code:</strong> <code style="background: #f1f5f9; padding: 5px 10px; border-radius: 4px; font-size: 16px;">{code}</code></p>
            <p style="margin: 10px 0;"><strong>Referral Link:</strong></p>
            <p style="margin: 10px 0;">
                <a href="{link}" style="color: #2563eb; word-break: break-all;">{link}</a>
            </p>
        </div>
        
        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px; margin: 20px 0;">
            <h3 style="color: #92400e; margin-top: 0;">💰 Commission Structure</h3>
            <ul style="color: #92400e; line-height: 1.8; margin: 0;">
                <li><strong>$500 one-time</strong> per signup (bounty model)</li>
                <li><strong>$50/month recurring</strong> per active subscriber (recurring model)</li>
                <li>Commission held for 60 days after customer payment to prevent fraud, then paid monthly</li>
            </ul>
        </div>
        
        <div style="margin: 30px 0;">
            <h3 style="color: #1e293b;">How It Works</h3>
            <ol style="color: #475569; line-height: 1.8;">
                <li>Share your referral link with construction clients</li>
                <li>When they sign up for LienDeadline Pro ($299/month), you earn a commission</li>
                <li>Track all referrals in your dashboard</li>
                <li>Get paid monthly via PayPal or bank transfer</li>
            </ol>
        </div>
        
        <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e2e8f0; margin-top: 30px;">
            <a href="https://liendeadline.com/broker-dashboard" style="display: inline-block; background: #c1554e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-bottom: 15px;">
                View Your Dashboard →
            </a>
            <p style="color: #64748b; font-size: 14px; margin: 0;">
                Questions? Reply to this email or contact partners@liendeadline.com
            </p>
        </div>
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
    <body style="margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color:#f3f4f6;">
        
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
                                <h2 style="margin:0 0 16px 0; font-size:24px; font-weight:600; color:#1f2937;">
                                    Welcome to LienDeadline!
                                </h2>
                                <p style="margin:0 0 24px 0; font-size:16px; color:#4b5563; line-height:1.6;">
                                    Thank you for joining LienDeadline. Your account is now active and ready to help you protect your receivables with automated lien deadline tracking.
                                </p>
                                
                                <!-- Login Credentials Box -->
                                <div style="background-color:#f9fafb; border:2px solid #e5e7eb; border-radius:8px; padding:24px; margin-bottom:30px;">
                                    <h3 style="margin:0 0 16px 0; font-size:18px; font-weight:600; color:#1e3a8a;">
                                        Your Login Credentials
                                    </h3>
                                    <table width="100%" cellpadding="8" cellspacing="0">
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; width:120px; font-size:14px;">Email:</td>
                                            <td style="color:#111827; font-size:14px;">{email}</td>
                                        </tr>
                                        <tr>
                                            <td style="color:#6b7280; font-weight:600; font-size:14px;">Password:</td>
                                            <td style="color:#111827; font-size:16px; font-family:'Courier New',monospace; font-weight:700; letter-spacing:1px;">{temp_password}</td>
                                        </tr>
                                    </table>
                                    <p style="margin:20px 0 0 0; text-align:center;">
                                        <a href="https://liendeadline.com/login.html" 
                                           style="display:inline-block; background-color:#1e3a8a; color:white; text-decoration:none; padding:14px 32px; border-radius:8px; font-weight:700; font-size:16px; box-shadow:0 4px 6px rgba(30,58,138,0.3);">
                                            Login to Dashboard →
                                        </a>
                                    </p>
                                </div>
                                
                                <!-- Next Steps Section -->
                                <div style="margin-bottom:30px;">
                                    <h3 style="margin:0 0 16px 0; font-size:20px; font-weight:600; color:#1f2937;">
                                        What's Next?
                                    </h3>
                                    <div style="background-color:#eff6ff; border-left:4px solid #2563eb; border-radius:4px; padding:20px; margin-bottom:20px;">
                                        <h4 style="margin:0 0 12px 0; font-size:16px; font-weight:600; color:#1e40af;">
                                            1. Connect QuickBooks (Recommended)
                                        </h4>
                                        <p style="margin:0; font-size:14px; color:#1e40af; line-height:1.6;">
                                            Automatically import invoices and track deadlines. Connect in your dashboard under "Integrations".
                                        </p>
                                    </div>
                                    <ul style="margin:0; padding-left:20px; color:#4b5563; font-size:15px; line-height:1.8;">
                                        <li style="margin-bottom:12px;">Change your password in Account Settings for security</li>
                                        <li style="margin-bottom:12px;">Create your first project and set up deadline reminders</li>
                                        <li style="margin-bottom:12px;">Run <strong>unlimited</strong> lien deadline calculations</li>
                                        <li style="margin-bottom:12px;">Download PDF reports for your records</li>
                                    </ul>
                                </div>
                                
                                <!-- Pro Tip -->
                                <div style="background-color:#fef3c7; border-left:4px solid #f59e0b; border-radius:4px; padding:16px; margin-bottom:30px;">
                                    <p style="margin:0; color:#92400e; font-size:14px; line-height:1.6;">
                                        <strong>💡 Pro Tip:</strong> Bookmark your dashboard for instant access. Set up email reminders to never miss a deadline.
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
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #059669 0%, #047857 100%); color: white; padding: 30px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0;">💰 New Referral! 🎉</h1>
            <p style="margin: 10px 0 0 0; opacity: 0.9;">You just earned a commission</p>
        </div>
        
        <div style="background: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h2 style="color: #1e293b; margin-top: 0;">Congratulations!</h2>
            <p style="color: #475569; line-height: 1.8;">Your referral just signed up for LienDeadline Pro.</p>
        </div>
        
        <div style="background: white; border: 2px solid #e2e8f0; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: #1e293b; margin-top: 0;">Referral Details</h3>
            <p style="margin: 10px 0;"><strong>Customer Email:</strong> {customer_email}</p>
            <p style="margin: 10px 0;"><strong>Plan:</strong> Professional ($299/month)</p>
            <p style="margin: 10px 0;"><strong>Commission Status:</strong> <span style="color: #f59e0b; font-weight: bold;">Pending (60-day holding period)</span></p>
            <p style="margin: 10px 0;"><strong>Commission Amount:</strong> <span style="color: #059669; font-size: 20px; font-weight: bold;">$500</span> (one-time bounty)</p>
        </div>
        
        <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; border-radius: 4px; margin: 20px 0;">
            <p style="margin: 0; color: #92400e;">
                <strong>⏰ Payment Timeline:</strong> Commission held for 60 days after customer payment to prevent fraud, then paid monthly. You'll receive an email when payment is processed.
            </p>
        </div>
        
        <div style="text-align: center; padding: 20px 0; border-top: 1px solid #e2e8f0; margin-top: 30px;">
            <a href="https://liendeadline.com/broker-dashboard" style="display: inline-block; background: #c1554e; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-bottom: 15px;">
                View All Referrals →
            </a>
            <p style="color: #64748b; font-size: 14px; margin: 0;">
                Keep sharing your referral link to earn more commissions!
            </p>
        </div>
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
    # Use short link format if referral_link is provided, otherwise fallback to old format
    if not referral_link:
        referral_link = f"https://liendeadline.com/?ref={referral_code}"
        
    dashboard_url = "https://liendeadline.com/broker-dashboard"
    
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
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f9fafb;">
        <tr>
            <td align="center" style="padding: 40px 20px;">
                <!-- Main content container -->
                <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);">
                    
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
                                <ul style="margin: 0 0 12px; padding-left: 20px; color: #1f2937; font-size: 15px; line-height: 1.8;">
                                    <li style="margin-bottom: 8px;"><strong>$500 one-time bounty</strong> per referred customer, OR</li>
                                    <li style="margin-bottom: 8px;"><strong>$50 per month</strong> for each active paying customer you refer</li>
                                </ul>
                                <p style="margin: 0 0 8px; font-size: 14px; color: #4b5563; line-height: 1.5;">
                                    Your specific commission model is visible in your broker dashboard.
                                </p>
                                <p style="margin: 0; font-size: 13px; color: #6b7280; font-style: italic;">
                                    Commission held for 60 days after customer payment to prevent fraud, then paid monthly.
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
                            {f'''
                            <div style="margin-top: 24px; padding: 20px; background-color: #fef3c7; border: 2px solid #f59e0b; border-radius: 8px;">
                                <p style="margin: 0 0 12px; font-size: 14px; font-weight: 600; color: #92400e;">
                                    🔐 Your Temporary Password
                                </p>
                                <p style="margin: 0; font-size: 18px; font-weight: 700; color: #1f2937; font-family: 'Courier New', monospace; letter-spacing: 2px;">
                                    {temp_password}
                                </p>
                                <p style="margin: 12px 0 0; font-size: 13px; color: #92400e;">
                                    Please change this password after your first login for security.
                                </p>
                            </div>
                            ''' if temp_password else ''}
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
