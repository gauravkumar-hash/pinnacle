from __future__ import annotations
from sqlalchemy import Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime
from .base import Base

if TYPE_CHECKING:
    from .specialisation import Specialisation
    from .appointment_request import AppointmentRequest


class Specialist(Base):
    __tablename__ = "specialists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialisation_id: Mapped[int] = mapped_column(Integer,
        ForeignKey("specialisations.id"), nullable=False)
    
    title: Mapped[Optional[str]] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String)
    credentials: Mapped[Optional[str]] = mapped_column(String)
    short_bio: Mapped[Optional[str]] = mapped_column(String)
    full_bio: Mapped[Optional[str]] = mapped_column(String)
    languages: Mapped[Optional[str]] = mapped_column(String)
    appointment_email: Mapped[str] = mapped_column(String, nullable=False)
    contact_email: Mapped[Optional[str]] = mapped_column(String)
    contact_phone: Mapped[Optional[str]] = mapped_column(String)
    available_days: Mapped[Optional[str]] = mapped_column(String)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    # relationships
    specialisation: Mapped[Specialisation] = relationship(
        "Specialisation", back_populates="specialists"
    )
    requests: Mapped[List[AppointmentRequest]] = relationship(
        "AppointmentRequest", back_populates="specialist"
    )