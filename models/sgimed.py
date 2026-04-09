from datetime import date, datetime
from typing import Any, Optional
from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from . import Base

class HL7Log(Base):
    __tablename__ = "sgimed_hl7_logs"

    id: Mapped[str] = mapped_column(primary_key=True)
    vendor: Mapped[str]
    nric: Mapped[str]
    branch_id: Mapped[str]
    patient_id: Mapped[str] = mapped_column(index=True)
    report_file_id: Mapped[str] = mapped_column(index=True)
    hl7_content: Mapped[str]
    last_edited: Mapped[datetime]
    created_at: Mapped[datetime]

class IncomingReport(Base):
    __tablename__ = "sgimed_incoming_reports"

    id: Mapped[str] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(index=True)
    nric: Mapped[str]
    vendor: Mapped[str]
    status: Mapped[str]
    branch_id: Mapped[str] = mapped_column(index=True)
    visit_id: Mapped[str]
    file_name: Mapped[str]
    report_file_id: Mapped[str] = mapped_column(index=True)
    file_date: Mapped[datetime]
    info_json: Mapped[str]
    last_edited: Mapped[datetime]
    health_report_generated: Mapped[bool | None]

class Measurement(Base):
    __tablename__ = "sgimed_measurements"

    id: Mapped[str] = mapped_column(primary_key=True)
    branch_id: Mapped[str]
    patient_id: Mapped[str] = mapped_column(index=True)
    type_name: Mapped[str]
    type_unit: Mapped[str]
    value: Mapped[str]
    measurement_date: Mapped[datetime] = mapped_column(index=True)
    last_edited: Mapped[datetime]
    created_at: Mapped[datetime]


class SGiMedInventory(Base):
    __tablename__ = "sgimed_inventory"

    id: Mapped[str] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    type: Mapped[str]  # Service, Drugs, Lab
    remark: Mapped[str | None]
    is_stock_tracked: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[Optional[float]] = mapped_column(default=None)
    inventory_json: Mapped[Optional[dict[str, Any]]] = mapped_column(default=None)
    last_edited: Mapped[datetime]
    created_at: Mapped[datetime]
    category_id: Mapped[str]

class SGiMedAppointmentType(Base):
    __tablename__ = "sgimed_appointment_types"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str]
    branch_id: Mapped[str]
    sort_key: Mapped[int]
    is_enabled: Mapped[bool]
    is_for_visit: Mapped[bool]
    is_for_appointment: Mapped[bool]
    is_block_type: Mapped[bool]
    last_edited: Mapped[datetime]
    created_at: Mapped[datetime]

class SGiMedInvoiceRefund(Base):
    '''
    Note: This is a table tracked from sgimed_updates.py:check_for_refunds()
    '''
    __tablename__ = "sgimed_invoice_refunds"

    sgimed_invoice_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    invoice_date: Mapped[date]
    refund_amount: Mapped[float]
    include_delivery_charges: Mapped[bool] = mapped_column(Boolean, default=False)
    sgimed_invoice_payment_items: Mapped[list[dict[str, Any]]]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
