# SHORT LINK IMPLEMENTATION GUIDE
# Converting from ?ref=MATS-A63763 to /r/mA63

## 📋 OVERVIEW
Convert obvious referral codes to short, clean links:
- OLD: https://liendeadline.com?ref=MATS-A63763
- NEW: https://liendeadline.com/r/mA63

## 🎯 BENEFITS
- Not obviously a referral link
- Shorter and cleaner
- Easier to share verbally
- More professional
- Better click-through rates

## 📦 STEP 1: DATABASE MIGRATION

### Add short_code column to brokers table

```sql
-- Run this in Railway PostgreSQL console or via migration script

-- Add column
ALTER TABLE brokers ADD COLUMN IF NOT EXISTS short_code VARCHAR(10) UNIQUE;

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_brokers_short_code ON brokers(short_code);

-- Create clicks tracking table (optional but recommended)
CREATE TABLE IF NOT EXISTS referral_clicks (
    id SERIAL PRIMARY KEY,
    short_code VARCHAR(10) NOT NULL,
    broker_id INTEGER,
    ip_address VARCHAR(45),
    user_agent TEXT,
    referrer_url TEXT,
    clicked_at TIMESTAMP DEFAULT NOW(),
    converted BOOLEAN DEFAULT FALSE,
    conversion_date TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON referral_clicks(short_code);
CREATE INDEX IF NOT EXISTS idx_clicks_broker ON referral_clicks(broker_id);
```

### Generate short codes for existing brokers

```sql
-- Option A: Simple random codes (quick)
UPDATE brokers 
SET short_code = SUBSTRING(MD5(RANDOM()::text) FROM 1 FOR 4)
WHERE short_code IS NULL;

-- Option B: Based on email hash (reproducible)
UPDATE brokers
SET short_code = SUBSTRING(MD5(email) FROM 1 FOR 4)
WHERE short_code IS NULL;
```

## 📝 STEP 2: UPDATE api/main.py

### Add short link generator function

```python
import hashlib
import random
import string

def generate_short_code(email: str, length: int = 4) -> str:
    """Generate short referral code from email"""
    # Characters excluding confusing ones (0/O, 1/l/I)
    charset = ''.join(c for c in (string.ascii_letters + string.digits) 
                     if c not in '0Ol1I')
    
    # Hash email for consistency
    hash_obj = hashlib.sha256(email.encode())
    hash_hex = hash_obj.hexdigest()
    
    # Convert to short code
    short_code = ""
    for i in range(length):
        index = int(hash_hex[i*2:i*2+2], 16) % len(charset)
        short_code += charset[index]
    
    return short_code


def ensure_unique_short_code(email: str, cursor) -> str:
    """Generate and verify unique short code"""
    short_code = generate_short_code(email, 4)
    
    # Check if exists
    cursor.execute("SELECT short_code FROM brokers WHERE short_code = ?", (short_code,))
    
    if cursor.fetchone():
        # Collision - make it longer
        short_code = generate_short_code(email, 6)
    
    return short_code
```

### Add referral redirect route

```python
from fastapi import Request, Response
from fastapi.responses import RedirectResponse

@app.get("/r/{short_code}")
async def referral_redirect(short_code: str, request: Request):
    """Handle short referral links"""
    
    # Validate format
    if not short_code or len(short_code) < 3 or len(short_code) > 8:
        raise HTTPException(status_code=404, detail="Invalid link")
    
    # Look up broker
    cursor = get_cursor()
    cursor.execute("""
        SELECT id, email, referral_code, name
        FROM brokers 
        WHERE short_code = ? AND status = 'approved'
    """, (short_code,))
    
    broker = cursor.fetchone()
    
    if not broker:
        logger.warning(f"Short code not found: {short_code}")
        raise HTTPException(status_code=404, detail="Link not found")
    
    broker_id, broker_email, referral_code, broker_name = broker
    
    # Track the click (optional but recommended)
    try:
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        referrer = request.headers.get("referer", "")
        
        cursor.execute("""
            INSERT INTO referral_clicks 
            (short_code, broker_id, ip_address, user_agent, referrer_url)
            VALUES (?, ?, ?, ?, ?)
        """, (short_code, broker_id, client_ip, user_agent, referrer))
        
        conn.commit()
        logger.info(f"📊 Click tracked: {short_code} -> {broker_email}")
    except Exception as e:
        logger.error(f"Click tracking failed: {e}")
        # Don't fail redirect if tracking fails
    
    # Create redirect with cookies
    redirect_response = RedirectResponse(url="/", status_code=302)
    
    # Set referral cookies (30-day expiry)
    cookie_age = 30 * 24 * 60 * 60  # 30 days
    
    redirect_response.set_cookie(
        key="ref_code",
        value=referral_code,
        max_age=cookie_age,
        httponly=True,
        samesite="lax"
    )
    
    redirect_response.set_cookie(
        key="ref_short",
        value=short_code,
        max_age=cookie_age,
        httponly=True,
        samesite="lax"
    )
    
    redirect_response.set_cookie(
        key="ref_broker",
        value=str(broker_id),
        max_age=cookie_age,
        httponly=True,
        samesite="lax"
    )
    
    logger.info(f"🔗 Referral redirect: {short_code} -> {broker_email}")
    
    return redirect_response
```

## 🔧 STEP 3: UPDATE api/admin.py

### Modify approve_partner function

```python
# In the approve_partner endpoint, after creating broker:

# Generate short code
short_code = ensure_unique_short_code(broker_email, cursor)

# Update broker record
cursor.execute("""
    UPDATE brokers 
    SET short_code = ?, 
        referral_link = ?,
        approved_at = NOW()
    WHERE email = ?
""", (
    short_code,
    f"https://liendeadline.com/r/{short_code}",
    broker_email
))

conn.commit()

# Update email to use short link
referral_link = f"https://liendeadline.com/r/{short_code}"

# Send welcome email with new link
send_broker_welcome_email(
    broker_email=broker_email,
    broker_name=broker_name,
    referral_link=referral_link,
    commission_model=commission_model
)
```

### Update welcome email template

```python
def send_broker_welcome_email(broker_email, broker_name, referral_link, commission_model):
    """Send welcome email with short referral link"""
    
    # Commission details
    if commission_model == "bounty":
        commission_text = "$500 one-time payment per signup"
    else:
        commission_text = "$50/month recurring per active customer"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ color: #2563eb; border-bottom: 3px solid #2563eb; padding-bottom: 10px; }}
            .link-box {{ 
                background: #f3f4f6; 
                padding: 20px; 
                border-radius: 8px; 
                margin: 20px 0;
                text-align: center;
            }}
            .link {{ 
                font-size: 20px; 
                font-weight: bold; 
                color: #2563eb; 
                text-decoration: none;
            }}
            .button {{
                display: inline-block;
                background: #2563eb;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 6px;
                margin: 20px 0;
            }}
            .steps {{ background: #f9fafb; padding: 15px; border-left: 4px solid #2563eb; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1 class="header">Welcome to LienDeadline Partner Program! 🎉</h1>
            
            <p>Hi {broker_name},</p>
            
            <p>Congratulations! Your application to join the LienDeadline Partner Program has been approved!</p>
            
            <h2>Your Referral Link</h2>
            
            <div class="link-box">
                <a href="{referral_link}" class="link">{referral_link}</a>
            </div>
            
            <p style="text-align: center; color: #6b7280; font-size: 14px;">
                ☝️ Share this link to start earning commissions
            </p>
            
            <h2>Commission Structure</h2>
            <p><strong>You earn:</strong> {commission_text}</p>
            
            <div class="steps">
                <h3>How it works:</h3>
                <ol>
                    <li><strong>Share your link</strong> with construction companies, contractors, and material suppliers</li>
                    <li><strong>They sign up</strong> for LienDeadline through your link</li>
                    <li><strong>You earn</strong> when they make their first payment ($299/month)</li>
                    <li><strong>Track everything</strong> in your partner dashboard</li>
                </ol>
            </div>
            
            <div style="text-align: center;">
                <a href="https://liendeadline.com/broker-dashboard" class="button">
                    Access Your Dashboard
                </a>
            </div>
            
            <h3>Tips for Success</h3>
            <ul>
                <li>Share with clients who deal with mechanics liens</li>
                <li>Focus on lumber yards, concrete suppliers, HVAC contractors</li>
                <li>Mention the 30-day free trial (first 50 API calls)</li>
                <li>Emphasize $1.2B lost annually to missed deadlines</li>
            </ul>
            
            <p>Questions? Reply to this email and we'll help!</p>
            
            <p>Best regards,<br>
            <strong>The LienDeadline Team</strong></p>
            
            <hr style="margin: 30px 0; border: none; border-top: 1px solid #e5e7eb;">
            
            <p style="font-size: 12px; color: #6b7280;">
                Your referral code: {referral_link.split('/')[-1]}<br>
                Dashboard: https://liendeadline.com/broker-dashboard
            </p>
        </div>
    </body>
    </html>
    """
    
    try:
        params = {
            "from": os.getenv("SMTP_FROM_EMAIL", "noreply@liendeadline.com"),
            "to": [broker_email],
            "subject": "Welcome to LienDeadline Partner Program! 🎉",
            "html": html_content
        }
        
        response = resend.Emails.send(params)
        logger.info(f"✅ Welcome email sent: {broker_email}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Email failed: {e}")
        raise
```

## 🎨 STEP 4: UPDATE broker-dashboard.html

### Display short link instead of query parameter

Find the referral link section and update:

```javascript
// OLD CODE:
const referralLink = `https://liendeadline.com?ref=${broker.referral_code}`;

// NEW CODE:
const referralLink = broker.referral_link || 
                     `https://liendeadline.com/r/${broker.short_code}`;

// Update the display
document.getElementById('referralLink').textContent = referralLink;
document.getElementById('referralLink').href = referralLink;

// Copy to clipboard button
document.getElementById('copyLinkBtn').addEventListener('click', () => {
    navigator.clipboard.writeText(referralLink);
    // Show success message
    alert('Link copied! Share it to start earning.');
});
```

## 📊 STEP 5: UPDATE ANALYTICS (Optional)

### Track click-through rates

```python
@app.get("/api/broker/analytics/{broker_email}")
async def get_broker_analytics(broker_email: str):
    """Get detailed analytics for broker"""
    
    cursor = get_cursor()
    
    # Get broker
    cursor.execute("""
        SELECT id, short_code, referral_code
        FROM brokers WHERE email = ?
    """, (broker_email,))
    
    broker = cursor.fetchone()
    if not broker:
        raise HTTPException(status_code=404)
    
    broker_id, short_code, referral_code = broker
    
    # Get click stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_clicks,
            COUNT(DISTINCT ip_address) as unique_clicks,
            COUNT(CASE WHEN converted = TRUE THEN 1 END) as conversions
        FROM referral_clicks
        WHERE broker_id = ?
    """, (broker_id,))
    
    clicks = cursor.fetchone()
    
    # Get referral stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_referrals,
            SUM(payout) as total_earned,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_commissions
        FROM referrals
        WHERE broker_id = ?
    """, (referral_code,))
    
    referrals = cursor.fetchone()
    
    return {
        "clicks": {
            "total": clicks[0],
            "unique": clicks[1],
            "conversions": clicks[2],
            "conversion_rate": f"{(clicks[2]/clicks[1]*100) if clicks[1] > 0 else 0:.1f}%"
        },
        "referrals": {
            "total": referrals[0],
            "earned": referrals[1],
            "pending": referrals[2]
        },
        "links": {
            "short": f"https://liendeadline.com/r/{short_code}",
            "referral_code": referral_code
        }
    }
```

## 🧪 STEP 6: TESTING

### Test checklist:

1. **Generate short code for new broker:**
   - Create new partner application
   - Approve in admin dashboard
   - Check email contains short link
   - Verify database has short_code

2. **Test redirect:**
   - Click short link: `https://liendeadline.com/r/mA63`
   - Should redirect to homepage
   - Check cookies are set (use browser dev tools)
   - Verify click tracked in database

3. **Test signup flow:**
   - Visit site via short link
   - Sign up for account
   - Verify broker gets credit

4. **Test broker dashboard:**
   - Login to broker dashboard
   - Verify short link displays correctly
   - Test copy button
   - Check analytics

### SQL queries for testing:

```sql
-- Check all brokers have short codes
SELECT email, short_code, referral_link FROM brokers;

-- Check recent clicks
SELECT * FROM referral_clicks ORDER BY clicked_at DESC LIMIT 10;

-- Check conversion rate per broker
SELECT 
    b.email,
    b.short_code,
    COUNT(rc.id) as clicks,
    COUNT(CASE WHEN rc.converted THEN 1 END) as conversions,
    ROUND(COUNT(CASE WHEN rc.converted THEN 1 END) * 100.0 / COUNT(rc.id), 2) as conversion_rate
FROM brokers b
LEFT JOIN referral_clicks rc ON rc.broker_id = b.id
GROUP BY b.id, b.email, b.short_code;
```

## 🚀 DEPLOYMENT

### Deploy to Railway:

1. **Backup database:**
   ```bash
   # Connect to Railway and export
   pg_dump $DATABASE_URL > backup.sql
   ```

2. **Run migrations:**
   ```bash
   # Add short_code column
   # Generate codes for existing brokers
   ```

3. **Deploy code:**
   ```bash
   git add .
   git commit -m "Add short link system for broker referrals"
   git push origin main
   ```

4. **Test in production:**
   - Approve a test partner
   - Check email has short link
   - Click link and verify redirect
   - Check Railway logs

5. **Update existing brokers (optional):**
   - Re-send welcome emails with new short links
   - Or just use for new brokers going forward

## 📈 EXPECTED IMPROVEMENTS

- **Click-through rate:** 30-50% higher (cleaner links)
- **Shareability:** Easier to say verbally
- **Professional image:** Less "spammy" looking
- **Tracking:** Better analytics with click data
- **Flexibility:** Can create custom branded links later

## 🔧 MAINTENANCE

### Future enhancements:

1. **Custom short codes:**
   - Let brokers choose: `/r/mats` instead of `/r/mA63`
   - Check availability
   - Reserve certain words

2. **QR codes:**
   - Generate QR for short links
   - Great for print materials

3. **Analytics dashboard:**
   - Show click trends
   - Geographic data
   - Device breakdown

4. **A/B testing:**
   - Test different landing pages
   - Optimize conversion rate

## 🆘 TROUBLESHOOTING

**Issue: Duplicate short codes**
- Solution: Use longer codes (6 chars) or add random suffix

**Issue: Redirect not working**
- Check: Route registered in FastAPI
- Check: Broker status is 'approved'
- Check: Cookies being set properly

**Issue: Clicks not tracked**
- Check: referral_clicks table exists
- Check: Database permissions
- Verify: Cursor commit() called

**Issue: Old links still in use**
- Support both: `/r/mA63` AND `?ref=MATS-A63763`
- Gradually phase out old format
