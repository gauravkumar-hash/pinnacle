from datetime import date, datetime
from enum import Enum
import logging
from typing import Literal, Optional
from pydantic import BaseModel, field_validator, HttpUrl
from utils.integrations.sgimed import SGiMedId, SGiMedIdName, get

def fetch_bulk_records(endpoint: Literal['/document', '/invoice', '/order/mc'], sgimed_patient_id: str):
    records = []
    for i in range(0, 20):
        resp = get(endpoint, { "page": i + 1, "patient_id": sgimed_patient_id })
        records += resp['data']
        # More than 20 pages, log as error
        if i == 0 and resp['pager']['pages'] > 20:
            logging.error(f"Patient {sgimed_patient_id} has more than 20 pages of {endpoint}")
        if resp['pager']['p'] >= resp['pager']['pages']:
            break

    return records

class SGiMedDocument(BaseModel):
    id: str
    name: str
    remark: str | None
    patient: SGiMedIdName
    visit: SGiMedId | None
    branch_id: str
    document_date: date
    upload_file_name: str | None
    file_ext_name: str | None
    document_type: SGiMedIdName
    last_edited: datetime | None
    created_at: datetime

def fetch_sgimed_documents(sgimed_patient_id: str):
    return [SGiMedDocument(**row) for row in fetch_bulk_records('/document', sgimed_patient_id)]

class SGiMedInvoiceStatus(str, Enum):
    VOID = "void" # No Item on Invoice
    DRAFT = "in work" # Draft
    BILL = "bill" # Marked as Outstanding
    PARTIAL_PAID = "partial paid" # Partially Paid
    PAID = "paid" # Paid Fully

class SGiMedInvoice(BaseModel):
    id: str
    discount: float
    status: SGiMedInvoiceStatus
    total: float
    patient_outstanding: float
    branch_id: str
    issued_date: date
    last_edited: datetime | None
    created_at: datetime
    company: SGiMedIdName | None
    patient: SGiMedIdName
    visit: SGiMedId

def fetch_sgimed_invoices(sgimed_patient_id: str):
    return [SGiMedInvoice(**row) for row in fetch_bulk_records('/invoice', sgimed_patient_id)]

class SGiMedMC(BaseModel):
    id: str
    patient: SGiMedIdName
    is_void: bool
    visit: SGiMedId
    branch_id: str
    last_edited: datetime | None
    created_at: datetime

def fetch_sgimed_mcs(sgimed_patient_id: str):
    return [SGiMedMC(**row) for row in fetch_bulk_records('/order/mc', sgimed_patient_id)]

class FilePath(BaseModel):
    link: HttpUrl

class SGiMedDocumentResp(BaseModel):
    id: str
    name: str
    remark: Optional[str] = None
    patient: SGiMedId
    # Bug: When visit is set, API returns "visit": [] instead of id
    # visit: Optional[SGiMedId] = None
    branch_id: str
    document_date: date
    upload_file_name: str | None
    file_path: FilePath
    file_ext_name: str | None
    document_type: SGiMedId
    last_edited: datetime | None
    created_at: datetime
    
    @field_validator("file_ext_name", mode="before")
    @classmethod
    def transform_language(cls, raw: Optional[str]) -> str:
        return raw if raw else 'pdf'

def get_document(sgimed_document_id: str) -> SGiMedDocumentResp:
    endpoint = f'/document/{sgimed_document_id}'
    resp_data = get(endpoint)
    resp = SGiMedDocumentResp(**resp_data)
    return resp

class SGiMedReportResp(BaseModel):
    id: str
    patient: SGiMedId
    file_name: str
    file_ext_name: str | None = None
    file_date: datetime
    file_path: FilePath

    @field_validator("file_ext_name", mode="before")
    @classmethod
    def transform_language(cls, raw: Optional[str]) -> str:
        return raw if raw else 'pdf'

def get_sgimed_report(sgimed_report_id: str) -> SGiMedReportResp:
    endpoint = f'/incoming-report/{sgimed_report_id}'
    resp_data = get(endpoint)
    resp = SGiMedReportResp(**resp_data)
    return resp
