# Payment Control System - Admin Dashboard

## Overview

The payment system uses **automated queueing with manual approval** - 95% automated, 5% your control.

## How It Works

### Automated Flow

```
Day 1: Customer signs up with ?ref=broker_john
     ↓
Stripe stores metadata: { referral: 'broker_john' }
     ↓
Day 60: Webhook fires "60 days passed"
     ↓
Check if customer still active
     ↓
IF active → Auto-queue payout
IF cancelled → No payout
     ↓
Day 61: Admin dashboard shows pending payout
     ↓
You click [Approve] → Stripe Connect transfers $500
```

### Monthly Recurring Flow

```
1st of Month: Cron job runs
     ↓
Calculate all active recurring broker commissions
     ↓
Queue payouts in admin dashboard
     ↓
You review and approve batch
     ↓
Stripe Connect transfers all at once
```

## Admin Dashboard Features

### Payout Queue

**Location**: Admin Dashboard → Payouts Tab

**Shows**:
- Broker name
- Customer name
- Amount ($500 or $50/month)
- Days active (must be 60+ for bounty)
- Status (Ready/Pending)

**Actions**:
- ✅ **Approve** - Transfer money via Stripe Connect
- ❌ **Reject** - Cancel payout (with reason)
- 📋 **View Details** - See full customer history

### Approval Process

1. **Automated Queueing**:
   - System calculates payouts automatically
   - Checks 60-day churn protection
   - Queues ready payouts

2. **Manual Review**:
   - You see pending payouts in dashboard
   - Review each payout
   - Click "Approve" or "Reject"

3. **Payment Execution**:
   - Stripe Connect transfers money
   - Payout logged in history
   - Broker notified via email

## Why Manual Approval?

### Benefits:

✅ **Fraud Protection** - Review before paying
✅ **Cash Flow Control** - Approve when you're ready
✅ **Error Prevention** - Catch mistakes before payment
✅ **Audit Trail** - Every payout is reviewed

### What Gets Automated:

✅ Payout calculation
✅ 60-day churn check
✅ Queue management
✅ Email notifications
✅ Payment execution (after approval)

### What You Control:

✅ Final approval button
✅ Reject with reason
✅ Batch approval
✅ Manual override

## Implementation

### Backend (FastAPI)

```python
# routes/admin.py

@app.get("/admin/payouts/pending")
def get_pending_payouts():
    """Get all payouts ready for approval"""
    payouts = db.payouts.filter(status='ready')
    return payouts

@app.post("/admin/payouts/{payout_id}/approve")
def approve_payout(payout_id: int):
    """Approve and execute payout"""
    payout = db.payouts.get(payout_id)
    
    # Transfer via Stripe Connect
    transfer = stripe.transfers.create(
        amount=payout.amount * 100,
        currency='usd',
        destination=payout.broker.stripe_account_id
    )
    
    # Update payout status
    payout.status = 'paid'
    payout.stripe_transfer_id = transfer.id
    payout.paid_at = datetime.now()
    db.save(payout)
    
    # Notify broker
    send_email(payout.broker.email, 'payout_confirmed', {
        'amount': payout.amount,
        'customer': payout.customer.name
    })
    
    return {'status': 'approved', 'transfer_id': transfer.id}

@app.post("/admin/payouts/{payout_id}/reject")
def reject_payout(payout_id: int, reason: str):
    """Reject payout with reason"""
    payout = db.payouts.get(payout_id)
    payout.status = 'rejected'
    payout.rejection_reason = reason
    db.save(payout)
    
    return {'status': 'rejected'}
```

### Automated Queueing (Cron Job)

```python
# cron/payout_queue.py

def queue_payouts():
    """Run daily - queue payouts that are ready"""
    
    # Bounty payouts (60 days active)
    active_customers = db.customers.filter(
        status='active',
        days_active__gte=60,
        payout_status='pending'
    )
    
    for customer in active_customers:
        if customer.referral_code:
            broker = db.brokers.get(referral_code=customer.referral_code)
            
            if broker.commission_model == 'bounty':
                # Queue $500 payout
                db.payouts.create(
                    broker_id=broker.id,
                    customer_id=customer.id,
                    amount=500,
                    type='bounty',
                    status='ready',
                    queued_at=datetime.now()
                )
    
    # Recurring payouts (monthly on 1st)
    if datetime.now().day == 1:
        recurring_brokers = db.brokers.filter(commission_model='recurring')
        
        for broker in recurring_brokers:
            active_referrals = db.referrals.filter(
                broker_id=broker.id,
                status='active'
            )
            
            total_commission = len(active_referrals) * 50
            
            if total_commission > 0:
                db.payouts.create(
                    broker_id=broker.id,
                    amount=total_commission,
                    type='recurring',
                    status='ready',
                    queued_at=datetime.now()
                )
```

## Admin Dashboard UI

### Payout Queue Display

```html
<!-- admin-dashboard.html -->

<div id="pending-payouts-list">
    <!-- Each payout card -->
    <div class="payout-card">
        <div>
            <div class="broker-name">John Smith</div>
            <div class="customer-name">Customer: ABC Supply</div>
            <div class="days-active">Active for 32 days</div>
        </div>
        <div>
            <div class="amount">$500</div>
            <button onclick="approvePayout(123)">Approve</button>
            <button onclick="rejectPayout(123)">Reject</button>
        </div>
    </div>
</div>
```

## Security

### Authentication

- Admin dashboard requires admin login
- JWT token authentication
- Role-based access control

### Audit Log

Every action is logged:
- Who approved/rejected
- When
- Why (if rejected)
- Stripe transfer ID

## Best Practices

1. **Review Daily** - Check payout queue each morning
2. **Batch Approve** - Approve multiple at once (if confident)
3. **Document Rejections** - Always add reason when rejecting
4. **Monitor Stripe** - Check Stripe dashboard for transfers
5. **Set Alerts** - Get notified when large payouts queue

## Cost Control

### Limits You Can Set:

- Maximum payout per broker per month
- Minimum payout threshold (e.g., $100)
- Hold period for new brokers (e.g., 60 days)

### Example Limits:

```python
MAX_PAYOUT_PER_BROKER = 5000  # $5,000/month max
MIN_PAYOUT_THRESHOLD = 100    # Don't pay < $100
NEW_BROKER_HOLD = 60          # Hold 60 days for new brokers
```

## Summary

**Automated**: Calculation, queueing, churn checks
**Manual**: Final approval, rejection, overrides
**Result**: Fast, secure, controlled payments

You have full control while minimizing manual work! 🎯

