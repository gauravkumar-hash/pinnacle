from __future__ import annotations
from sqlalchemy import Integer, String, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from datetime import date, datetime
from utils import sg_datetime
from . import Base

if TYPE_CHECKING:
    from .specialisation import Specialisation


class ClinicService(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialisation_id: Mapped[int] = mapped_column(Integer, ForeignKey("specialisations.id", ondelete="CASCADE"), nullable=False)
    
    service_name: Mapped[str] = mapped_column(String, nullable=False)
    clinic_name: Mapped[str] = mapped_column(String, nullable=False)
    consultation_fee: Mapped[Optional[str]] = mapped_column(String)
    clinic_photo_path: Mapped[Optional[str]] = mapped_column(String)
    banner_image_path: Mapped[Optional[str]] = mapped_column(String)
    
    bio: Mapped[Optional[str]] = mapped_column(String)
    service_details: Mapped[Optional[str]] = mapped_column(String)
    languages: Mapped[Optional[str]] = mapped_column(String)
    years_of_practice: Mapped[Optional[int]] = mapped_column(Integer)
    hospital_affiliations: Mapped[Optional[str]] = mapped_column(String)
    board_certifications: Mapped[Optional[str]] = mapped_column(String)
    awards: Mapped[Optional[str]] = mapped_column(String)
    insurance_tpa: Mapped[Optional[str]] = mapped_column(String)
    insurance_shield_plan: Mapped[Optional[str]] = mapped_column(String)
    
    contact_name: Mapped[Optional[str]] = mapped_column(String)
    contact_email: Mapped[Optional[str]] = mapped_column(String)
    contact_phone: Mapped[Optional[str]] = mapped_column(String)
    cc_emails: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    available_days: Mapped[Optional[str]] = mapped_column(String)
    available_time_slots: Mapped[Optional[str]] = mapped_column(String)
    day_availability: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    # ISO "YYYY-MM-DD" dates on which the service is temporarily unavailable.
    # Unlike active=False, a blocked date only hides bookability for that date.
    blocked_dates: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)

    def is_blocked_on(self, day: date) -> bool:
        return bool(self.blocked_dates) and day.isoformat() in self.blocked_dates

    @property
    def blocked_today(self) -> bool:
        return self.is_blocked_on(sg_datetime.now().date())

    # timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    # relationships
    specialisation: Mapped[Specialisation] = relationship("Specialisation", back_populates="services")
