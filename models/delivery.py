from typing import Any, Optional, TYPE_CHECKING
from datetime import datetime, date
import uuid
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from enum import Enum
from . import Base

if TYPE_CHECKING:
    from .teleconsult import Teleconsult
    from .patient import Account
    from .pinnacle import PinnacleAccount

class DeliveryStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"
    NO_DELIVERY_SERVICE = "no_delivery_service"

class DeliveryZone(Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    CENTRAL = "central"
    UNKNOWN = "unknown"

class TeleconsultDelivery(Base):
    __tablename__ = "teleconsult_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    teleconsult_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teleconsult_queues.id"), index=True
    )
    zone: Mapped[DeliveryZone]
    address: Mapped[str]
    postal: Mapped[str]
    status: Mapped[DeliveryStatus] = mapped_column(default=DeliveryStatus.PENDING)
    dispatch_history: Mapped[list[dict[str, Any]]] = mapped_column(server_default="[]")
    is_migrant: Mapped[bool]
    number_of_packages: Mapped[Optional[int]]
    delivery_date: Mapped[Optional[date]]
    delivery_attempt: Mapped[int] = mapped_column(default=1)
    recipient_name: Mapped[Optional[str]]
    receipt_date: Mapped[Optional[datetime]]
    is_delivery_note_exists: Mapped[bool] = mapped_column(server_default="false")
    delivery_note_file_path: Mapped[Optional[str]]
    group_id: Mapped[Optional[str]] # Used for family feature
    # Foreign Keys stored
    dispatch_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("pinnacle_accounts.id"), index=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    patient_account: Mapped["Account"] = relationship(back_populates="teleconsult_deliveries", foreign_keys=[patient_id])
    clinic_account: Mapped["PinnacleAccount"] = relationship(back_populates="teleconsult_deliveries", foreign_keys=[dispatch_id])
    teleconsult: Mapped["Teleconsult"] = relationship(back_populates="teleconsult_delivery")

class PinnacleZone(Base):
    __tablename__ = "teleconsult_delivery_zones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sector_code: Mapped[str] = mapped_column(unique=True, index=True)
    zone: Mapped[DeliveryZone] = mapped_column(default=DeliveryZone.UNKNOWN)
    has_service: Mapped[bool] = mapped_column(server_default="true")
    is_migrant_area: Mapped[bool] = mapped_column(server_default="false")

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
