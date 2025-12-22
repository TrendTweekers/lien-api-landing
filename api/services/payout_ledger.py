"""
Payout Ledger Service
Canonical computation of broker payout amounts: Due / Hold / Paid

Rules:
- ONE-TIME $500: One earning event per customer at first successful payment
  - Becomes payable at payment_date + 60 days if customer still ACTIVE
  - Never pay twice for same customer
  
- RECURRING $50/month: One earning event per successful monthly charge
  - Each event becomes payable at charge_date + 60 days
  - Only if that specific charge is not refunded/chargeback
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import json

# Status constants
STATUS_ACTIVE = 'ACTIVE'
STATUS_CANCELED = 'CANCELED'
STATUS_REFUNDED = 'REFUNDED'
STATUS_CHARGEBACK = 'CHARGEBACK'
STATUS_PAST_DUE = 'PAST_DUE'

# Commission models
MODEL_BOUNTY = 'bounty'  # $500 one-time
MODEL_RECURRING = 'recurring'  # $50/month

# Payout amounts
BOUNTY_AMOUNT = Decimal('500.00')
RECURRING_AMOUNT = Decimal('50.00')

# Hold period (days)
HOLD_PERIOD_DAYS = 60


class EarningEvent:
    """Represents a single earning event (one-time or recurring payment)"""
    def __init__(
        self,
        referral_id: int,
        broker_id: int,
        customer_email: str,
        customer_stripe_id: Optional[str],
        commission_model: str,
        amount_earned: Decimal,
        payment_date: datetime,
        status: str = STATUS_ACTIVE,
        paid_at: Optional[datetime] = None,
        paid_batch_id: Optional[str] = None
    ):
        self.referral_id = referral_id
        self.broker_id = broker_id
        self.customer_email = customer_email
        self.customer_stripe_id = customer_stripe_id
        self.commission_model = commission_model
        self.amount_earned = amount_earned
        self.payment_date = payment_date
        self.status = status
        self.paid_at = paid_at
        self.paid_batch_id = paid_batch_id
        
        # Calculate eligibility
        self.eligible_at = payment_date + timedelta(days=HOLD_PERIOD_DAYS)
        self.is_eligible = datetime.now() >= self.eligible_at
        self.is_paid = paid_at is not None
        
        # Determine amounts
        if self.is_paid:
            self.amount_paid = self.amount_earned
            self.amount_due_now = Decimal('0.00')
            self.amount_on_hold = Decimal('0.00')
        elif self.is_eligible and self.status == STATUS_ACTIVE:
            self.amount_paid = Decimal('0.00')
            self.amount_due_now = self.amount_earned
            self.amount_on_hold = Decimal('0.00')
        else:
            self.amount_paid = Decimal('0.00')
            self.amount_due_now = Decimal('0.00')
            self.amount_on_hold = self.amount_earned
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for API responses"""
        return {
            'referral_id': self.referral_id,
            'customer_email': self.customer_email,
            'customer_stripe_id': self.customer_stripe_id,
            'commission_model': self.commission_model,
            'payment_date': self.payment_date.isoformat(),
            'amount_earned': float(self.amount_earned),
            'amount_paid': float(self.amount_paid),
            'amount_due_now': float(self.amount_due_now),
            'amount_on_hold': float(self.amount_on_hold),
            'status': self.status,
            'eligible_at': self.eligible_at.isoformat(),
            'is_eligible': self.is_eligible,
            'is_paid': self.is_paid,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'paid_batch_id': self.paid_batch_id
        }


class BrokerPayoutLedger:
    """Canonical payout ledger for a single broker"""
    def __init__(self, broker_id: int, broker_name: str, broker_email: str, commission_model: str):
        self.broker_id = broker_id
        self.broker_name = broker_name
        self.broker_email = broker_email
        self.commission_model = commission_model
        self.earning_events: List[EarningEvent] = []
        
        # Computed totals
        self.total_earned = Decimal('0.00')
        self.total_paid = Decimal('0.00')
        self.total_due_now = Decimal('0.00')
        self.total_on_hold = Decimal('0.00')
        self.next_payout_date: Optional[datetime] = None
        
        # Breakdown by customer
        self.customer_breakdown: Dict[str, Dict] = {}
    
    def add_earning_event(self, event: EarningEvent):
        """Add an earning event to the ledger"""
        self.earning_events.append(event)
        
        # Update totals
        self.total_earned += event.amount_earned
        self.total_paid += event.amount_paid
        self.total_due_now += event.amount_due_now
        self.total_on_hold += event.amount_on_hold
        
        # Update next payout date (earliest eligible unpaid event)
        if event.amount_due_now > 0:
            if self.next_payout_date is None or event.eligible_at < self.next_payout_date:
                self.next_payout_date = event.eligible_at
        
        # Update customer breakdown
        customer_key = event.customer_email or event.customer_stripe_id or 'unknown'
        if customer_key not in self.customer_breakdown:
            self.customer_breakdown[customer_key] = {
                'customer_email': event.customer_email,
                'customer_stripe_id': event.customer_stripe_id,
                'commission_model': event.commission_model,
                'last_payment_date': event.payment_date,
                'amount_earned': Decimal('0.00'),
                'amount_paid': Decimal('0.00'),
                'amount_due_now': Decimal('0.00'),
                'amount_on_hold': Decimal('0.00'),
                'status': event.status,
                'events': []
            }
        
        breakdown = self.customer_breakdown[customer_key]
        breakdown['amount_earned'] += event.amount_earned
        breakdown['amount_paid'] += event.amount_paid
        breakdown['amount_due_now'] += event.amount_due_now
        breakdown['amount_on_hold'] += event.amount_on_hold
        
        # Update last payment date if this is more recent
        if event.payment_date > breakdown['last_payment_date']:
            breakdown['last_payment_date'] = event.payment_date
            breakdown['status'] = event.status
        
        breakdown['events'].append(event.to_dict())
    
    def to_dict(self) -> Dict:
        """Convert ledger to dictionary for API responses"""
        return {
            'broker_id': self.broker_id,
            'broker_name': self.broker_name,
            'broker_email': self.broker_email,
            'commission_model': self.commission_model,
            'total_earned': float(self.total_earned),
            'total_paid': float(self.total_paid),
            'total_due_now': float(self.total_due_now),
            'total_on_hold': float(self.total_on_hold),
            'next_payout_date': self.next_payout_date.isoformat() if self.next_payout_date else None,
            'customer_breakdown': {
                customer_key: {
                    **breakdown,
                    'amount_earned': float(breakdown['amount_earned']),
                    'amount_paid': float(breakdown['amount_paid']),
                    'amount_due_now': float(breakdown['amount_due_now']),
                    'amount_on_hold': float(breakdown['amount_on_hold']),
                    'last_payment_date': breakdown['last_payment_date'].isoformat()
                }
                for customer_key, breakdown in self.customer_breakdown.items()
            },
            'earning_events': [event.to_dict() for event in self.earning_events]
        }


def compute_broker_ledger(
    cursor,
    broker_id: int,
    db_type: str = 'postgresql'
) -> BrokerPayoutLedger:
    """
    Compute the canonical payout ledger for a broker.
    
    This is the single source of truth for payout calculations.
    All payout endpoints should use this function.
    """
    # Get broker info
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT id, name, email, commission_model
            FROM brokers
            WHERE id = %s
        """, (broker_id,))
    else:
        cursor.execute("""
            SELECT id, name, email, commission_model
            FROM brokers
            WHERE id = ?
        """, (broker_id,))
    
    broker_row = cursor.fetchone()
    if not broker_row:
        raise ValueError(f"Broker {broker_id} not found")
    
    if isinstance(broker_row, dict):
        broker_name = broker_row.get('name', 'Unknown')
        broker_email = broker_row.get('email', '')
        commission_model = broker_row.get('commission_model', MODEL_BOUNTY)
    else:
        broker_name = broker_row[1] if len(broker_row) > 1 else 'Unknown'
        broker_email = broker_row[2] if len(broker_row) > 2 else ''
        commission_model = broker_row[3] if len(broker_row) > 3 else MODEL_BOUNTY
    
    ledger = BrokerPayoutLedger(broker_id, broker_name, broker_email, commission_model)
    
    # Get all referrals for this broker
    # Note: We need to check if the referrals table has the new columns
    # For now, we'll query what exists and adapt
    
    # Get broker's referral_code to match referrals table
    # referrals.broker_id stores the referral_code (text), not the numeric id
    if db_type == 'postgresql':
        cursor.execute("""
            SELECT referral_code FROM brokers WHERE id = %s
        """, (broker_id,))
    else:
        cursor.execute("""
            SELECT referral_code FROM brokers WHERE id = ?
        """, (broker_id,))
    
    broker_ref_result = cursor.fetchone()
    broker_referral_code = None
    if broker_ref_result:
        if isinstance(broker_ref_result, dict):
            broker_referral_code = broker_ref_result.get('referral_code')
        else:
            broker_referral_code = broker_ref_result[0] if len(broker_ref_result) > 0 else None
    
    if not broker_referral_code:
        # No referral code found, return empty ledger
        return ledger
    
    # Query referrals by broker_id (which stores referral_code string)
    if db_type == 'postgresql':
        # Try to get referrals with payment tracking
        try:
            cursor.execute("""
                SELECT 
                    r.id,
                    r.broker_id,
                    r.customer_email,
                    r.customer_stripe_id,
                    r.payout_type,
                    r.payout,
                    r.status,
                    r.hold_until,
                    r.created_at,
                    r.paid_at,
                    r.payment_date,
                    r.paid_batch_id
                FROM referrals r
                WHERE r.broker_id = %s
                ORDER BY r.created_at ASC
            """, (broker_referral_code,))
        except Exception:
            # Fallback: query without payment_date column
            cursor.execute("""
                SELECT 
                    r.id,
                    r.broker_id,
                    r.customer_email,
                    r.customer_stripe_id,
                    r.payout_type,
                    r.payout,
                    r.status,
                    r.hold_until,
                    r.created_at,
                    r.paid_at,
                    NULL as payment_date,
                    NULL as paid_batch_id
                FROM referrals r
                WHERE r.broker_id = %s
                ORDER BY r.created_at ASC
            """, (broker_referral_code,))
    else:
        try:
            cursor.execute("""
                SELECT 
                    r.id,
                    r.broker_id,
                    r.customer_email,
                    r.customer_stripe_id,
                    r.payout_type,
                    r.payout,
                    r.status,
                    r.hold_until,
                    r.created_at,
                    r.paid_at,
                    r.payment_date,
                    r.paid_batch_id
                FROM referrals r
                WHERE r.broker_id = ?
                ORDER BY r.created_at ASC
            """, (broker_referral_code,))
        except Exception:
            cursor.execute("""
                SELECT 
                    r.id,
                    r.broker_id,
                    r.customer_email,
                    r.customer_stripe_id,
                    r.payout_type,
                    r.payout,
                    r.status,
                    r.hold_until,
                    r.created_at,
                    r.paid_at,
                    NULL as payment_date,
                    NULL as paid_batch_id
                FROM referrals r
                WHERE r.broker_id = ?
                ORDER BY r.created_at ASC
            """, (broker_referral_code,))
    
    referrals = cursor.fetchall()
    
    # Process each referral into earning events
    for ref in referrals:
        if isinstance(ref, dict):
            ref_id = ref.get('id')
            customer_email = ref.get('customer_email', '')
            customer_stripe_id = ref.get('customer_stripe_id')
            payout_type = ref.get('payout_type', commission_model)
            payout_amount = Decimal(str(ref.get('payout', 0)))
            status = ref.get('status', 'on_hold')
            hold_until = ref.get('hold_until')
            created_at = ref.get('created_at')
            paid_at = ref.get('paid_at')
            payment_date = ref.get('payment_date') or created_at
            paid_batch_id = ref.get('paid_batch_id')
        else:
            ref_id = ref[0] if len(ref) > 0 else None
            customer_email = ref[2] if len(ref) > 2 else ''
            customer_stripe_id = ref[3] if len(ref) > 3 else None
            payout_type = ref[4] if len(ref) > 4 else commission_model
            payout_amount = Decimal(str(ref[5] if len(ref) > 5 else 0))
            status = ref[6] if len(ref) > 6 else 'on_hold'
            hold_until = ref[7] if len(ref) > 7 else None
            created_at = ref[8] if len(ref) > 8 else None
            paid_at = ref[9] if len(ref) > 9 else None
            payment_date = ref[10] if len(ref) > 10 else created_at
            paid_batch_id = ref[11] if len(ref) > 11 else None
        
        if not ref_id:
            continue
        
        # Parse dates
        if isinstance(payment_date, str):
            try:
                payment_date = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
            except:
                payment_date = datetime.now()
        elif payment_date is None:
            payment_date = datetime.now()
        
        if isinstance(paid_at, str):
            try:
                paid_at = datetime.fromisoformat(paid_at.replace('Z', '+00:00'))
            except:
                paid_at = None
        
        # Map status
        status_mapped = STATUS_ACTIVE
        if status in ['canceled', 'cancelled', 'CANCELED']:
            status_mapped = STATUS_CANCELED
        elif status in ['refunded', 'REFUNDED']:
            status_mapped = STATUS_REFUNDED
        elif status in ['chargeback', 'CHARGEBACK']:
            status_mapped = STATUS_CHARGEBACK
        elif status in ['past_due', 'PAST_DUE']:
            status_mapped = STATUS_PAST_DUE
        
        # Determine commission model
        if payout_type == 'recurring' or commission_model == MODEL_RECURRING:
            commission_model_used = MODEL_RECURRING
        else:
            commission_model_used = MODEL_BOUNTY
        
        # Create earning event
        event = EarningEvent(
            referral_id=ref_id,
            broker_id=broker_id,
            customer_email=customer_email,
            customer_stripe_id=customer_stripe_id,
            commission_model=commission_model_used,
            amount_earned=payout_amount,
            payment_date=payment_date,
            status=status_mapped,
            paid_at=paid_at,
            paid_batch_id=paid_batch_id
        )
        
        ledger.add_earning_event(event)
    
    return ledger


def compute_all_brokers_ledgers(cursor, db_type: str = 'postgresql') -> List[BrokerPayoutLedger]:
    """Compute ledgers for all brokers"""
    if db_type == 'postgresql':
        cursor.execute("SELECT id FROM brokers WHERE status IN ('approved', 'active')")
    else:
        cursor.execute("SELECT id FROM brokers WHERE status IN ('approved', 'active') OR status IS NULL")
    
    broker_ids = cursor.fetchall()
    ledgers = []
    
    for broker_row in broker_ids:
        broker_id = broker_row[0] if isinstance(broker_row, (list, tuple)) else broker_row.get('id')
        try:
            ledger = compute_broker_ledger(cursor, broker_id, db_type)
            ledgers.append(ledger)
        except Exception as e:
            print(f"Error computing ledger for broker {broker_id}: {e}")
            continue
    
    return ledgers

