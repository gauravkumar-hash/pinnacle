from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from . import Base

class CronLog(Base):
    __tablename__ = "backend_crons"

    id: Mapped[str] = mapped_column(primary_key=True)
    last_modified: Mapped[datetime]
    last_page: Mapped[Optional[int]]

class NotificationLog(Base):
    __tablename__ = "backend_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    title: Mapped[str]
    message: Mapped[str]

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # account: Mapped["Account"] = relationship(back_populates="teleconsults", foreign_keys=[account_id])
    
class SystemConfig(Base):
    __tablename__ = "backend_configs"
    
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]
    value_type: Mapped[str]  # "string", "boolean", "integer", "float", "json"
    description: Mapped[Optional[str]]
    category: Mapped[str]  # For grouping related configs
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
