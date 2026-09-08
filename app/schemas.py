from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict


# ---------- Auth ----------

class OwnerSignup(BaseModel):
    name: str
    email: EmailStr
    phone: str
    password: str


class OwnerLogin(BaseModel):
    email: EmailStr
    password: str


class OwnerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    phone: str
    subscription_status: str


class OwnerProfileUpdate(BaseModel):
    name: str
    phone: str


class GoogleLoginRequest(BaseModel):
    credential: str  # the ID token Google's Identity Services library hands back


class GoogleClientIdOut(BaseModel):
    google_client_id: str
    enabled: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- Property ----------

class PropertyCreate(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None


class PropertyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    address: Optional[str]
    city: Optional[str]


# ---------- Room & Bed ----------

class RoomCreate(BaseModel):
    room_number: str
    room_type: Optional[str] = None
    monthly_rent: Decimal
    num_beds: int = 1  # convenience: auto-create this many beds (A, B, C...)


class RoomUpdate(BaseModel):
    room_number: Optional[str] = None
    room_type: Optional[str] = None
    monthly_rent: Optional[Decimal] = None


class BedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    bed_label: Optional[str]
    status: str


class RoomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    room_number: str
    room_type: Optional[str]
    monthly_rent: Decimal
    beds: list[BedOut] = []


# ---------- Tenant ----------

class TenantCreate(BaseModel):
    bed_id: int
    name: str
    phone: str
    id_proof_type: Optional[str] = None
    id_proof_number: Optional[str] = None
    move_in_date: date
    monthly_rent: Decimal


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    id_proof_type: Optional[str] = None
    id_proof_number: Optional[str] = None
    monthly_rent: Optional[Decimal] = None


class TenantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    phone: str
    move_in_date: Optional[date]
    move_out_date: Optional[date]
    monthly_rent: Decimal
    status: str
    bed_id: Optional[int]


class TenantMoveOut(BaseModel):
    move_out_date: date


# ---------- Rent Cycle ----------

class RentCycleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    due_date: date
    amount_due: Decimal
    amount_paid: Decimal
    status: str
    paid_on: Optional[date]


class MarkPaidRequest(BaseModel):
    amount_paid: Decimal
    paid_on: Optional[date] = None


# ---------- Billing ----------

class SubscriptionStatus(BaseModel):
    is_active: bool
    status: str  # "trial" | "active" | "expired"
    trial_ends_at: Optional[datetime] = None
    subscription_active_until: Optional[datetime] = None
    days_left: int
    price_rupees: int


class RazorpayOrderOut(BaseModel):
    order_id: str
    amount_paise: int
    currency: str = "INR"
    key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ---------- Complaint ----------

class ComplaintCreate(BaseModel):
    tenant_id: int
    description: str


class ComplaintUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None  # "open" or "resolved"


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: int
    description: str
    status: str
    created_at: datetime
