# CUSTOMER DASHBOARD LOGIN SYSTEM GUIDE
# For https://liendeadline.com/dashboard

## 🎯 OVERVIEW

**Three Separate Dashboards in Your System:**
1. **/dashboard** - For paying customers ($299/month)
2. **/broker-dashboard** - For partners/affiliates
3. **/admin-dashboard** - For you (the admin)

This guide covers the CUSTOMER dashboard authentication.

---

## 🔐 RECOMMENDED CUSTOMER LOGIN FLOW

### **Option A: API Key Authentication (Simplest - Recommended)**

Best for API products like LienDeadline. No password management needed.

**How it works:**
1. Customer signs up via Stripe checkout
2. Account created automatically after payment
3. API key generated and emailed
4. Customer visits `/dashboard`
5. Enters email + API key
6. Gains access

**Implementation:**

```python
# Generate API key when customer signs up
import secrets

def generate_api_key(customer_email: str) -> str:
    """Generate secure API key"""
    prefix = "ld_"  # liendeadline prefix
    key = secrets.token_urlsafe(32)  # 32 bytes = 43 chars base64
    return f"{prefix}{key}"

# Store in database
cursor.execute("""
    INSERT INTO customers (email, api_key, stripe_customer_id, created_at)
    VALUES (?, ?, ?, NOW())
""", (customer_email, api_key, stripe_customer_id))

# Send welcome email with API key
send_customer_welcome_email(customer_email, api_key)
```

**Dashboard Login:**

```python
@app.post("/api/auth/login")
async def customer_login(email: str, api_key: str):
    """Authenticate customer with email + API key"""
    
    cursor = get_cursor()
    cursor.execute("""
        SELECT id, email, stripe_customer_id, subscription_status
        FROM customers
        WHERE email = ? AND api_key = ? AND subscription_status = 'active'
    """, (email, api_key))
    
    customer = cursor.fetchone()
    
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session token
    session_token = secrets.token_urlsafe(32)
    
    # Store session
    cursor.execute("""
        INSERT INTO sessions (customer_id, token, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
    """, (customer[0], session_token))
    
    conn.commit()
    
    return {
        "session_token": session_token,
        "customer": {
            "email": customer[1],
            "subscription_status": customer[3]
        }
    }
```

**Frontend (dashboard.html):**

```html
<!-- Login Form -->
<div id="loginForm" class="max-w-md mx-auto mt-20">
    <h2 class="text-2xl font-bold mb-6">Customer Login</h2>
    
    <input 
        type="email" 
        id="email" 
        placeholder="Your email"
        class="w-full p-3 border rounded mb-4"
    />
    
    <input 
        type="password" 
        id="apiKey" 
        placeholder="Your API key"
        class="w-full p-3 border rounded mb-4"
    />
    
    <button onclick="login()" class="w-full bg-blue-600 text-white p-3 rounded">
        Sign In
    </button>
    
    <p class="text-sm text-gray-600 mt-4">
        Don't have an API key? Check your welcome email or 
        <a href="/signup" class="text-blue-600">sign up here</a>.
    </p>
</div>

<script>
async function login() {
    const email = document.getElementById('email').value;
    const apiKey = document.getElementById('apiKey').value;
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, api_key: apiKey })
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // Store session token
            localStorage.setItem('session_token', data.session_token);
            localStorage.setItem('customer_email', data.customer.email);
            
            // Hide login, show dashboard
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('dashboardContent').style.display = 'block';
            
            // Load customer data
            loadDashboard();
        } else {
            alert('Invalid email or API key');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Login failed. Please try again.');
    }
}

// Check if already logged in
window.onload = function() {
    const sessionToken = localStorage.getItem('session_token');
    
    if (sessionToken) {
        // Verify session is still valid
        verifySession(sessionToken).then(valid => {
            if (valid) {
                document.getElementById('loginForm').style.display = 'none';
                document.getElementById('dashboardContent').style.display = 'block';
                loadDashboard();
            } else {
                localStorage.removeItem('session_token');
            }
        });
    }
};
</script>
```

---

### **Option B: Email + Password (Traditional)**

More familiar to users, but requires password reset flows.

**Implementation:**

```python
import bcrypt

@app.post("/api/auth/register")
async def register_customer(email: str, password: str, stripe_customer_id: str):
    """Register new customer with password"""
    
    # Hash password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    cursor = get_cursor()
    cursor.execute("""
        INSERT INTO customers (email, password_hash, stripe_customer_id)
        VALUES (?, ?, ?)
    """, (email, password_hash, stripe_customer_id))
    
    conn.commit()
    
    return {"success": True}

@app.post("/api/auth/login")
async def login_customer(email: str, password: str):
    """Login with email + password"""
    
    cursor = get_cursor()
    cursor.execute("""
        SELECT id, email, password_hash, subscription_status
        FROM customers
        WHERE email = ? AND subscription_status = 'active'
    """, (email,))
    
    customer = cursor.fetchone()
    
    if not customer:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not bcrypt.checkpw(password.encode('utf-8'), customer[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session
    session_token = secrets.token_urlsafe(32)
    
    cursor.execute("""
        INSERT INTO sessions (customer_id, token, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
    """, (customer[0], session_token))
    
    conn.commit()
    
    return {"session_token": session_token}
```

---

### **Option C: Magic Link (No Password)**

Most modern approach - no passwords to remember.

**How it works:**
1. User enters email
2. System sends magic link
3. User clicks link
4. Auto-logged in

```python
import secrets
from datetime import datetime, timedelta

@app.post("/api/auth/send-magic-link")
async def send_magic_link(email: str):
    """Send magic link to customer email"""
    
    cursor = get_cursor()
    cursor.execute("""
        SELECT id FROM customers WHERE email = ? AND subscription_status = 'active'
    """, (email,))
    
    customer = cursor.fetchone()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Generate magic token
    magic_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=1)
    
    # Store token
    cursor.execute("""
        INSERT INTO magic_links (customer_id, token, expires_at)
        VALUES (?, ?, ?)
    """, (customer[0], magic_token, expires_at))
    
    conn.commit()
    
    # Send email
    magic_link = f"https://liendeadline.com/auth/verify?token={magic_token}"
    
    send_magic_link_email(email, magic_link)
    
    return {"message": "Magic link sent! Check your email."}

@app.get("/auth/verify")
async def verify_magic_link(token: str):
    """Verify magic link and create session"""
    
    cursor = get_cursor()
    cursor.execute("""
        SELECT customer_id 
        FROM magic_links
        WHERE token = ? AND expires_at > datetime('now') AND used = FALSE
    """, (token,))
    
    result = cursor.fetchone()
    
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired link")
    
    customer_id = result[0]
    
    # Mark token as used
    cursor.execute("UPDATE magic_links SET used = TRUE WHERE token = ?", (token,))
    
    # Create session
    session_token = secrets.token_urlsafe(32)
    cursor.execute("""
        INSERT INTO sessions (customer_id, token, expires_at)
        VALUES (?, ?, datetime('now', '+7 days'))
    """, (customer_id, session_token))
    
    conn.commit()
    
    # Redirect to dashboard with session
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=7*24*60*60,
        httponly=True,
        samesite="lax"
    )
    
    return response
```

---

## 📊 DATABASE SCHEMA

### Required tables:

```sql
-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    api_key VARCHAR UNIQUE,           -- Option A
    password_hash VARCHAR,             -- Option B
    stripe_customer_id VARCHAR UNIQUE,
    subscription_status VARCHAR DEFAULT 'active',
    subscription_tier VARCHAR DEFAULT 'pro',
    api_calls_used INTEGER DEFAULT 0,
    api_calls_limit INTEGER DEFAULT 10000,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    token VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

-- Magic links table (if using Option C)
CREATE TABLE IF NOT EXISTS magic_links (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    token VARCHAR UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

-- Create indexes
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_api_key ON customers(api_key);
CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_customer ON sessions(customer_id);
```

---

## 🎨 DASHBOARD FEATURES TO DISPLAY

Once logged in, show:

```javascript
async function loadDashboard() {
    const sessionToken = localStorage.getItem('session_token');
    
    // Fetch customer data
    const response = await fetch('/api/customer/dashboard', {
        headers: {
            'Authorization': `Bearer ${sessionToken}`
        }
    });
    
    const data = await response.json();
    
    // Display stats
    document.getElementById('apiCallsUsed').textContent = data.api_calls_used;
    document.getElementById('apiCallsLimit').textContent = data.api_calls_limit;
    document.getElementById('subscriptionStatus').textContent = data.subscription_status;
    document.getElementById('currentPlan').textContent = data.subscription_tier;
    
    // Display API key (masked)
    const maskedKey = maskApiKey(data.api_key);
    document.getElementById('apiKey').textContent = maskedKey;
    
    // Load recent API calls
    loadRecentApiCalls();
    
    // Load usage chart
    loadUsageChart();
}

function maskApiKey(key) {
    // Show first 7 and last 4 characters
    return key.substring(0, 7) + '...' + key.substring(key.length - 4);
}
```

**Dashboard sections:**
- API usage statistics
- Current subscription plan
- API key (with copy button)
- Recent API calls log
- Usage charts
- Billing information
- Documentation links
- Support contact

---

## 🔄 STRIPE WEBHOOK INTEGRATION

Create customer account when payment succeeds:

```python
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        customer_email = session['customer_email']
        stripe_customer_id = session['customer']
        
        # Create customer account
        api_key = generate_api_key(customer_email)
        
        cursor = get_cursor()
        cursor.execute("""
            INSERT INTO customers (email, api_key, stripe_customer_id)
            VALUES (?, ?, ?)
        """, (customer_email, api_key, stripe_customer_id))
        
        conn.commit()
        
        # Send welcome email with login credentials
        send_customer_welcome_email(customer_email, api_key)
        
        logger.info(f"✅ Customer account created: {customer_email}")
    
    elif event['type'] == 'customer.subscription.deleted':
        # Handle cancellation
        stripe_customer_id = event['data']['object']['customer']
        
        cursor = get_cursor()
        cursor.execute("""
            UPDATE customers 
            SET subscription_status = 'cancelled'
            WHERE stripe_customer_id = ?
        """, (stripe_customer_id,))
        
        conn.commit()
    
    return {"status": "success"}
```

---

## 📧 WELCOME EMAIL WITH LOGIN CREDENTIALS

```python
def send_customer_welcome_email(email: str, api_key: str):
    """Send welcome email with dashboard access"""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #2563eb;">Welcome to LienDeadline! 🎉</h1>
            
            <p>Thank you for subscribing! Your account is now active.</p>
            
            <h2>Dashboard Access</h2>
            
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p><strong>Dashboard:</strong> <a href="https://liendeadline.com/dashboard">liendeadline.com/dashboard</a></p>
                <p><strong>Email:</strong> {email}</p>
                <p><strong>API Key:</strong> <code style="background: white; padding: 5px;">{api_key}</code></p>
            </div>
            
            <p>⚠️ <strong>Keep your API key secure!</strong> Don't share it publicly.</p>
            
            <h3>Getting Started</h3>
            <ol>
                <li>Visit your dashboard</li>
                <li>Copy your API key</li>
                <li>Check out our API documentation</li>
                <li>Make your first API call</li>
            </ol>
            
            <div style="margin: 30px 0;">
                <a href="https://liendeadline.com/dashboard" 
                   style="background: #2563eb; color: white; padding: 12px 24px; 
                          text-decoration: none; border-radius: 6px; display: inline-block;">
                    Access Dashboard
                </a>
            </div>
            
            <h3>Need Help?</h3>
            <p>Check out our:</p>
            <ul>
                <li><a href="https://liendeadline.com/docs">API Documentation</a></li>
                <li><a href="https://liendeadline.com/examples">Code Examples</a></li>
                <li><a href="mailto:support@liendeadline.com">Email Support</a></li>
            </ul>
            
            <p>Happy calculating!</p>
            
            <p>Best regards,<br>
            <strong>The LienDeadline Team</strong></p>
        </div>
    </body>
    </html>
    """
    
    params = {
        "from": "noreply@liendeadline.com",
        "to": [email],
        "subject": "Welcome to LienDeadline - Your Account is Active!",
        "html": html_content
    }
    
    resend.Emails.send(params)
```

---

## 🧪 TESTING

1. **Create test customer:**
   ```bash
   curl -X POST https://liendeadline.com/api/test/create-customer \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com"}'
   ```

2. **Try logging in:**
   - Visit /dashboard
   - Enter test email + API key
   - Should see dashboard

3. **Test session:**
   - Refresh page
   - Should stay logged in
   - Check localStorage has session_token

4. **Test logout:**
   - Clear localStorage
   - Refresh page
   - Should show login form again

---

## 💡 MY RECOMMENDATION

**Use Option A: API Key Authentication**

**Reasons:**
1. ✅ Perfect for API products
2. ✅ No password reset flows needed
3. ✅ More secure (can rotate keys)
4. ✅ Familiar to developers
5. ✅ Easy to implement
6. ✅ Customers already understand API keys

**Implementation priority:**
1. Set up API key generation
2. Create customer accounts via Stripe webhook
3. Send welcome email with API key
4. Build dashboard login page
5. Add session management
6. Test end-to-end flow

Want me to help implement this?
