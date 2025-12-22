#!/usr/bin/env python3
"""
Test script to simulate broker payout ledger calculations.

Creates:
- 2 brokers (one bounty, one recurring)
- 3 customers
- Multiple payment events
- Shows due/hold/paid calculations
"""

import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

try:
    from services.payout_ledger import (
        BrokerPayoutLedger,
        EarningEvent,
        STATUS_ACTIVE,
        STATUS_CANCELED,
        MODEL_BOUNTY,
        MODEL_RECURRING,
        BOUNTY_AMOUNT,
        RECURRING_AMOUNT
    )
    print("✅ Payout ledger module imported successfully")
except ImportError as e:
    print(f"❌ Failed to import payout ledger: {e}")
    sys.exit(1)


def simulate_broker_ledger():
    """Simulate broker payout scenarios"""
    
    print("\n" + "="*80)
    print("BROKER PAYOUT LEDGER SIMULATION")
    print("="*80 + "\n")
    
    # Scenario 1: One-Time Bounty Broker
    print("📊 SCENARIO 1: One-Time Bounty Broker ($500 per customer)")
    print("-" * 80)
    
    broker1 = BrokerPayoutLedger(
        broker_id=1,
        broker_name="John Doe",
        broker_email="john@example.com",
        commission_model=MODEL_BOUNTY
    )
    
    # Customer 1: Payment 60+ days ago (eligible)
    event1 = EarningEvent(
        referral_id=1,
        broker_id=1,
        customer_email="customer1@example.com",
        customer_stripe_id="cus_001",
        commission_model=MODEL_BOUNTY,
        amount_earned=BOUNTY_AMOUNT,
        payment_date=datetime.now() - timedelta(days=65),
        status=STATUS_ACTIVE
    )
    broker1.add_earning_event(event1)
    
    # Customer 2: Payment 30 days ago (still on hold)
    event2 = EarningEvent(
        referral_id=2,
        broker_id=1,
        customer_email="customer2@example.com",
        customer_stripe_id="cus_002",
        commission_model=MODEL_BOUNTY,
        amount_earned=BOUNTY_AMOUNT,
        payment_date=datetime.now() - timedelta(days=30),
        status=STATUS_ACTIVE
    )
    broker1.add_earning_event(event2)
    
    # Customer 3: Payment paid
    event3 = EarningEvent(
        referral_id=3,
        broker_id=1,
        customer_email="customer3@example.com",
        customer_stripe_id="cus_003",
        commission_model=MODEL_BOUNTY,
        amount_earned=BOUNTY_AMOUNT,
        payment_date=datetime.now() - timedelta(days=70),
        status=STATUS_ACTIVE,
        paid_at=datetime.now() - timedelta(days=5)
    )
    broker1.add_earning_event(event3)
    
    ledger1 = broker1.to_dict()
    print(f"Broker: {ledger1['broker_name']} ({ledger1['broker_email']})")
    print(f"Commission Model: {ledger1['commission_model']}")
    print(f"Total Earned: ${ledger1['total_earned']:.2f}")
    print(f"Total Paid: ${ledger1['total_paid']:.2f}")
    print(f"Total Due Now: ${ledger1['total_due_now']:.2f}")
    print(f"Total On Hold: ${ledger1['total_on_hold']:.2f}")
    print(f"Next Payout Date: {ledger1['next_payout_date']}")
    print(f"\nCustomer Breakdown:")
    for customer_key, breakdown in ledger1['customer_breakdown'].items():
        print(f"  - {breakdown['customer_email']}:")
        print(f"    Earned: ${breakdown['amount_earned']:.2f}, "
              f"Paid: ${breakdown['amount_paid']:.2f}, "
              f"Due: ${breakdown['amount_due_now']:.2f}, "
              f"Hold: ${breakdown['amount_on_hold']:.2f}")
    
    # Scenario 2: Recurring Monthly Broker
    print("\n\n📊 SCENARIO 2: Recurring Monthly Broker ($50/month per customer)")
    print("-" * 80)
    
    broker2 = BrokerPayoutLedger(
        broker_id=2,
        broker_name="Sarah Smith",
        broker_email="sarah@example.com",
        commission_model=MODEL_RECURRING
    )
    
    # Customer 1: 3 monthly payments
    # Payment 1: 70 days ago (eligible)
    event4 = EarningEvent(
        referral_id=4,
        broker_id=2,
        customer_email="client1@example.com",
        customer_stripe_id="cus_101",
        commission_model=MODEL_RECURRING,
        amount_earned=RECURRING_AMOUNT,
        payment_date=datetime.now() - timedelta(days=70),
        status=STATUS_ACTIVE
    )
    broker2.add_earning_event(event4)
    
    # Payment 2: 40 days ago (on hold)
    event5 = EarningEvent(
        referral_id=5,
        broker_id=2,
        customer_email="client1@example.com",
        customer_stripe_id="cus_101",
        commission_model=MODEL_RECURRING,
        amount_earned=RECURRING_AMOUNT,
        payment_date=datetime.now() - timedelta(days=40),
        status=STATUS_ACTIVE
    )
    broker2.add_earning_event(event5)
    
    # Payment 3: 10 days ago (on hold)
    event6 = EarningEvent(
        referral_id=6,
        broker_id=2,
        customer_email="client1@example.com",
        customer_stripe_id="cus_101",
        commission_model=MODEL_RECURRING,
        amount_earned=RECURRING_AMOUNT,
        payment_date=datetime.now() - timedelta(days=10),
        status=STATUS_ACTIVE
    )
    broker2.add_earning_event(event6)
    
    # Customer 2: 2 payments, but canceled
    # Payment 1: 65 days ago (eligible but canceled)
    event7 = EarningEvent(
        referral_id=7,
        broker_id=2,
        customer_email="client2@example.com",
        customer_stripe_id="cus_102",
        commission_model=MODEL_RECURRING,
        amount_earned=RECURRING_AMOUNT,
        payment_date=datetime.now() - timedelta(days=65),
        status=STATUS_CANCELED
    )
    broker2.add_earning_event(event7)
    
    # Payment 2: 35 days ago (on hold but canceled)
    event8 = EarningEvent(
        referral_id=8,
        broker_id=2,
        customer_email="client2@example.com",
        customer_stripe_id="cus_102",
        commission_model=MODEL_RECURRING,
        amount_earned=RECURRING_AMOUNT,
        payment_date=datetime.now() - timedelta(days=35),
        status=STATUS_CANCELED
    )
    broker2.add_earning_event(event8)
    
    ledger2 = broker2.to_dict()
    print(f"Broker: {ledger2['broker_name']} ({ledger2['broker_email']})")
    print(f"Commission Model: {ledger2['commission_model']}")
    print(f"Total Earned: ${ledger2['total_earned']:.2f}")
    print(f"Total Paid: ${ledger2['total_paid']:.2f}")
    print(f"Total Due Now: ${ledger2['total_due_now']:.2f}")
    print(f"Total On Hold: ${ledger2['total_on_hold']:.2f}")
    print(f"Next Payout Date: {ledger2['next_payout_date']}")
    print(f"\nCustomer Breakdown:")
    for customer_key, breakdown in ledger2['customer_breakdown'].items():
        print(f"  - {breakdown['customer_email']} ({breakdown['status']}):")
        print(f"    Earned: ${breakdown['amount_earned']:.2f}, "
              f"Paid: ${breakdown['amount_paid']:.2f}, "
              f"Due: ${breakdown['amount_due_now']:.2f}, "
              f"Hold: ${breakdown['amount_on_hold']:.2f}")
    
    # Summary
    print("\n\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nBroker 1 (Bounty):")
    print(f"  Due Now: ${ledger1['total_due_now']:.2f}")
    print(f"  On Hold: ${ledger1['total_on_hold']:.2f}")
    print(f"  Paid: ${ledger1['total_paid']:.2f}")
    
    print(f"\nBroker 2 (Recurring):")
    print(f"  Due Now: ${ledger2['total_due_now']:.2f}")
    print(f"  On Hold: ${ledger2['total_on_hold']:.2f}")
    print(f"  Paid: ${ledger2['total_paid']:.2f}")
    
    print(f"\n✅ Simulation complete!")
    print(f"\nExpected Results:")
    print(f"  - Broker 1 should have $500 due (customer1 eligible)")
    print(f"  - Broker 1 should have $500 on hold (customer2 not yet eligible)")
    print(f"  - Broker 1 should have $500 paid (customer3)")
    print(f"  - Broker 2 should have $50 due (client1 payment1 eligible)")
    print(f"  - Broker 2 should have $100 on hold (client1 payments 2-3)")
    print(f"  - Broker 2 should have $0 due for client2 (canceled)")


if __name__ == "__main__":
    simulate_broker_ledger()

