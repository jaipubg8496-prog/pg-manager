from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_active_subscription as get_current_owner
from app.routers.properties import _get_owned_property
from app.services import rent_service

router = APIRouter(tags=["rent"])


def _get_owned_rent_cycle(cycle_id: int, owner: models.Owner, db: Session) -> models.RentCycle:
    cycle = (
        db.query(models.RentCycle)
        .join(models.Tenant)
        .join(models.Property)
        .filter(models.RentCycle.id == cycle_id, models.Property.owner_id == owner.id)
        .first()
    )
    if not cycle:
        raise HTTPException(status_code=404, detail="Rent cycle not found")
    return cycle


@router.post("/api/properties/{property_id}/rent-cycles/generate", response_model=list[schemas.RentCycleOut])
def generate_rent_cycles(
    property_id: int,
    due_date: date = Query(..., description="Due date for this month's rent, e.g. 2026-10-05"),
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    _get_owned_property(property_id, current_owner, db)
    return rent_service.generate_monthly_rent_cycles(db, property_id, due_date)


@router.get("/api/properties/{property_id}/rent-status")
def rent_status_dashboard(
    property_id: int,
    search: str | None = Query(None, description="Filter by tenant name or phone"),
    status: str | None = Query(None, description="Filter by rent status: pending, paid, partial, overdue"),
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """
    The core screen an owner opens every day: who's paid, who hasn't, and
    how much money is currently outstanding across this property.
    """
    _get_owned_property(property_id, current_owner, db)
    rent_service.mark_overdue_cycles(db, property_id, date.today())

    # Latest rent cycle per active tenant
    tenant_query = db.query(models.Tenant).filter(
        models.Tenant.property_id == property_id, models.Tenant.status == "active"
    )
    if search:
        like = f"%{search}%"
        tenant_query = tenant_query.filter(
            (models.Tenant.name.ilike(like)) | (models.Tenant.phone.ilike(like))
        )
    tenants = tenant_query.order_by(models.Tenant.name).all()

    rows = []
    total_pending = 0
    for tenant in tenants:
        latest_cycle = (
            db.query(models.RentCycle)
            .filter(models.RentCycle.tenant_id == tenant.id)
            .order_by(models.RentCycle.due_date.desc())
            .first()
        )

        # Status filter applies to the tenant's latest cycle status
        if status and (not latest_cycle or latest_cycle.status != status):
            continue

        if latest_cycle and latest_cycle.status in ("pending", "overdue", "partial"):
            total_pending += float(latest_cycle.amount_due) - float(latest_cycle.amount_paid)

        rows.append({
            "tenant_id": tenant.id,
            "tenant_name": tenant.name,
            "phone": tenant.phone,
            "rent_cycle": schemas.RentCycleOut.model_validate(latest_cycle) if latest_cycle else None,
        })

    vacant_beds = (
        db.query(models.Bed)
        .join(models.Room)
        .filter(models.Room.property_id == property_id, models.Bed.status == "vacant")
        .count()
    )

    return {
        "tenants": rows,
        "total_pending_amount": total_pending,
        "vacant_beds": vacant_beds,
    }


@router.post("/api/rent-cycles/{cycle_id}/mark-paid", response_model=schemas.RentCycleOut)
def mark_rent_paid(
    cycle_id: int,
    payload: schemas.MarkPaidRequest,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    cycle = _get_owned_rent_cycle(cycle_id, current_owner, db)

    cycle.amount_paid = payload.amount_paid
    cycle.paid_on = payload.paid_on or date.today()

    if float(payload.amount_paid) >= float(cycle.amount_due):
        cycle.status = "paid"
    else:
        cycle.status = "partial"

    db.commit()
    db.refresh(cycle)
    return cycle


@router.get("/api/rent-cycles/{cycle_id}/reminder-text")
def get_reminder_text(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    cycle = _get_owned_rent_cycle(cycle_id, current_owner, db)
    return rent_service.build_reminder_text(cycle.tenant, cycle)


@router.get("/api/tenants/{tenant_id}/rent-cycles", response_model=list[schemas.RentCycleOut])
def tenant_rent_history(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """Full rent history for one tenant — every cycle ever generated for them."""
    from app.routers.tenants import _get_owned_tenant
    _get_owned_tenant(tenant_id, current_owner, db)  # ownership check

    return (
        db.query(models.RentCycle)
        .filter(models.RentCycle.tenant_id == tenant_id)
        .order_by(models.RentCycle.due_date.desc())
        .all()
    )


@router.delete("/api/rent-cycles/{cycle_id}", status_code=204)
def delete_rent_cycle(
    cycle_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """Removes a rent cycle entirely — use for cleaning up a mistakenly
    generated or duplicate cycle, not for reversing a real payment."""
    cycle = _get_owned_rent_cycle(cycle_id, current_owner, db)
    db.delete(cycle)
    db.commit()
    return None
