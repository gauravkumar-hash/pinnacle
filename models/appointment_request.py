from __future__ import annotations
from sqlalchemy import Integer, String, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional
from datetime import datetime
import enum
from . import Base

if TYPE_CHECKING:
    from .specialisation import Specialisation
    from .specialist import Specialist


class RequestStatus(enum.Enum):
    PENDING   = "pending"
    CONFIRMED = "confirmed"
    REJECTED  = "rejected"
    COMPLETED = "completed"


class AppointmentRequest(Base):
    __tablename__ = "appointment_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialisation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specialisations.id"), nullable=False
    )
    specialist_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("specialists.id"), nullable=False
    )
    patient_name: Mapped[str] = mapped_column(String, nullable=False)
    patient_dob: Mapped[Optional[str]] = mapped_column(String)
    contact_number: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    preferred_days: Mapped[Optional[str]] = mapped_column(String)
    preferred_time: Mapped[Optional[str]] = mapped_column(String)
    reason: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.PENDING, nullable=False
    )
    status_message: Mapped[Optional[str]] = mapped_column(String)

    # timestamps
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    # relationships
    specialisation: Mapped[Specialisation] = relationship(
        "Specialisation", back_populates="requests"

    )
    specialist: Mapped[Specialist] = relationship(
        "Specialist", back_populates="requests"
    )