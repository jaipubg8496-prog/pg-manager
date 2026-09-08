from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.config import (
    settings,
    SUBSCRIPTION_PRICE_RUPEES,
    SUBSCRIPTION_PERIOD_DAYS,
)
from app.auth.dependencies import get_current_owner, is_subscription_active

router = APIRouter(
    prefix="/api/billing",
    tags=["billing"],
)


def _razorpay_client():
    """Create Razorpay client when billing is used."""

    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise HTTPException(
            status_code=500,
            detail=(
                "Razorpay is not configured. "
                "Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET."
            ),
        )

    import razorpay

    return razorpay.Client(
        auth=(
            settings.razorpay_key_id,
            settings.razorpay_key_secret,
        )
    )


@router.get(
    "/status",
    response_model=schemas.SubscriptionStatus,
)
def subscription_status(
    current_owner: models.Owner = Depends(get_current_owner),
):
    now = datetime.utcnow()

    active = is_subscription_active(current_owner)

    if (
        current_owner.subscription_active_until
        and now < current_owner.subscription_active_until
    ):
        status_label = "active"

        days_left = (
            current_owner.subscription_active_until - now
        ).days

    elif (
        current_owner.trial_ends_at
        and now < current_owner.trial_ends_at
    ):
        status_label = "trial"

        days_left = (
            current_owner.trial_ends_at - now
        ).days

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


@router.post(
    "/create-order",
    response_model=schemas.RazorpayOrderOut,
)
def create_order(
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    client = _razorpay_client()

    amount_paise = SUBSCRIPTION_PRICE_RUPEES * 100

    order_data = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": f"pg_{current_owner.id}_{int(datetime.utcnow().timestamp())}",
        "notes": {
            "owner_id": str(current_owner.id),
        },
    }

    try:
        order = client.order.create(data=order_data)

    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to create Razorpay order: {str(e)}",
        )

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


@router.post(
    "/verify",
    response_model=schemas.SubscriptionStatus,
)
def verify_payment(
    payload: schemas.VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    client = _razorpay_client()

    payment = (
        db.query(models.Payment)
        .filter(
            models.Payment.razorpay_order_id
            == payload.razorpay_order_id,
            models.Payment.owner_id
            == current_owner.id,
        )
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="No matching order found for this account",
        )

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": payload.razorpay_order_id,
                "razorpay_payment_id": payload.razorpay_payment_id,
                "razorpay_signature": payload.razorpay_signature,
            }
        )

    except Exception:
        payment.status = "failed"
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="Payment verification failed.",
        )

    payment.status = "paid"
    payment.razorpay_payment_id = payload.razorpay_payment_id
    payment.paid_at = datetime.utcnow()

    now = datetime.utcnow()

    if (
        current_owner.subscription_active_until
        and current_owner.subscription_active_until > now
    ):
        base = current_owner.subscription_active_until
    else:
        base = now

    current_owner.subscription_active_until = (
        base + timedelta(days=SUBSCRIPTION_PERIOD_DAYS)
    )

    current_owner.subscription_status = "active"

    db.commit()
    db.refresh(current_owner)

    return subscription_status(current_owner)