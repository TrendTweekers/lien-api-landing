# Referral Tracking Implementation Guide

## How Referral Tracking Works

### 1. Customer Clicks Referral Link

**Broker's Link:** `lien-api.com?ref=broker_john_123`

**What Happens:**
- Landing page (`script.js`) detects `?ref=` parameter
- Saves referral code to `localStorage`
- Code: `localStorage.setItem('referral_code', 'broker_john_123')`

### 2. Customer Signs Up

**When customer clicks "Get API Key":**

```javascript
// Get referral code from localStorage
const referralCode = localStorage.getItem('referral_code');

// Send to Stripe Checkout with metadata
await stripe.checkout.sessions.create({
  success_url: 'https://app.lien-api.com/success',
  cancel_url: 'https://lien-api.com/pricing',
  metadata: {
    referral_code: referralCode || null  // ← Tracked here
  },
  // ... other checkout params
});
```

### 3. Stripe Webhook Receives Payment

**Your backend webhook handler:**

```javascript
// Stripe webhook endpoint
app.post('/webhook/stripe', async (req, res) => {
  const event = req.body;
  
  if (event.type === 'checkout.session.completed') {
    const session = event.data.object;
    const referralCode = session.metadata.referral_code;
    
    if (referralCode) {
      // Link customer to broker in database
      await db.referrals.create({
        broker_code: referralCode,
        customer_email: session.customer_email,
        customer_id: session.customer,
        subscription_id: session.subscription,
        commission_per_month: 50, // $50 per customer
        status: 'active',
        signup_date: new Date()
      });
      
      // Update broker dashboard (real-time notification)
      notifyBroker(referralCode, {
        newCustomer: session.customer_email,
        commission: 50
      });
    }
  }
  
  res.json({ received: true });
});
```

### 4. Broker Dashboard Updates

**Real-time updates via:**
- WebSocket connection (for live updates)
- Or periodic API polling
- Or server-sent events (SSE)

**Broker sees:**
- New customer appears in "Active Customers" table
- Total customers count increases
- Monthly commission updates automatically

## Email Template Flow

### Broker Dashboard Button

```javascript
// Copy Email Template button
function copyEmailTemplate() {
  const brokerName = 'John';
  const referralCode = 'broker_john_123';
  
  const template = `Subject: Save $15K/year on mechanics lien compliance

Hi [Client Name],

I found a tool that auto-calculates mechanics lien deadlines for your suppliers.

Benefits:
- Never miss another lien deadline
- Covers all 50 states
- $299/month (saves $15K+ in missed liens)

Check it out: lien-api.com?ref=${referralCode}

Let me know if you have questions!

${brokerName}`;

  navigator.clipboard.writeText(template);
  // Show notification: "✅ Email template copied!"
}
```

### Broker's Workflow

1. Log into `partners.lien-api.com/dashboard`
2. Click "Copy Email Template"
3. Paste into Gmail/Outlook
4. Replace `[Client Name]` with actual client name
5. Send to 300 customers
6. Dashboard auto-updates as signups happen

## Monthly Payout Flow

### Automated Payout (1st of each month)

```javascript
// Cron job runs monthly
async function processMonthlyPayouts() {
  const brokers = await db.brokers.findAll();
  
  for (const broker of brokers) {
    const activeReferrals = await db.referrals.findAll({
      where: {
        broker_code: broker.referral_code,
        status: 'active'
      }
    });
    
    const totalCommission = activeReferrals.length * 50; // $50 per customer
    
    if (totalCommission > 0) {
      // Transfer via Stripe Connect
      await stripe.transfers.create({
        amount: totalCommission * 100, // Convert to cents
        currency: 'usd',
        destination: broker.stripe_account_id,
        metadata: {
          period: 'monthly',
          customers: activeReferrals.length
        }
      });
      
      // Log payout
      await db.payouts.create({
        broker_code: broker.referral_code,
        amount: totalCommission,
        customers_count: activeReferrals.length,
        payout_date: new Date()
      });
      
      // Email broker confirmation
      sendPayoutEmail(broker.email, {
        amount: totalCommission,
        customers: activeReferrals.length
      });
    }
  }
}
```

## Database Schema

### Referrals Table

```sql
CREATE TABLE referrals (
  id SERIAL PRIMARY KEY,
  broker_code VARCHAR(255) NOT NULL,
  customer_email VARCHAR(255) NOT NULL,
  customer_id VARCHAR(255), -- Stripe customer ID
  subscription_id VARCHAR(255), -- Stripe subscription ID
  commission_per_month DECIMAL(10,2) DEFAULT 50.00,
  status VARCHAR(50) DEFAULT 'active', -- active, cancelled, paused
  signup_date TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### Brokers Table

```sql
CREATE TABLE brokers (
  id SERIAL PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  referral_code VARCHAR(255) UNIQUE NOT NULL,
  stripe_account_id VARCHAR(255), -- Stripe Connect account
  tier VARCHAR(50) DEFAULT 'bounty', -- bounty or partner
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Payouts Table

```sql
CREATE TABLE payouts (
  id SERIAL PRIMARY KEY,
  broker_code VARCHAR(255) NOT NULL,
  amount DECIMAL(10,2) NOT NULL,
  customers_count INTEGER NOT NULL,
  stripe_transfer_id VARCHAR(255),
  payout_date TIMESTAMP NOT NULL,
  status VARCHAR(50) DEFAULT 'pending', -- pending, completed, failed
  created_at TIMESTAMP DEFAULT NOW()
);
```

## Security Considerations

1. **Validate referral codes** - Ensure they exist in database before tracking
2. **Prevent self-referrals** - Check if customer email matches broker email
3. **Rate limiting** - Prevent abuse of referral system
4. **30-day anti-churn** - Only pay after customer has been active 30 days
5. **Fraud detection** - Monitor for suspicious patterns

## Testing

### Test Referral Flow

1. Visit: `lien-api.com?ref=broker_test_123`
2. Check browser console: Should see "Referral code saved: broker_test_123"
3. Check localStorage: `localStorage.getItem('referral_code')` should return code
4. Simulate signup: Check that referral code is included in Stripe metadata

### Test Email Template

1. Open `broker-dashboard.html`
2. Click "Copy Email Template"
3. Paste into text editor
4. Verify referral link is correct
5. Verify template is professional and clear

## Next Steps

1. **Backend API** - Build endpoints for:
   - Creating broker accounts
   - Tracking referrals
   - Processing payouts
   - Dashboard data

2. **Stripe Integration** - Set up:
   - Stripe Connect for broker payouts
   - Webhook handlers
   - Metadata tracking

3. **Database** - Create tables for:
   - Brokers
   - Referrals
   - Payouts

4. **Authentication** - Add:
   - Broker login system
   - Session management
   - Protected dashboard routes

