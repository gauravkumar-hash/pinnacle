from typing import Any, Optional, List, TYPE_CHECKING
from datetime import datetime, time
import uuid
from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, String, Float, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column, backref
from sqlalchemy.sql import func
from models.model_enums import AppointmentServiceGroupType, AppointmentStatus, DayOfWeek, AppointmentCategory
from pydantic import BaseModel
from . import Base

if TYPE_CHECKING:
    from .patient import Account
    from .sgimed import SGiMedInventory

class AppointmentAuditLog(Base):
    __tablename__ = "appointment_audit_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sgimed_appointment_id: Mapped[str]
    sgimed_payload: Mapped[dict[str, Any]]
    source: Mapped[str] # sgimed, patient
    action: Mapped[str] # reschedule, cancel, delete
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class SGiMedAppointment(Base):
    '''
    Create/Update from backend-patient-app/scheduler_actions/sgimed_appointment_updates.py
    Delete from backend-patient-app/routers/patient/actions/appointment.py
    '''
    __tablename__ = "sgimed_appointments"

    id: Mapped[str] = mapped_column(primary_key=True)
    subject: Mapped[str]
    patient_id: Mapped[Optional[str]] # When it is guest appointment, patient_id is null
    calendar_id: Mapped[str] # calendars[0].id
    branch_id: Mapped[str]
    is_all_day: Mapped[bool]
    appointment_type_id: Mapped[str] # appointment_type.id
    is_informed: Mapped[bool]
    is_queued: Mapped[bool]
    is_cancelled: Mapped[bool]
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True)) # f"{start_date[:11]}{start_time}{start_date[19:]}"
    end_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True)) # f"{end_date[:11]}{end_time}{end_date[19:]}"
    confirm_time: Mapped[Optional[datetime]]
    confirm_user: Mapped[Optional[str]]
    is_confirmed: Mapped[bool]

    last_edited: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Seems to always be null but relevant to apply to appointment prepayment
    # "confirm_time": null,
    # "confirm_user": null,
    # "is_confirmed": false,

class AppointmentCount(Base):
    __tablename__ = "appointment_counts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sgimed_branch_id: Mapped[str] = mapped_column(index=True)
    sgimed_calendar_id: Mapped[str] = mapped_column(index=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    count: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Appointment(Base):
    __tablename__ = "patient_appointments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Appointment ID - Optional during Prepayment
    sgimed_appointment_id: Mapped[Optional[str]]
    corporate_code: Mapped[Optional[str]] # Code keyed in by user
    affiliate_code: Mapped[Optional[str]] # Code from deeplink
    # Services: [{"id": "<service_group_id>", "name": "<title>", "icon": "<icon url>", "items": [{"id": "<service_id>", "name": "<service_name>"}]}]
    services: Mapped[list[dict[str, Any]]]
    # Existing Account or Guest
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    # Guests: [{"name": "<name>", "mobile": "<mobile>"}]
    guests: Mapped[Optional[list[dict[str, Any]]]]
    # Branch: { "id": "<branch_id>", "name": "<branch_name>", "address": "<address>", "url": "<url>" }
    branch: Mapped[dict[str, Any]]
    # Date and time information
    start_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration: Mapped[int] # Duration in minutes
    # Survey
    patient_survey: Mapped[Optional[dict[str, Any]]]
    corporate_survey: Mapped[Optional[dict[str, Any]]]
    # Payment information
    payment_breakdown: Mapped[dict[str, Any]]
    payment_ids: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    invoice_ids: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    # Status information
    status: Mapped[AppointmentStatus]
    # Used to group appointments based on family
    group_id: Mapped[Optional[str]] = mapped_column(index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"))
    index: Mapped[Optional[int]]
    notifications_sent: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    account: Mapped["Account"] = relationship("Account", foreign_keys=[account_id], backref="appointments")
    created_by_account: Mapped["Account"] = relationship("Account", foreign_keys=[created_by], backref="created_appointments")

    def get_services(self):
        return [ServiceGroupCol.model_validate(service_group) for service_group in self.services]

    def get_guests(self):
        if not self.guests:
            return None
        return [GuestCol.model_validate(guest) for guest in self.guests]

    def get_branch(self):
        return BranchCol.model_validate(self.branch)

    def get_payment_breakdown(self):
        return PaymentBreakdownCol.model_validate(self.payment_breakdown)

class AppointmentServiceGroup(Base):
    __tablename__ = "appointment_service_groups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    title: Mapped[Optional[str]] # Additional title for the service group screen
    description: Mapped[Optional[str]]
    index: Mapped[int]
    icon: Mapped[str]
    duration: Mapped[int] = mapped_column(Integer)  # Duration in minutes
    type: Mapped[AppointmentServiceGroupType]
    services: Mapped[List["AppointmentService"]] = relationship("AppointmentService", back_populates="group")
    restricted_branches: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    unsupported_branches: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    restricted_memberships: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])

    corporate_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("appointment_corporate_codes.id"))
    corporate_code: Mapped["AppointmentCorporateCode"] = relationship(back_populates="appointment_service_groups")

    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    category: Mapped[AppointmentCategory] = mapped_column(default=AppointmentCategory.GENERAL)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AppointmentCorporateCode(Base):
    __tablename__ = "appointment_corporate_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String, unique=True)
    organization: Mapped[str]
    patient_survey: Mapped[dict[str, Any]]
    corporate_survey: Mapped[dict[str, Any]]
    only_primary_user: Mapped[bool] = mapped_column(Boolean, default=False) # Indicate no dependants can be used added
    # Validity period
    valid_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[AppointmentCategory] = mapped_column(default=AppointmentCategory.GENERAL)

    appointment_service_groups: Mapped[List["AppointmentServiceGroup"]] = relationship(back_populates="corporate_code")
    appointment_onsite_branches: Mapped[List["AppointmentOnsiteBranch"]] = relationship(back_populates="corporate_code")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AppointmentService(Base):
    __tablename__ = "appointment_services"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sgimed_inventory_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sgimed_inventory.id"))
    name: Mapped[str]
    prepayment_price: Mapped[float] = mapped_column(Float, default=0.0) # Price needed for prepayment
    display_price: Mapped[float] = mapped_column(Float, default=0.0) # Price displayed to the user prepayment_price <= display_price
    index: Mapped[int]
    min_booking_ahead_days: Mapped[int] = mapped_column(Integer, default=2)
    # Group relationship
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("appointment_service_groups.id"))
    group: Mapped["AppointmentServiceGroup"] = relationship("AppointmentServiceGroup", back_populates="services")
    restricted_branches: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    unsupported_branches: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    # Tests related to this service
    tests: Mapped[Optional[list[dict[str, Any]]]] # [{ "name": str, "exclusion": str }]

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sgimed_inventory: Mapped["SGiMedInventory"] = relationship("SGiMedInventory", foreign_keys=[sgimed_inventory_id], backref="appointment_services")

class AppointmentOnsiteBranch(Base):
    __tablename__ = "appointment_onsite_branches"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    branch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pinnacle_branches.id"))
    # branch: Mapped["Branch"] = relationship("Branch", back_populates="onsite_branches")

    corporate_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("appointment_corporate_codes.id"))
    corporate_code: Mapped["AppointmentCorporateCode"] = relationship(back_populates="appointment_onsite_branches")

    header: Mapped[Optional[str]]
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[AppointmentCategory] = mapped_column(default=AppointmentCategory.GENERAL)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class AppointmentBranchOperatingHours(Base):
    __tablename__ = "appointment_operating_hours"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    day: Mapped[DayOfWeek]
    start_time: Mapped[time]
    end_time: Mapped[time]
    cutoff_time: Mapped[int] = mapped_column(default=0)
    max_bookings: Mapped[int] = mapped_column(Integer, default=1)
    # Branch relationship
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("pinnacle_branches.id"))
    # branch: Mapped["Branch"] = relationship("Branch", back_populates="operating_hours")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# Pydantic Models to support Apppointment
class ServiceItemCol(BaseModel):
    id: str
    name: str
    prepayment_price: float
    display_price: float

class ServiceGroupCol(BaseModel):
    id: str
    name: str
    items: list[ServiceItemCol]

class BranchCol(BaseModel):
    id: str
    sgimed_branch_id: str
    sgimed_appointment_type_id: str
    name: str
    address: str
    url: str

class GuestCol(BaseModel):
    name: str
    mobile: str
    sgimed_appointment_id: str | None = None

class PaymentBreakdownItemCol(BaseModel):
    title: str
    amount: float

class PaymentBreakdownCol(BaseModel):
    items: list[PaymentBreakdownItemCol]
    gst: float
    total: float
