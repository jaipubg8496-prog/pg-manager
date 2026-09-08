from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_active_subscription as get_current_owner

router = APIRouter(prefix="/api/properties", tags=["properties"])


def _get_owned_property(property_id: int, owner: models.Owner, db: Session) -> models.Property:
    """Fetch a property but only if it belongs to the logged-in owner. This is the
    pattern every owner-scoped route should follow — never trust an ID alone."""
    prop = (
        db.query(models.Property)
        .filter(models.Property.id == property_id, models.Property.owner_id == owner.id)
        .first()
    )
    if not prop:
        raise HTTPException(status_code=404, detail="Property not found")
    return prop


@router.get("", response_model=list[schemas.PropertyOut])
def list_properties(
    search: str | None = Query(None, description="Filter by name or city (case-insensitive)"),
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    query = db.query(models.Property).filter(models.Property.owner_id == current_owner.id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.Property.name.ilike(like)) | (models.Property.city.ilike(like))
        )
    return query.order_by(models.Property.name).all()


@router.post("", response_model=schemas.PropertyOut, status_code=201)
def create_property(
    payload: schemas.PropertyCreate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    prop = models.Property(owner_id=current_owner.id, **payload.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.get("/{property_id}", response_model=schemas.PropertyOut)
def get_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    return _get_owned_property(property_id, current_owner, db)


@router.put("/{property_id}", response_model=schemas.PropertyOut)
def update_property(
    property_id: int,
    payload: schemas.PropertyUpdate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    prop = _get_owned_property(property_id, current_owner, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(prop, field, value)
    db.commit()
    db.refresh(prop)
    return prop


@router.delete("/{property_id}", status_code=204)
def delete_property(
    property_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    prop = _get_owned_property(property_id, current_owner, db)
    # Cascades handle rooms/beds/tenants/rent_cycles/complaints automatically
    # (see cascade="all, delete-orphan" on the Property model's relationships).
    db.delete(prop)
    db.commit()
    return None
