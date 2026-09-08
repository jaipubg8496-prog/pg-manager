from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_active_subscription as get_current_owner
from app.routers.properties import _get_owned_property
from app.routers.tenants import _get_owned_tenant

router = APIRouter(tags=["complaints"])


def _get_owned_complaint(complaint_id: int, owner: models.Owner, db: Session) -> models.Complaint:
    complaint = (
        db.query(models.Complaint)
        .join(models.Tenant)
        .join(models.Property)
        .filter(models.Complaint.id == complaint_id, models.Property.owner_id == owner.id)
        .first()
    )
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint


@router.get("/api/properties/{property_id}/complaints", response_model=list[schemas.ComplaintOut])
def list_complaints(
    property_id: int,
    status: str | None = Query(None, description="Filter by status: open or resolved"),
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    _get_owned_property(property_id, current_owner, db)

    query = (
        db.query(models.Complaint)
        .join(models.Tenant)
        .filter(models.Tenant.property_id == property_id)
    )
    if status:
        query = query.filter(models.Complaint.status == status)
    return query.order_by(models.Complaint.created_at.desc()).all()


@router.post("/api/complaints", response_model=schemas.ComplaintOut, status_code=201)
def create_complaint(
    payload: schemas.ComplaintCreate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    _get_owned_tenant(payload.tenant_id, current_owner, db)  # ownership check

    complaint = models.Complaint(tenant_id=payload.tenant_id, description=payload.description)
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    return complaint


@router.put("/api/complaints/{complaint_id}", response_model=schemas.ComplaintOut)
def update_complaint(
    complaint_id: int,
    payload: schemas.ComplaintUpdate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    complaint = _get_owned_complaint(complaint_id, current_owner, db)
    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(complaint, field, value)

    if updates.get("status") == "resolved" and complaint.resolved_at is None:
        complaint.resolved_at = datetime.utcnow()
    elif updates.get("status") == "open":
        complaint.resolved_at = None

    db.commit()
    db.refresh(complaint)
    return complaint


@router.delete("/api/complaints/{complaint_id}", status_code=204)
def delete_complaint(
    complaint_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    complaint = _get_owned_complaint(complaint_id, current_owner, db)
    db.delete(complaint)
    db.commit()
    return None
