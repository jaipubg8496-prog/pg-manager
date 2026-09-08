from datetime import datetime, date

from sqlalchemy import (
    Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import relationship

from app.database import Base


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    phone = Column(String(15), nullable=False)
    password_hash = Column(String(255), nullable=True)  # null for Google-only accounts
    google_sub = Column(String(255), nullable=True, unique=True, index=True)  # Google's stable user id
    subscription_status = Column(String(20), default="trial")  # trial, active, expired — informational only
    created_at = Column(DateTime, default=datetime.utcnow)

    # Source of truth for access control (see app/auth/dependencies.py):
    # trial_ends_at is set once at signup. subscription_active_until is pushed
    # forward by 30 days every time a payment is verified. Access is allowed
    # if either window is still in the future.
    trial_ends_at = Column(DateTime, nullable=True)
    subscription_active_until = Column(DateTime, nullable=True)

    properties = relationship("Property", back_populates="owner", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="owner", cascade="all, delete-orphan")


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    address = Column(Text)
    city = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("Owner", back_populates="properties")
    rooms = relationship("Room", back_populates="property", cascade="all, delete-orphan")
    tenants = relationship("Tenant", back_populates="property", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    room_number = Column(String(20), nullable=False)
    room_type = Column(String(20))  # single, double, triple, dorm
    monthly_rent = Column(Numeric(10, 2), nullable=False)

    property = relationship("Property", back_populates="rooms")
    beds = relationship("Bed", back_populates="room", cascade="all, delete-orphan")


class Bed(Base):
    __tablename__ = "beds"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    bed_label = Column(String(10))  # A, B, C
    status = Column(String(20), default="vacant")  # vacant, occupied

    room = relationship("Room", back_populates="beds")
    tenant = relationship("Tenant", back_populates="bed", uselist=False)


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    bed_id = Column(Integer, ForeignKey("beds.id"), nullable=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(15), nullable=False)
    id_proof_type = Column(String(30))
    id_proof_number = Column(String(50))
    move_in_date = Column(Date)
    move_out_date = Column(Date, nullable=True)
    monthly_rent = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="active")  # active, moved_out

    property = relationship("Property", back_populates="tenants")
    bed = relationship("Bed", back_populates="tenant")
    rent_cycles = relationship("RentCycle", back_populates="tenant", cascade="all, delete-orphan")
    complaints = relationship("Complaint", back_populates="tenant", cascade="all, delete-orphan")


class RentCycle(Base):
    __tablename__ = "rent_cycles"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    due_date = Column(Date, nullable=False)
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), default=0)
    status = Column(String(20), default="pending")  # pending, paid, partial, overdue
    paid_on = Column(Date, nullable=True)

    tenant = relationship("Tenant", back_populates="rent_cycles")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(20), default="open")  # open, resolved
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="complaints")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id", ondelete="CASCADE"), nullable=False)
    razorpay_order_id = Column(String(64), nullable=False)
    razorpay_payment_id = Column(String(64), nullable=True)
    amount_rupees = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), default="created")  # created, paid, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)

    owner = relationship("Owner", back_populates="payments")
