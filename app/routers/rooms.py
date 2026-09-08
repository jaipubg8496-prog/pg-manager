import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.auth.dependencies import require_active_subscription as get_current_owner
from app.routers.properties import _get_owned_property

router = APIRouter(tags=["rooms"])


def _get_owned_room(room_id: int, owner: models.Owner, db: Session) -> models.Room:
    room = (
        db.query(models.Room)
        .join(models.Property)
        .filter(models.Room.id == room_id, models.Property.owner_id == owner.id)
        .first()
    )
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


def _get_owned_bed(bed_id: int, owner: models.Owner, db: Session) -> models.Bed:
    bed = (
        db.query(models.Bed)
        .join(models.Room)
        .join(models.Property)
        .filter(models.Bed.id == bed_id, models.Property.owner_id == owner.id)
        .first()
    )
    if not bed:
        raise HTTPException(status_code=404, detail="Bed not found")
    return bed


@router.get("/api/properties/{property_id}/rooms", response_model=list[schemas.RoomOut])
def list_rooms(
    property_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    _get_owned_property(property_id, current_owner, db)  # ownership check
    return db.query(models.Room).filter(models.Room.property_id == property_id).order_by(models.Room.room_number).all()


@router.post("/api/properties/{property_id}/rooms", response_model=schemas.RoomOut, status_code=201)
def create_room(
    property_id: int,
    payload: schemas.RoomCreate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    _get_owned_property(property_id, current_owner, db)  # ownership check

    room = models.Room(
        property_id=property_id,
        room_number=payload.room_number,
        room_type=payload.room_type,
        monthly_rent=payload.monthly_rent,
    )
    db.add(room)
    db.flush()  # get room.id before commit, so we can attach beds

    # Auto-create beds labeled A, B, C... based on num_beds (convenience for MVP)
    labels = string.ascii_uppercase
    for i in range(payload.num_beds):
        label = labels[i] if i < len(labels) else str(i + 1)
        db.add(models.Bed(room_id=room.id, bed_label=label, status="vacant"))

    db.commit()
    db.refresh(room)
    return room


@router.put("/api/rooms/{room_id}", response_model=schemas.RoomOut)
def update_room(
    room_id: int,
    payload: schemas.RoomUpdate,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    room = _get_owned_room(room_id, current_owner, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return room


@router.delete("/api/rooms/{room_id}", status_code=204)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    room = _get_owned_room(room_id, current_owner, db)

    occupied = any(bed.status == "occupied" for bed in room.beds)
    if occupied:
        raise HTTPException(
            status_code=400,
            detail="Can't delete a room with an active tenant in it. Move the tenant out first.",
        )

    db.delete(room)  # cascades to beds
    db.commit()
    return None


@router.post("/api/rooms/{room_id}/beds", response_model=schemas.BedOut, status_code=201)
def add_bed(
    room_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    """Adds one more bed to an existing room, auto-labeling it the next letter."""
    room = _get_owned_room(room_id, current_owner, db)

    labels = string.ascii_uppercase
    used_labels = {b.bed_label for b in room.beds}
    next_label = next((l for l in labels if l not in used_labels), str(len(room.beds) + 1))

    bed = models.Bed(room_id=room.id, bed_label=next_label, status="vacant")
    db.add(bed)
    db.commit()
    db.refresh(bed)
    return bed


@router.delete("/api/beds/{bed_id}", status_code=204)
def delete_bed(
    bed_id: int,
    db: Session = Depends(get_db),
    current_owner: models.Owner = Depends(get_current_owner),
):
    bed = _get_owned_bed(bed_id, current_owner, db)
    if bed.status == "occupied":
        raise HTTPException(status_code=400, detail="Can't delete an occupied bed. Move the tenant out first.")
    db.delete(bed)
    db.commit()
    return None
