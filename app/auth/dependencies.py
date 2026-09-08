from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.auth.security import decode_access_token
from app import models

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_owner(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.Owner:
    """
    Decodes the JWT, loads the owner from DB.
    Every protected route depends on this — this is what guarantees
    one owner can never see another owner's data.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    owner_id = payload.get("sub")
    if owner_id is None:
        raise credentials_error

    owner = db.query(models.Owner).filter(models.Owner.id == int(owner_id)).first()
    if owner is None:
        raise credentials_error

    return owner


def is_subscription_active(owner: models.Owner) -> bool:
    """True if the owner is still inside their free trial OR has a paid
    subscription that hasn't lapsed yet. This is the one source of truth —
    the frontend's blur/paywall is just a UI reflection of this same check."""
    now = datetime.utcnow()
    trial_active = bool(owner.trial_ends_at and now < owner.trial_ends_at)
    subscription_active = bool(owner.subscription_active_until and now < owner.subscription_active_until)
    return trial_active or subscription_active


def require_active_subscription(
    current_owner: models.Owner = Depends(get_current_owner),
) -> models.Owner:
    """Same as get_current_owner, but also blocks access once the trial has
    ended and there's no active paid subscription. Use this instead of
    get_current_owner on any route that reveals or changes real PG data —
    auth and billing routes should keep using plain get_current_owner so a
    locked-out owner can still log in and pay."""
    if not is_subscription_active(current_owner):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Your free trial has ended. Subscribe to keep using PG Manager.",
        )
    return current_owner
