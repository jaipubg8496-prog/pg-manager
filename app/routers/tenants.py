from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_active_subscription as get_current_owner
from app.routers.properties import _get_owned_property

router = APIRouter(tags=["tenants"])


def _get_owned_tenant(tenant_id: int, owner: models.Owner, db: Session) -> models.Tenant:
    """Fetch a tenant, but only if it belongs to one of this owner's properties."""
    tenant = (
        db.query(models.Tenant)
        .join(models.Property)
        .filter(models.Tenant.id == tenant_id, models.Property.owner_id == owner.id)
        .first()
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/api/properties/{property_id}/tenants", response_model=list[schemas.TenantOut])
def list_tenants(
    property_id: int,
    search: str | None = Query(None, description="Filter by tenant name or phone"),
    status: str | None = Query(None, description="Filter by status: active or moved_out"),
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    _get_owned_property(property_id, current_owner, db)

    query = db.query(models.Tenant).filter(models.Tenant.property_id == property_id)
    if status:
        query = query.filter(models.Tenant.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (models.Tenant.name.ilike(like)) | (models.Tenant.phone.ilike(like))
        )
    return query.order_by(models.Tenant.name).all()


@router.post("/api/properties/{property_id}/tenants", response_model=schemas.TenantOut, status_code=201)
def create_tenant(
    property_id: int,
    payload: schemas.TenantCreate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    _get_owned_property(property_id, current_owner, db)

    bed = db.query(models.Bed).filter(models.Bed.id == payload.bed_id).first()
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    if bed.status == "occupied":
        raise HTTPException(status_code=400, detail="This bed is already occupied")

    tenant = models.Tenant(
        property_id=property_id,
        bed_id=payload.bed_id,
        name=payload.name,
        phone=payload.phone,
        id_proof_type=payload.id_proof_type,
        id_proof_number=payload.id_proof_number,
        move_in_date=payload.move_in_date,
        monthly_rent=payload.monthly_rent,
        status="active",
    )
    bed.status = "occupied"

    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/api/tenants/{tenant_id}", response_model=schemas.TenantOut)
def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    return _get_owned_tenant(tenant_id, current_owner, db)


@router.put("/api/tenants/{tenant_id}", response_model=schemas.TenantOut)
def update_tenant(
    tenant_id: int,
    payload: schemas.TenantUpdate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """Edit tenant details — name, phone, ID proof, rent amount. Does not
    change bed assignment or status; use /move-out for that."""
    tenant = _get_owned_tenant(tenant_id, current_owner, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.put("/api/tenants/{tenant_id}/move-out", response_model=schemas.TenantOut)
def move_out_tenant(
    tenant_id: int,
    payload: schemas.TenantMoveOut,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """Marks a tenant as moved out and frees their bed — this is what makes
    the bed show up as 'vacant' again everywhere in the app."""
    tenant = _get_owned_tenant(tenant_id, current_owner, db)

    tenant.status = "moved_out"
    tenant.move_out_date = payload.move_out_date

    if tenant.bed:
        tenant.bed.status = "vacant"
        tenant.bed_id = None  # detach so the bed can be freely reassigned

    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/api/tenants/{tenant_id}", status_code=204)
def delete_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """Permanently removes a tenant record (and their rent/complaint history).
    Frees the bed first if they were still active. Prefer move-out over this
    for real tenants — use delete mainly to clean up test/mistaken entries."""
    tenant = _get_owned_tenant(tenant_id, current_owner, db)

    if tenant.bed and tenant.status == "active":
        tenant.bed.status = "vacant"

    db.delete(tenant)
    db.commit()
    return None
