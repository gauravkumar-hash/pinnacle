import logging
from typing import Any, Optional, List, TYPE_CHECKING
import uuid
from datetime import datetime
from sqlalchemy import ARRAY, Column, ForeignKey, String, Table
from sqlalchemy.orm import relationship, Mapped, mapped_column, Session
from sqlalchemy.sql import func
from config import SGIMED_TELEMED_APPT_TYPE_ID
from utils import sg_datetime

from . import Base
from .model_enums import CollectionMethod, DocumentType, PatientType, TeleconsultStatus
from .document import Document
from .pinnacle import Service

if TYPE_CHECKING:
    from .patient import Account
    from .payments import Invoice, Payment
    from .pinnacle import PinnacleAccount, Branch
    from .delivery import TeleconsultDelivery

# The reason for the association table is because there are other tables like Appointment that would reference te documents
teleconsult_invoices_assocs = Table(
    "teleconsult_invoices",
    Base.metadata,
    Column("teleconsult_id", ForeignKey("teleconsult_queues.id"), primary_key=True),
    Column("invoice_id", ForeignKey("payment_invoices.id"), primary_key=True)
)

# The reason for the association table is because there are other tables like Appointment that would reference te documents
teleconsult_documents_assocs = Table(
    "teleconsult_documents",
    Base.metadata,
    Column("teleconsult_id", ForeignKey("teleconsult_queues.id"), primary_key=True),
    Column("document_id", ForeignKey("patient_documents.id"), primary_key=True)
)

teleconsult_payment_assocs = Table(
    "teleconsult_payments",
    Base.metadata,
    Column("teleconsult_id", ForeignKey("teleconsult_queues.id"), primary_key=True),
    Column("payment_id", ForeignKey("payment_logs.id"), primary_key=True)
)

class Teleconsult(Base):
    __tablename__ = "teleconsult_queues"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    patient_type: Mapped[PatientType]
    allergy: Mapped[Optional[str]]
    sgimed_visit_id: Mapped[Optional[str]]
    queue_number: Mapped[Optional[str]]
    queue_status: Mapped[str] = mapped_column(default="Please wait for your turn") # Queue message to be displayed to user
    address: Mapped[str]
    status: Mapped[TeleconsultStatus] = mapped_column(default=TeleconsultStatus.PREPAYMENT) # This field is instruction in SGiMed
    corporate_code: Mapped[Optional[str]]
    payment_breakdown: Mapped[list[dict[str, Any]]]
    total: Mapped[float]
    balance: Mapped[float] = mapped_column(default=0.0)
    collection_method: Mapped[Optional[CollectionMethod]]
    additional_status: Mapped[Optional[TeleconsultStatus]] # This field is to track states like "Missed"
    doctor_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("pinnacle_accounts.id"), index=True)
    branch_id: Mapped[Optional[str]] = mapped_column(ForeignKey("pinnacle_branches.id"), index=True)
    # room_id: Mapped[Optional[str]] # Zoom room id. Not needed as Zoom uses Session Name which can be set to Teleconsult ID or Queue Number
    notifications_sent: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[]) # "FIVE_BEFORE, ONE_BEFORE, SESSION_STARTED". Reset when rejoin queue is called
    teleconsult_start_time: Mapped[Optional[datetime]]
    teleconsult_join_time: Mapped[Optional[datetime]]
    teleconsult_end_time: Mapped[Optional[datetime]]
    
    checkin_time: Mapped[datetime] = mapped_column(server_default=func.now()) # This is required as this timing would be updated on two occasions: 1. When the user checks in 2. When the user is missed and rejoin queue
    checkout_time: Mapped[Optional[datetime]]
    # Used for My Family feature
    group_id: Mapped[Optional[str]]
    index: Mapped[Optional[int]]
    created_by: Mapped[Optional[str]] = mapped_column(ForeignKey("patient_accounts.id"), index=True)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    # Relationships
    account: Mapped["Account"] = relationship(back_populates="teleconsults", foreign_keys=[account_id])
    branch: Mapped["Branch"] = relationship(back_populates="teleconsults")
    doctor: Mapped["PinnacleAccount"] = relationship(back_populates="teleconsults")
    payments: Mapped[List["Payment"]] = relationship(secondary=teleconsult_payment_assocs, back_populates="teleconsults", order_by="Payment.created_at")
    invoices: Mapped[List["Invoice"]] = relationship(secondary=teleconsult_invoices_assocs, back_populates="teleconsults")
    documents: Mapped[List["Document"]] = relationship(secondary=teleconsult_documents_assocs)
    created_by_account: Mapped[Optional["Account"]] = relationship(foreign_keys=[created_by])
    teleconsult_delivery: Mapped[Optional["TeleconsultDelivery"]] = relationship(back_populates="teleconsult")

    def get_appointment_type_id(self, db: Session):
        service = db.query(Service).filter(
                Service.sgimed_branch_id == self.branch.sgimed_branch_id,
                Service.is_for_telemed == True,
            ).first()
        if not service:
            logging.error(f"Teleconsult service not found for branch: {self.branch.sgimed_branch_id}")
            return SGIMED_TELEMED_APPT_TYPE_ID
        return service.sgimed_appointment_type_id
    
    def get_successful_payments(self):
        from models.payments import PaymentStatus
        return [row for row in self.payments if row.status == PaymentStatus.PAYMENT_SUCCESS]

    def complete(self, db: Session):
        self.status = TeleconsultStatus.CHECKED_OUT
        self.checkout_time = sg_datetime.now()
        self.queue_status = "Completed"
        # Update MCs to Show
        doc = db.query(Document).filter(
                Document.sgimed_visit_id == self.sgimed_visit_id, 
                Document.document_type == DocumentType.MC
            ).first()
        if doc:
            doc.hidden = False
        self.invoices[0].show_details = True
        db.commit()

