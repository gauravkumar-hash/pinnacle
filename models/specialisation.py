from __future__ import annotations
from sqlalchemy import Integer, String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING, Optional, List
from datetime import datetime
from . import Base

if TYPE_CHECKING:
    from .specialist import Specialist
    from .appointment_request import AppointmentRequest


class Specialisation(Base):
    __tablename__ = "specialisations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String)
    icon_url: Mapped[Optional[str]] = mapped_column(String)
    banner_url: Mapped[Optional[str]] = mapped_column(String)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=datetime.utcnow)

    # relationships
    specialists: Mapped[List[Specialist]] = relationship(
        "Specialist", back_populates="specialisation"
    )
    requests: Mapped[List[AppointmentRequest]] = relationship(
        "AppointmentRequest", back_populates="specialisation"
    )
