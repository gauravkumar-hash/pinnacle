from typing import Any, Optional, List, TYPE_CHECKING
from enum import Enum
import uuid
from datetime import datetime
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from .model_enums import VisitType
from . import Base
from .teleconsult import teleconsult_payment_assocs, teleconsult_invoices_assocs

if TYPE_CHECKING:
    from .teleconsult import Teleconsult
    from .patient import Account

class PaymentProvider(Enum):
    APP_STRIPE = 'APP_STRIPE'
    APP_NETS_CLICK = 'APP_NETS_CLICK'
    APP_2C2P = 'APP_2C2P'

class PaymentMethod(Enum):
    NETS_CLICK = 'nets_click'
    CARD_STRIPE = 'card_stripe'
    CARD_SGIMED = 'card_sgimed'
    CARD_2C2P = 'card_2c2p'
    PAYNOW_NETS = 'paynow_nets'
    PAYNOW_STRIPE = 'paynow_stripe'
    PAYNOW_2C2P = 'paynow_2c2p'
    DEFERRED_PAYMENT = 'deferred_payment'

class PaymentStatus(Enum):
    PAYMENT_CREATED = 'payment_created'
    PAYMENT_CANCELED = 'payment_canceled'
    PAYMENT_EXPIRED = 'payment_expired'
    PAYMENT_FAILED = 'payment_failed'
    PAYMENT_SUCCESS = 'payment_success'

class PaymentType(Enum):
    PREPAYMENT = 'prepayment'
    POSTPAYMENT = 'postpayment'
    APPOINTMENT = 'appointment'
    TOKENIZATION = 'tokenization'

class PaymentMode(Base):
    __tablename__ = "pinnacle_payment_modes"
    
    id: Mapped[PaymentProvider] = mapped_column(primary_key=True) # Payment provider
    sgimed_payment_mode_id: Mapped[str] # SGiMed payment_mode_id
    name: Mapped[str] # Name of the payment mode

class Payment(Base):
    __tablename__ = "payment_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    payment_id: Mapped[str] # ID provided by payment provider
    account_id: Mapped[str] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    payment_breakdown: Mapped[list[dict[str, Any]]]
    payment_type: Mapped[PaymentType]
    payment_method: Mapped[PaymentMethod]
    payment_amount: Mapped[float]
    payment_provider: Mapped[Optional[PaymentProvider]]
    status: Mapped[PaymentStatus]
    remarks: Mapped[Optional[dict[str, Any]]]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    account: Mapped["Account"] = relationship(back_populates="payments")
    teleconsults: Mapped[List["Teleconsult"]] = relationship(secondary=teleconsult_payment_assocs, back_populates="payments")
    # Foreign Key without constraints: https://stackoverflow.com/a/37809175/6944050
    payment_mode: Mapped["PaymentMode"] = relationship('PaymentMode', primaryjoin='foreign(Payment.payment_provider) == PaymentMode.id')

class PaymentReconciliation(Base):
    __tablename__ = "payment_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(unique=True)
    completed_at: Mapped[datetime] = mapped_column(index=True)
    branch: Mapped[str]
    patients: Mapped[list[str]]
    sgimed_visit_id: Mapped[list[str]]    
    payment_type: Mapped[PaymentType]
    payment_provider: Mapped[PaymentProvider]
    payment_method: Mapped[PaymentMethod]
    payment_amount: Mapped[float]
    payment_amount_nett: Mapped[float]
    payment_platform_fees: Mapped[str]

class Invoice(Base):
    __tablename__ = "payment_invoices"

    id: Mapped[str] = mapped_column(primary_key=True) # This is mapped to SGiMed invoice_id
    visit_type: Mapped[VisitType]
    account_id: Mapped[str] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    amount: Mapped[float]
    invoice_html: Mapped[str]
    mc_html: Mapped[Optional[str]]
    items: Mapped[list[dict[str, Any]]] # This is the breakdown of the invoice
    prescriptions: Mapped[list[dict[str, Any]]]
    hide_invoice: Mapped[bool] = mapped_column(server_default='false')
    # This is flag to prevent access prior to postpayment
    show_details: Mapped[bool] = mapped_column(server_default='false')
    sgimed_last_edited: Mapped[str]
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    account: Mapped["Account"] = relationship(back_populates="invoices")
    teleconsults: Mapped[List["Teleconsult"]] = relationship(secondary=teleconsult_invoices_assocs, back_populates="invoices")
    
class DynamicPricing(Base):
    __tablename__ = 'payment_dynamic_rates'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[str]
    timing: Mapped[str]
    # corporate_codes JSON column ({ "payment_corporate_codes.id": [ <sgimed_consultation_item_ids> ]})
    corporate_codes: Mapped[dict[str, Any]] = mapped_column(default={})
    sgimed_consultation_inventory_ids: Mapped[list[str]] = mapped_column(default=[])
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

class CorporateCode(Base):
    __tablename__ = 'payment_corporate_codes'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(index=True, unique=True)
    deleted: Mapped[bool] = mapped_column(server_default='false')
    # Only these inputs can be user entered.
    allow_user_input: Mapped[bool] = mapped_column(server_default='false') # This flag determines if a user to key in this promo code. (e.g. SA Rate)
    remarks: Mapped[Optional[str]]
    # Null uses dynamic rates
    skip_prepayment: Mapped[bool] = mapped_column(server_default='false')
    hide_invoice: Mapped[bool] = mapped_column(server_default='false')
    sgimed_consultation_inventory_ids: Mapped[list[str]] = mapped_column(default=[])
    priority_index: Mapped[int] = mapped_column(server_default='100', index=True)  # Lower number = higher priority
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

class PaymentToken(Base):
    __tablename__ = 'payment_tokens'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[str] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    provider: Mapped[PaymentProvider]
    method: Mapped[PaymentMethod]
    token: Mapped[str]
    details: Mapped[dict[str, Any]]
    deleted: Mapped[bool] = mapped_column(server_default='false')
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    account: Mapped["Account"] = relationship(back_populates="payment_tokens")
    
class PaymentTransaction(Base):
    __tablename__ = 'payment_transactions'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    provider: Mapped[PaymentProvider]
    invoice_num: Mapped[Optional[str]]
    type: Mapped[PaymentType]
    endpoint: Mapped[str]
    request: Mapped[dict[str, Any]]
    response: Mapped[dict[str, Any]]
    webhook: Mapped[dict[str, Any]]
    status: Mapped[PaymentStatus] = mapped_column(default=PaymentStatus.PAYMENT_FAILED)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
