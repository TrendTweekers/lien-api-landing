"""
Short Link System for LienDeadline Broker Referrals
Converts obvious referral codes (MATS-A63763) to short codes (mA63)
"""

import random
import string
import hashlib
from datetime import datetime, timedelta

class ShortLinkGenerator:
    """Generates short, non-obvious referral codes"""
    
    # Characters for short codes (avoids confusing characters like 0/O, 1/l/I)
    CHARSET = string.ascii_letters + string.digits
    SAFE_CHARSET = ''.join(c for c in CHARSET if c not in '0Ol1I')
    
    @staticmethod
    def generate_short_code(broker_email: str, length: int = 4) -> str:
        """
        Generate a short, unique code from broker email
        
        Args:
            broker_email: Broker's email address
            length: Length of short code (default 4)
            
        Returns:
            Short code like 'mA63' or 'xK9p'
        """
        # Create hash from email + timestamp for uniqueness
        unique_string = f"{broker_email}{datetime.now().isoformat()}"
        hash_object = hashlib.sha256(unique_string.encode())
        hash_hex = hash_object.hexdigest()
        
        # Convert hash to base62-like encoding
        short_code = ""
        for i in range(length):
            # Take portions of hash and map to charset
            index = int(hash_hex[i*2:i*2+2], 16) % len(ShortLinkGenerator.SAFE_CHARSET)
            short_code += ShortLinkGenerator.SAFE_CHARSET[index]
        
        return short_code
    
    @staticmethod
    def generate_random_code(length: int = 4) -> str:
        """Generate a completely random short code"""
        return ''.join(random.choices(ShortLinkGenerator.SAFE_CHARSET, k=length))
    
    @staticmethod
    def is_valid_code(code: str) -> bool:
        """Check if a code is valid format"""
        if not code:
            return False
        if len(code) < 3 or len(code) > 8:
            return False
        return all(c in ShortLinkGenerator.CHARSET for c in code)


# SQL Migration Scripts
SQL_ADD_SHORT_CODE = """
-- Add short_code column to brokers table
ALTER TABLE brokers ADD COLUMN IF NOT EXISTS short_code VARCHAR(10) UNIQUE;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_brokers_short_code ON brokers(short_code);

-- Update existing brokers with short codes (run once)
-- UPDATE brokers SET short_code = SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 4) WHERE short_code IS NULL;
"""

SQL_REFERRAL_CLICKS_TABLE = """
-- Track referral link clicks for analytics
CREATE TABLE IF NOT EXISTS referral_clicks (
    id SERIAL PRIMARY KEY,
    short_code VARCHAR(10) NOT NULL,
    broker_id INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    referrer_url TEXT,
    clicked_at TIMESTAMP DEFAULT NOW(),
    converted BOOLEAN DEFAULT FALSE,
    conversion_date TIMESTAMP,
    FOREIGN KEY (broker_id) REFERENCES brokers(id)
);

CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON referral_clicks(short_code);
CREATE INDEX IF NOT EXISTS idx_clicks_broker ON referral_clicks(broker_id);
"""


# FastAPI Route Handler
FASTAPI_ROUTE_CODE = '''
from fastapi import Request, Response, HTTPException
from fastapi.responses import RedirectResponse
import logging

logger = logging.getLogger(__name__)

@app.get("/r/{short_code}")
async def referral_redirect(short_code: str, request: Request, response: Response):
    """
    Handle short referral links like /r/mA63
    1. Look up broker by short code
    2. Track the click
    3. Set referral cookie
    4. Redirect to main page
    """
    
    # Validate code format
    if not ShortLinkGenerator.is_valid_code(short_code):
        logger.warning(f"Invalid short code format: {short_code}")
        raise HTTPException(status_code=404, detail="Invalid referral link")
    
    # Look up broker
    cursor = get_cursor()
    cursor.execute("""
        SELECT id, name, email, referral_code 
        FROM brokers 
        WHERE short_code = ? AND status = 'approved'
    """, (short_code,))
    
    broker = cursor.fetchone()
    
    if not broker:
        logger.warning(f"Short code not found or broker not approved: {short_code}")
        raise HTTPException(status_code=404, detail="Referral link not found")
    
    broker_id, broker_name, broker_email, referral_code = broker
    
    # Track the click for analytics
    try:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        referrer = request.headers.get("referer", "")
        
        cursor.execute("""
            INSERT INTO referral_clicks 
            (short_code, broker_id, ip_address, user_agent, referrer_url)
            VALUES (?, ?, ?, ?, ?)
        """, (short_code, broker_id, client_ip, user_agent, referrer))
        
        conn.commit()
        logger.info(f"Tracked click for broker {broker_email} via {short_code}")
    except Exception as e:
        logger.error(f"Failed to track click: {e}")
        # Don't fail the redirect if tracking fails
    
    # Set referral tracking cookie (lasts 30 days)
    redirect_response = RedirectResponse(url="/", status_code=302)
    
    # Set multiple cookies for redundancy
    redirect_response.set_cookie(
        key="ref_code",
        value=referral_code,
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
        samesite="lax"
    )
    
    redirect_response.set_cookie(
        key="ref_short",
        value=short_code,
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        samesite="lax"
    )
    
    redirect_response.set_cookie(
        key="ref_broker",
        value=str(broker_id),
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        samesite="lax"
    )
    
    logger.info(f"Redirecting referral from {short_code} for broker {broker_email}")
    
    return redirect_response
'''


# Update Broker Creation Function
BROKER_CREATION_UPDATE = '''
# In api/admin.py, update the approve_partner function:

from short_link_system import ShortLinkGenerator

# After creating the broker in database, generate short code:

# Generate short code
short_code = ShortLinkGenerator.generate_short_code(broker_email)

# Check if code already exists (collision unlikely but handle it)
cursor.execute("SELECT short_code FROM brokers WHERE short_code = ?", (short_code,))
if cursor.fetchone():
    # Generate random code if collision
    short_code = ShortLinkGenerator.generate_random_code(6)

# Update broker with short code
cursor.execute("""
    UPDATE brokers 
    SET short_code = ?, referral_link = ?
    WHERE email = ?
""", (short_code, f"https://liendeadline.com/r/{short_code}", broker_email))

conn.commit()

# Update email to use short link instead of ?ref=
referral_link = f"https://liendeadline.com/r/{short_code}"
'''


# Updated Welcome Email Template
EMAIL_TEMPLATE_UPDATE = '''
def send_broker_welcome_email(broker_email: str, broker_name: str, 
                               short_code: str, commission_model: str):
    """Send welcome email with short referral link"""
    
    # Determine commission details
    if commission_model == "bounty":
        commission_text = "$500 one-time payment per signup"
        commission_amount = "$500"
    else:
        commission_text = "$50/month recurring per active customer"
        commission_amount = "$50/month"
    
    # Short, clean referral link
    referral_link = f"https://liendeadline.com/r/{short_code}"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h1 style="color: #2563eb;">Welcome to LienDeadline Partner Program! 🎉</h1>
        
        <p>Hi {broker_name},</p>
        
        <p>Congratulations! Your application has been approved!</p>
        
        <h2 style="color: #1e40af;">Your Referral Link</h2>
        
        <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0; font-size: 18px; font-weight: bold;">
                <a href="{referral_link}" style="color: #2563eb; text-decoration: none;">
                    {referral_link}
                </a>
            </p>
        </div>
        
        <h2 style="color: #1e40af;">Commission: {commission_amount}</h2>
        <p>{commission_text}</p>
        
        <h3>How it works:</h3>
        <ol>
            <li>Share your referral link with construction companies and contractors</li>
            <li>When they sign up and make their first payment, you earn commission</li>
            <li>Track your referrals and earnings in your partner dashboard</li>
        </ol>
        
        <div style="margin: 30px 0;">
            <a href="https://liendeadline.com/broker-dashboard" 
               style="background: #2563eb; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 6px; display: inline-block;">
                Access Partner Dashboard
            </a>
        </div>
        
        <p>Start earning today by sharing your link!</p>
        
        <p>Best regards,<br>The LienDeadline Team</p>
    </div>
    """
    
    # Send via Resend
    params = {
        "from": os.getenv("SMTP_FROM_EMAIL", "noreply@liendeadline.com"),
        "to": [broker_email],
        "subject": "Welcome to LienDeadline Partner Program! 🎉",
        "html": html_content
    }
    
    response = resend.Emails.send(params)
    return response
'''


if __name__ == "__main__":
    # Test the generator
    print("Testing Short Link Generator")
    print("=" * 50)
    
    # Test with sample emails
    test_emails = [
        "mats@insurance.com",
        "john@brokerage.com",
        "jane@consulting.com"
    ]
    
    for email in test_emails:
        short_code = ShortLinkGenerator.generate_short_code(email)
        print(f"Email: {email}")
        print(f"Short Code: {short_code}")
        print(f"Link: https://liendeadline.com/r/{short_code}")
        print()
    
    print("\nRandom codes:")
    for i in range(5):
        print(f"  {ShortLinkGenerator.generate_random_code()}")
