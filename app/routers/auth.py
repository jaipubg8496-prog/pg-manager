from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from app.database import get_db
from app import models, schemas
from app.config import TRIAL_DAYS, settings
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_owner

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.OwnerOut, status_code=status.HTTP_201_CREATED)
def signup(payload: schemas.OwnerSignup, db: Session = Depends(get_db)):
    existing = db.query(models.Owner).filter(models.Owner.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")

    owner = models.Owner(
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        trial_ends_at=datetime.utcnow() + timedelta(days=TRIAL_DAYS),
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # OAuth2PasswordRequestForm uses "username" as the field name — we treat it as email.
    owner = db.query(models.Owner).filter(models.Owner.email == form_data.username).first()

    if not owner:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if owner.password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account was created with Google Sign-In. Use the 'Sign in with Google' button instead.",
        )

    if not verify_password(form_data.password, owner.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token = create_access_token(data={"sub": str(owner.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/google-client-id", response_model=schemas.GoogleClientIdOut)
def get_google_client_id():
    """Public — lets the login page know whether to render the Google button
    at all, and what client ID to initialize it with. No secret is exposed
    here; the client ID is meant to be public."""
    return {"google_client_id": settings.google_client_id, "enabled": bool(settings.google_client_id)}


@router.post("/google", response_model=schemas.Token)
def google_login(payload: schemas.GoogleLoginRequest, db: Session = Depends(get_db)):
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="Google Sign-In isn't configured on this server yet.")

    try:
        claims = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google sign-in — please try again.")

    google_sub = claims["sub"]
    email = claims.get("email")
    name = claims.get("name") or (email.split("@")[0] if email else "PG Owner")

    # First, try matching by Google's stable id (fast path for returning users).
    owner = db.query(models.Owner).filter(models.Owner.google_sub == google_sub).first()

    if not owner and email:
        # Second, check if this email already has a password-based account —
        # link Google to it rather than creating a confusing duplicate.
        owner = db.query(models.Owner).filter(models.Owner.email == email).first()
        if owner:
            owner.google_sub = google_sub

    if not owner:
        owner = models.Owner(
            name=name,
            email=email,
            phone="",  # collected later via profile edit if needed
            password_hash=None,
            google_sub=google_sub,
            trial_ends_at=datetime.utcnow() + timedelta(days=TRIAL_DAYS),
        )
        db.add(owner)

    db.commit()
    db.refresh(owner)

    access_token = create_access_token(data={"sub": str(owner.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.OwnerOut)
def read_current_owner(current_owner: models.Owner = Depends(get_current_owner)):
    return current_owner


@router.put("/me", response_model=schemas.OwnerOut)
def update_profile(
    payload: schemas.OwnerProfileUpdate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """Only name and phone are editable here — email is tied to login
    (password or Google) and changing it is deliberately out of scope."""
    current_owner.name = payload.name
    current_owner.phone = payload.phone
    db.commit()
    db.refresh(current_owner)
    return current_owner
