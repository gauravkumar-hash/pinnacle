from datetime import date, datetime
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from models import get_db
from models.document import Document
from models.model_enums import DocumentStatus, DocumentType
from models.patient import Account
from models.pinnacle import Branch
from utils.fastapi import SuccessResp
from utils.supabase_auth import get_superadmin
from sqlalchemy.orm import joinedload
router = APIRouter(dependencies=[Depends(get_superadmin)])

class DocumentAdminResp(BaseModel):
    id: str
    sgimed_patient_id: str
    patient_name: str
    patient_nric: str
    branch_name: str
    status: DocumentStatus | None
    name: str
    document_type: DocumentType
    document_date: date
    last_updated: datetime | None # NOTE: This is taken from SGiMed previously and timings were not changed to UTC

class DocumentAdminReq(BaseModel):
    doc_date: date | None = None

@router.post('/hidden', response_model=list[DocumentAdminResp])
def get_hidden_documents(req: DocumentAdminReq, db: Session = Depends(get_db)):
    db_req = db.query(Document) \
        .options(
            joinedload(Document.account).load_only(Account.name), # Left Join
            joinedload(Document.branch).load_only(Branch.name), # Left Join
        ) \
        .filter(
            Document.hidden == True,
            or_(Document.status == DocumentStatus.COMPLETE, Document.status == None)
        )
    if req.doc_date:
        db_req = db_req.filter(Document.document_date == req.doc_date)
    documents = db_req.all()

    return [
        DocumentAdminResp(
            id=str(document.id),
            sgimed_patient_id=document.sgimed_patient_id,
            patient_name=document.account.name,
            patient_nric=document.account.nric,
            branch_name=document.branch.name,
            status=document.status,
            name=document.name,
            document_type=document.document_type,
            document_date=document.document_date,
            last_updated=document.updated_at if document.updated_at else document.created_at
        ) 
        for document in documents if document.account and document.branch
    ]

class UpdateHiddenDocumentReq(BaseModel):
    id: str

@router.post('/hidden/update', response_model=SuccessResp)
def unhide_document(req: UpdateHiddenDocumentReq, db: Session = Depends(get_db)):
    updated = db.query(Document) \
        .filter(
            Document.id == req.id,
            Document.hidden == True
        ) \
        .update({
            Document.hidden: False
        })
    db.commit()
    return SuccessResp(success=bool(updated))
