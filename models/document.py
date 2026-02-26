from typing import Optional, TYPE_CHECKING
import os.path as osp
import uuid
from datetime import datetime, date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from .model_enums import DocumentType, FileViewerType, DocumentStatus
from . import Base

if TYPE_CHECKING:
    from .patient import Account
    from .pinnacle import Branch

class Document(Base):
    __tablename__ = "patient_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sgimed_patient_id: Mapped[str]
    sgimed_document_id: Mapped[str] = mapped_column(unique=True)
    sgimed_branch_id: Mapped[str]
    sgimed_visit_id: Mapped[Optional[str]]
    status: Mapped[Optional[DocumentStatus]]
    name: Mapped[str]
    hidden: Mapped[bool] = mapped_column(default=False)
    document_date: Mapped[date]
    remarks: Mapped[Optional[str]]
    document_type: Mapped[DocumentType]
    notification_sent: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[Optional[datetime]] # = mapped_column(server_default=func.now())
    updated_at: Mapped[Optional[datetime]] # = mapped_column(server_default=func.now(), onupdate=func.now())

    account: Mapped[Optional["Account"]] = relationship(
        foreign_keys='Account.sgimed_patient_id',
        primaryjoin="Document.sgimed_patient_id == Account.sgimed_patient_id"
    )
    
    branch: Mapped[Optional["Branch"]] = relationship(
        foreign_keys='Branch.sgimed_branch_id',
        primaryjoin="Document.sgimed_branch_id == Branch.sgimed_branch_id"
    )

    def get_file_viewer_type(self):
        if self.document_type in [DocumentType.MC, DocumentType.INVOICE]:
            return FileViewerType.HTML
        elif self.name.lower().endswith('pdf'):
            return FileViewerType.PDF
        return FileViewerType.IMAGE

    def get_file_name(self):
        ext = osp.splitext(self.name)[-1].lower()
        if not ext:
            ext = '.pdf'
        
        return f"{self.document_type.value} {self.document_date.strftime('%d %b %Y')}{ext}"

class DocumentTypeSGiMed(Base):
    __tablename__ = "patient_document_types"
    
    id: Mapped[DocumentType] = mapped_column(primary_key=True)
    sgimed_document_type_id: Mapped[str]

class HealthReport(Base):
    __tablename__ = "patient_health_reports"

    sgimed_hl7_id: Mapped[str] = mapped_column(primary_key=True)
    sgimed_hl7_content: Mapped[str]
    sgimed_patient_id: Mapped[str]
    sgimed_report_id: Mapped[str] = mapped_column(unique=True) # Lab Report
    sgimed_report_file_date: Mapped[datetime] # UTC time
    patient_test_results: Mapped[str] # HL7 Markers + Patient Measurements
    report_summary: Mapped[str]
    disclaimer_accepted_at: Mapped[Optional[datetime]] 
    
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

class HealthReportProfile(Base):
    __tablename__ = "patient_health_report_profiles"

    sgimed_hl7_id: Mapped[str] = mapped_column(primary_key=True)
    health_profile_id: Mapped[str] = mapped_column(primary_key=True)
    sgimed_patient_id: Mapped[str] = mapped_column(index=True)
    report: Mapped[str]
