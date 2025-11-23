# portal.py - Stripe Customer Portal endpoint
from fastapi import APIRouter, Depends, HTTPException
from admin import verify_admin
import stripe
import os

router = APIRouter(prefix="/admin", tags=["admin"])

# Initialize Stripe (set your secret key)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_...")

@router.post("/portal")
def create_portal_session(
    customer_id: str,
    return_url: str = "https://app.lien-api.com",
    user: str = Depends(verify_admin)
):
    """
    Create Stripe Customer Portal session.
    
    Args:
        customer_id: Stripe customer ID
        return_url: URL to return to after portal
        user: Admin username (from auth)
    
    Returns:
        Portal session URL
    """
    try:
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url
        )
        
        return {
            "url": session.url,
            "customer_id": customer_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

