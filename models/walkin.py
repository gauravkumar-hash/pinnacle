import logging
from sqlalchemy import String, ForeignKey, Table, Column
from sqlalchemy.orm import relationship, Mapped, mapped_column, Session, joinedload
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
import uuid
from sqlalchemy.dialects.postgresql import ARRAY

from models.pinnacle import Service
from .model_enums import WalkinQueueStatus
from . import Base
from .document import Document

if TYPE_CHECKING:
    from .patient import Account
    from .payments import Invoice
    from .pinnacle import Branch
    
# # The reason for the association table is because there are other tables like Appointment that would reference te documents
walkin_invoices_assocs = Table(
    "walkin_invoices",
    Base.metadata,
    Column("walkin_id", ForeignKey("walkin_queues.id"), primary_key=True),
    Column("invoice_id", ForeignKey("payment_invoices.id"), primary_key=True)
)

# # The reason for the association table is because there are other tables like Appointment that would reference te documents
walkin_documents_assocs = Table(
    "walkin_documents",
    Base.metadata,
    Column("walkin_id", ForeignKey("walkin_queues.id"), primary_key=True),
    Column("document_id", ForeignKey("patient_documents.id"), primary_key=True)
)

walkin_payment_assocs = Table(
    "walkin_payments",
    Base.metadata,
    Column("walkin_id", ForeignKey("walkin_queues.id"), primary_key=True),
    Column("payment_id", ForeignKey("payment_logs.id"), primary_key=True),
)

class WalkInQueue(Base):
    __tablename__ = 'walkin_queues'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    branch_id: Mapped[str] = mapped_column(ForeignKey('pinnacle_branches.id'), index=True)
    
    # TODO: Add in patient foreign key with firebase id
    # patient_id: Mapped[String] = mapped_column(ForeignKey("....."), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    queue_number: Mapped[Optional[str]]
    sgimed_pending_queue_id: Mapped[str]
    sgimed_visit_id: Mapped[Optional[str]]
    service: Mapped[str]
    queue_status: Mapped[str]
    checkin_time: Mapped[Optional[datetime]]
    checkout_time: Mapped[Optional[datetime]]
    status: Mapped[WalkinQueueStatus] = mapped_column(default=WalkinQueueStatus.PENDING)
    notifications_sent: Mapped[list[str]] = mapped_column(ARRAY(String, dimensions=1), default=[])
    remarks: Mapped[Optional[str]]   
    # Used for My Family feature
    group_id: Mapped[Optional[str]]
    index: Mapped[Optional[int]]
    created_by: Mapped[Optional[str]] = mapped_column(ForeignKey("patient_accounts.id"), index=True)
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    # Relationships
    account: Mapped["Account"] = relationship(back_populates="walkins", foreign_keys=[account_id])
    branch: Mapped["Branch"] = relationship("Branch", back_populates="walkin_queues")
    # payments: Mapped[List["Payment"]] = relationship(secondary=walkin_payment_assocs, back_populates="teleconsults")
    invoices: Mapped[List["Invoice"]] = relationship(secondary=walkin_invoices_assocs)
    documents: Mapped[List["Document"]] = relationship(secondary=walkin_documents_assocs)
    created_by_account: Mapped[Optional["Account"]] = relationship(foreign_keys=[created_by])
    
    def get_sgimed_appointment_type_id(self, db: Session):
        service = db.query(Service.sgimed_appointment_type_id) \
            .filter(
                Service.label == self.service, 
                Service.sgimed_branch_id == self.branch.sgimed_branch_id
            ).first()
        if not service:
            logging.error(f"get_service_id: Service not found for branch {self.branch.id} and service {self.service}")
            return ''
        return service[0]
