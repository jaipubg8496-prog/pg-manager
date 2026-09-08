from datetime import date
from urllib.parse import quote

from sqlalchemy.orm import Session

from app import models


def generate_monthly_rent_cycles(db: Session, property_id: int, due_date: date) -> list[models.RentCycle]:
    """
    Creates one rent_cycle row per active tenant in this property for the given due_date,
    unless one already exists for that tenant + month (avoids duplicate cycles if the
    owner clicks 'generate' twice).

    Called by the owner from the dashboard once a month (a manual button click is fine
    for the MVP — a scheduled cron job can automate this later).
    """
    active_tenants = (
        db.query(models.Tenant)
        .filter(models.Tenant.property_id == property_id, models.Tenant.status == "active")
        .all()
    )

    created = []
    for tenant in active_tenants:
        already_exists = (
            db.query(models.RentCycle)
            .filter(
                models.RentCycle.tenant_id == tenant.id,
                models.RentCycle.due_date == due_date,
            )
            .first()
        )
        if already_exists:
            continue

        cycle = models.RentCycle(
            tenant_id=tenant.id,
            due_date=due_date,
            amount_due=tenant.monthly_rent,
            amount_paid=0,
            status="pending",
        )
        db.add(cycle)
        created.append(cycle)

    db.commit()
    for cycle in created:
        db.refresh(cycle)

    return created


def mark_overdue_cycles(db: Session, property_id: int, today: date) -> None:
    """Flips any 'pending' cycle past its due date to 'overdue'. Call this before
    building the rent-status dashboard so the numbers are always current.

    SQLAlchemy's bulk .update() can't run on a query that already has a .join()
    in it, so we get the tenant ids for this property first, then filter
    RentCycle by that list instead of joining directly.
    """
    tenant_ids = (
        db.query(models.Tenant.id)
        .filter(models.Tenant.property_id == property_id)
        .subquery()
    )

    (
        db.query(models.RentCycle)
        .filter(
            models.RentCycle.tenant_id.in_(db.query(tenant_ids)),
            models.RentCycle.status == "pending",
            models.RentCycle.due_date < today,
        )
        .update({models.RentCycle.status: "overdue"}, synchronize_session=False)
    )
    db.commit()


def build_reminder_text(tenant: models.Tenant, cycle: models.RentCycle) -> dict:
    """
    Builds a WhatsApp-ready reminder message and a wa.me deep link.
    No WhatsApp Business API needed for the MVP — this just pre-fills the message
    so the owner taps once to open a chat with the text already typed in.
    """
    message = (
        f"Hi {tenant.name}, this is a reminder that your PG rent of "
        f"Rs. {cycle.amount_due} was due on {cycle.due_date.strftime('%d %b %Y')}. "
        f"Please pay at the earliest. Thank you!"
    )

    # Strip any non-digit characters and assume Indian numbers if no country code given
    digits = "".join(ch for ch in tenant.phone if ch.isdigit())
    if len(digits) == 10:
        digits = "91" + digits

    wa_link = f"https://wa.me/{digits}?text={quote(message)}"

    return {"message": message, "whatsapp_link": wa_link}
