from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.config import settings, SUBSCRIPTION_PRICE_RUPEES, SUBSCRIPTION_PERIOD_DAYS
from app.auth.dependencies import get_current_owner, is_subscription_active

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _razorpay_client():
    """Builds the Razorpay client lazily, at call-time, so a missing key
    doesn't crash the whole app at startup — only billing actions fail,
    with a message that tells you exactly what to fix."""
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=500,
            detail="Razorpay isn't configured yet. Add RAZORPAY_KEY_ID and "
                   "RAZORPAY_KEY_SECRET to your .env file.",
        )
    import razorpay  # imported here so the package is only required once billing is actually used
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


@router.get("/status", response_model=schemas.SubscriptionStatus)
def subscription_status(current_owner: models.Owner = Depends(get_current_owner)):
    now = datetime.utcnow()
    active = is_subscription_active(current_owner)

    if current_owner.subscription_active_until and now < current_owner.subscription_active_until:
        status_label = "active"
        days_left = (current_owner.subscription_active_until - now).days
    elif current_owner.trial_ends_at and now < current_owner.trial_ends_at:
        status_label = "trial"
        days_left = (current_owner.trial_ends_at - now).days
    else:
        status_label = "expired"
        days_left = 0

    return schemas.SubscriptionStatus(
        is_active=active,
        status=status_label,
        trial_ends_at=current_owner.trial_ends_at,
        subscription_active_until=current_owner.subscription_active_until,
        days_left=days_left,
        price_rupees=SUBSCRIPTION_PRICE_RUPEES,
    )


@router.post("/create-order", response_model=schemas.RazorpayOrderOut)
def create_order(
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    client = _razorpay_client()
    amount_paise = SUBSCRIPTION_PRICE_RUPEES * 100

    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1,
        "notes": {"owner_id": str(current_owner.id)},
    })

    payment = models.Payment(
        owner_id=current_owner.id,
        razorpay_order_id=order["id"],
        amount_rupees=SUBSCRIPTION_PRICE_RUPEES,
        status="created",
    )
    db.add(payment)
    db.commit()

    return schemas.RazorpayOrderOut(
        order_id=order["id"],
        amount_paise=amount_paise,
        key_id=settings.razorpay_key_id,
    )


@router.post("/verify", response_model=schemas.SubscriptionStatus)
def verify_payment(
    payload: schemas.VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    client = _razorpay_client()

    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.razorpay_order_id == payload.razorpay_order_id,
            models.Payment.owner_id == current_owner.id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="No matching order found for this account")

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": payload.razorpay_order_id,
            "razorpay_payment_id": payload.razorpay_payment_id,
            "razorpay_signature": payload.razorpay_signature,
        })
    except Exception:
        payment.status = "failed"
        db.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed. No charge was applied.")

    payment.status = "paid"
    payment.razorpay_payment_id = payload.razorpay_payment_id
    payment.paid_at = datetime.utcnow()

    # Extend from whichever is later: now, or their current subscription end
    # (so renewing a few days early doesn't lose those remaining days).
    now = datetime.utcnow()
    base = current_owner.subscription_active_until if (current_owner.subscription_active_until and current_owner.subscription_active_until > now) else now
    current_owner.subscription_active_until = base + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
    current_owner.subscription_status = "active"

    db.commit()
    db.refresh(current_owner)

    return subscription_status(current_owner)
