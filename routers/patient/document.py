from datetime import date, datetime, timedelta
from enum import Enum
import logging
from typing import Literal, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import requests
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from models import get_db
from models.corporate import CorpAuthorisation, CorporateAuth, CorporateUser
from models.document import Document, DocumentTypeSGiMed, HealthReport
from models.model_enums import DocumentStatus, DocumentType, FileViewerType, TeleconsultStatus
from models.patient import Account
from models.teleconsult import Teleconsult
from utils import sg_datetime
from utils.fastapi import HTTPJSONException, SuccessResp
from utils.integrations.sgimed import get_invoice_html, get_mc_html, retrieve_sgimed_patient_id, user_exists_in_sgimed
from utils.integrations.sgimed_documents import SGiMedInvoiceStatus, fetch_sgimed_documents, fetch_sgimed_invoices, fetch_sgimed_mcs, get_document, get_sgimed_report
from .utils import validate_firebase_token, validate_user
from services.health_report import generate_health_report_pdf

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

def commit_or_rollback(db: Session, error: str):
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"{error}, {e}", exc_info=True)

def retrieve_sgimed_records(db: Session, user: Account):
    '''
    Sync invoices and MCs from SGiMed to patient_documents
    '''
    if user.sgimed_synced:
        return
    if not user.sgimed_patient_id:
        logging.error(f"Invalid call to retrieve_sgimed_records, sgimed_patient_id is None. User: {user.id}")
        return
    
    # Retrieve any existing documents that are already added via Cron Scheduler
    existing_documents = db.query(Document.sgimed_document_id).filter(
            Document.sgimed_patient_id == user.sgimed_patient_id,
            # Document.document_type.in_([DocumentType.INVOICE, DocumentType.MC])
        ).all()
    existing_documents = [row[0] for row in existing_documents]
    
    # Retrieve MCs, need to check if teleconsult is outstanding
    teleconsults = db.query(Teleconsult.sgimed_visit_id).filter(
            Teleconsult.account_id == user.id,
            Teleconsult.sgimed_visit_id != None,
            Teleconsult.status != TeleconsultStatus.CHECKED_OUT
        ).all()    
    teleconsults = [row[0] for row in teleconsults]

    # Populate Documents
    doc_types = db.query(DocumentTypeSGiMed).all()
    doc_type_dict = { dtype.sgimed_document_type_id: dtype.id for dtype in doc_types }
    documents = fetch_sgimed_documents(user.sgimed_patient_id)    
    print(f"User {user.sgimed_patient_id}: {len(documents)} Documents")
    for row in documents:
        if row.id in existing_documents:
            continue
        if row.document_type.id not in doc_type_dict:
            continue

        db.add(Document(
            sgimed_patient_id=row.patient.id,
            sgimed_document_id=row.id,
            sgimed_branch_id=row.branch_id,
            sgimed_visit_id=row.visit.id if row.visit else None,
            hidden=False,
            name=row.name,
            document_date=row.document_date,
            remarks=row.remark,
            document_type=doc_type_dict[row.document_type.id],
            created_at=row.created_at,
            updated_at=row.last_edited if row.last_edited else row.created_at,
        ))
    commit_or_rollback(db, f"Failed to add documents. patient_id: {user.sgimed_patient_id}")

    # Populate Invoices
    invoices = fetch_sgimed_invoices(user.sgimed_patient_id)
    # This is needed to filter out duplicates from SGiMed invoices
    invoices = { inv.id: inv for inv in invoices }
    for row in invoices.values():
        if row.id in existing_documents:
            continue

        sgimed_invoice_status_mapping = {
            SGiMedInvoiceStatus.VOID: DocumentStatus.VOID,
            SGiMedInvoiceStatus.DRAFT: DocumentStatus.DRAFT,
            SGiMedInvoiceStatus.BILL: DocumentStatus.PENDING,
            SGiMedInvoiceStatus.PARTIAL_PAID: DocumentStatus.PENDING,
            SGiMedInvoiceStatus.PAID: DocumentStatus.COMPLETE,
        }
        status = sgimed_invoice_status_mapping.get(row.status, None)
        # Pending state to commplete based on patient_outstanding
        if status == DocumentStatus.PENDING and row.patient_outstanding <= 0:
            status = DocumentStatus.COMPLETE
        hidden = status in [DocumentStatus.DRAFT, DocumentStatus.VOID] or bool(row.total <= 0 or row.discount > 0)
        
        update_dict = {
            "sgimed_patient_id": row.patient.id,
            "sgimed_document_id": row.id,
            "sgimed_branch_id": row.branch_id,
            "sgimed_visit_id": row.visit.id,
            "name": "Invoice",
            "status": status,
            "hidden": hidden,
            "document_date": row.issued_date,
            "remarks": f"${row.total:.2f}",
            "document_type": DocumentType.INVOICE,
            "created_at": row.created_at,
            "updated_at": row.last_edited if row.last_edited else row.created_at,
        }
        doc = db.query(Document).filter_by(sgimed_document_id=row.id).first()
        if doc:
            doc.update_vars(update_dict)
        else:
            doc = Document(**update_dict)
            db.add(doc)

    commit_or_rollback(db, f"Failed to add invoices. patient_id: {user.sgimed_patient_id}")

    # Populate Medical Certificates
    mcs = fetch_sgimed_mcs(user.sgimed_patient_id)
    print(f"User {user.sgimed_patient_id}: {len(mcs)} MCs")
    for row in mcs:
        if row.id in existing_documents:
            continue
        
        db.add(Document(
            sgimed_patient_id=row.patient.id,
            sgimed_document_id=row.id,
            sgimed_branch_id=row.branch_id,
            sgimed_visit_id=row.visit.id,
            name="Medical Certificate (MC)",
            hidden=row.visit.id in teleconsults,
            document_date=row.created_at.date(),
            document_type=DocumentType.MC,
            created_at=row.created_at,
            updated_at=row.last_edited if row.last_edited else row.created_at,
        ))
    commit_or_rollback(db, f"Failed to add MCs. patient_id: {user.sgimed_patient_id}")

    user.sgimed_synced = True
    db.commit()

def validate_patient_sync(db: Session, user: Account):
    # Check if user.sgimed_patient_id is valid, if not, reset it
    if user.sgimed_patient_id and not user_exists_in_sgimed(user.sgimed_patient_id):
        user.sgimed_patient_id = None
        user.sgimed_synced = False
    
    # If sgimed_patient_id is not valid, retrieve it from SGiMed
    if not user.sgimed_patient_id:
        retrieve_sgimed_patient_id(db, user)

class DocumentRouteType(str, Enum):
    ALL = 'All'
    MY_FAMILY = 'My Family'
    # Please ensure all DocumentType are included here
    INVOICE = 'Invoice'
    MC = 'Medical Certificate (MC)'
    HEALTH_SCREENING = 'Health Report'
    LAB = 'Lab Report'
    RADIOLOGY = 'Radiology Report'
    REFERRAL_LETTER = 'Referral'
    VACCINATION = 'Vaccination Report'

class DocumentInfo(BaseModel):
    id: str
    type: DocumentType
    title: str
    subtitle: str
    content: Optional[str] = None
    file_type: FileViewerType
    file_name: str
    pathname: Literal['/documents/viewer', '/documents/health_report'] = '/documents/viewer'

class DownloadDocumentReq(BaseModel):
    code: str

def validate_edocs_access(db: Session, user: Account):
    # Check if user belongs to any corporate user
    corp_codes = db.query(CorporateUser.code).filter(CorporateUser.ic_type == user.ic_type, CorporateUser.nric == user.nric).all()
    corp_codes = [row[0] for row in corp_codes]    
    if not corp_codes:
        return
    
    # Check if user has permission to access eDocs
    exists = db.query(CorporateAuth.id).filter(
            CorporateAuth.code.in_(corp_codes), 
            CorporateAuth.permission == CorpAuthorisation.BLOCK_EDOCS
        ).first()
    if exists:
        raise HTTPJSONException(
            "Access Denied",
            f"\"My Records\" is disabled for your account.\n[]()\nPlease contact {','.join(corp_codes)} HR if you require any clarification."
        )

@router.post('/validate_code', response_model=SuccessResp)
async def validate_code(req: DownloadDocumentReq, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    validate_edocs_access(db, user)
    # Check if user.sgimed_patient_id is valid, if not, reset it
    validate_patient_sync(db, user)

    if not user.sgimed_patient_id:
        return SuccessResp(success=True)
    if user.sgimed_auth_code != req.code:
        raise HTTPJSONException(
            "Invalid Code",
            "Code is invalid, please try again.\n[]()\nIf this was a mistake, kindly call\n[+65 6235 1852](tel:62351852)"
        )

    return SuccessResp(success=True)

class DocumentsReq(BaseModel):
    offset: int
    type: DocumentRouteType
    code: str

class DocumentsResp(BaseModel):
    # pager: Pager
    data: list[DocumentInfo]
    next_cursor: Optional[int] = None

def get_docs(req: DocumentsReq, user: Account, db: Session, show_app_health_reports: bool = False, page_size: int = 20):
    validate_edocs_access(db, user)

    # If sgimed_patient_id is still not valid, return empty documents
    if not user.sgimed_patient_id:
        return DocumentsResp(data=[], next_cursor=None)
    if user.sgimed_auth_code != req.code:
        raise HTTPException(status_code=400, detail="Invalid code")
    
    # Called to ensure that documents are synced
    retrieve_sgimed_records(db, user)

    qry = db.query(Document).filter(Document.hidden == False)

    # Filter for current user and family members
    user_queries = []
    # Do not include current user, if "My Family" is selected
    if req.type != DocumentRouteType.MY_FAMILY:
        user_queries = [Document.sgimed_patient_id == user.sgimed_patient_id]
    
    def calculate_age(today: datetime, birth_date: date) -> int:
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

    # Used to populate document retrieval names
    family_names = {}

    today = sg_datetime.now()
    for family_member in user.family_members:
        # Ensure that sgimed_patient_id is populated corrected
        if not family_member.nok_account.sgimed_patient_id:
            retrieve_sgimed_patient_id(db, family_member.nok_account)
        if not family_member.nok_account.sgimed_patient_id:
            continue

        # Called to ensure that documents are synced
        retrieve_sgimed_records(db, family_member.nok_account)

        # If user is above 21, do not show health screening documents
        # Also queries for documents created after the family member was added
        # created_at is in UTC, while document created_at is in SGT, thus the conversion and drop of tzinfo
        # Allow the viewing of documents created 3 days before the family member was added
        nok_created_at = sg_datetime.sg(family_member.created_at).replace(tzinfo=None) - timedelta(days=3)
        if calculate_age(today, family_member.nok_account.date_of_birth) >= 21:
            user_queries.append(and_(
                Document.sgimed_patient_id == family_member.nok_account.sgimed_patient_id,
                # Do not include Health Screening, Lab, Radiology, Vaccination reports
                Document.document_type != DocumentType.HEALTH_SCREENING,
                Document.document_type != DocumentType.LAB,
                Document.document_type != DocumentType.RADIOLOGY,
                Document.document_type != DocumentType.VACCINATION,
                Document.created_at >= nok_created_at
            ))
        else:
            user_queries.append(
                and_(
                    Document.sgimed_patient_id == family_member.nok_account.sgimed_patient_id,
                    Document.created_at >= nok_created_at
                )
            )

        # Populate names for documents retrieval
        family_names[family_member.nok_account.sgimed_patient_id] = family_member.nok_account.name

    # If user_queries are empty, meaning no data, return empty. Because querying it will return all data
    if not user_queries:
        return DocumentsResp(
            data=[], 
            next_cursor=None
        )

    qry = qry.filter(or_(*user_queries))

    # Filter by Document Type
    all_doc_routes = [DocumentRouteType.ALL, DocumentRouteType.MY_FAMILY]
    if req.type not in all_doc_routes:
        qry = qry.filter(Document.document_type == DocumentType(req.type.value))
    
    # Ensure app health reports are not shown for app deployed version without Health Report UI
    if not show_app_health_reports:
        qry = qry.filter(or_(Document.status == None, Document.status != DocumentStatus.APP_HEALTH_REPORT))

    # Order By & Pagination
    qry = qry \
        .order_by(Document.created_at.desc()) \
        .offset(req.offset).limit(page_size) \
    
    # Convert DB model to FastAPI response model
    docs = qry.all()
    docs = [
        DocumentInfo(
            id=str(doc.id),
            type=doc.document_type,
            title=doc.document_type.value,
            subtitle=doc.created_at.strftime("%d %b %Y, %I:%M%p") + (f" **For {family_names[doc.sgimed_patient_id]}**" if doc.sgimed_patient_id != user.sgimed_patient_id else ""),
            content=doc.remarks if doc.document_type == DocumentType.INVOICE else None,
            file_type=doc.get_file_viewer_type(),
            file_name=doc.get_file_name(),
            pathname='/documents/viewer' if doc.status != DocumentStatus.APP_HEALTH_REPORT else '/documents/health_report',
        ) 
        for doc in docs if doc.created_at
    ]

    return DocumentsResp(
            data=docs, 
            next_cursor=req.offset + page_size if len(docs) == page_size else None
        )

@router.post('/', response_model=DocumentsResp)
def get_docs_v1(req: DocumentsReq, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    return get_docs(req, user, db, False)

@router.post('/v2', response_model=DocumentsResp)
def get_docs_v2(req: DocumentsReq, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    return get_docs(req, user, db, True)

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def get_document_db(db: Session, user: Account, code: str, document_id: str):
    # Ensure sgimed_patient_id & sgimed_auth_code are valid
    sgimed_patient_id = user.sgimed_patient_id
    if not sgimed_patient_id:
        raise HTTPException(400, "You do not have permission to access this document. If this was a mistake, please contact an administrator")
    if not user.sgimed_auth_code == code:
        raise HTTPException(400, "Invalid code")

    # Ensure record exists in the database
    doc_db = db.query(Document).filter(Document.id == document_id).first()
    if not doc_db:
        raise HTTPException(400, "You do not have permission to access this document. If this was a mistake, please contact an administrator")
    if doc_db.hidden:
        raise HTTPException(400, "This document is not available for download")

    return doc_db

def check_family_access(db: Session, user: Account, doc_patient_id: str):
    if user.sgimed_patient_id == doc_patient_id:
        return True

    if doc_patient_id not in [fm.nok_account.sgimed_patient_id for fm in user.family_members if fm.nok_account.sgimed_patient_id]:
        raise HTTPException(400, "You do not have permission to access this document. If this was a mistake, please contact an administrator.")

    return True

@router.get('/health_report/{report_id}')
async def get_health_report(report_id: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    '''
    Get health report from SGiMed
    '''
    # Validation to ensure that user has access to the document
    validate_edocs_access(db, user)
    report = db.query(HealthReport).filter(
        HealthReport.sgimed_report_id == report_id
    ).first()
    if not report:
        raise HTTPException(400, "You do not have permission to access this document. If this was a mistake, please contact an administrator.")
    
    check_family_access(db, user, report.sgimed_patient_id)
    
    fname, pdf_bytes = generate_health_report_pdf(report, db)
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{fname}"'}
    )

@router.get("/{document_id}")
async def download_document(document_id: str, code: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    '''
    Download document from SGiMed
    '''
    validate_edocs_access(db, user)
    if is_valid_uuid(document_id):
        doc_db = get_document_db(db, user, code, document_id)
        if doc_db.document_type in [DocumentType.INVOICE, DocumentType.MC]:
            raise HTTPException(400, "This document is not available for download")
        # Fetch document from SGiMed
        try:
            doc = get_document(doc_db.sgimed_document_id)
        except Exception as e:
            logging.error(f"download_document: Patient: {user.sgimed_patient_id}, Document: {doc_db.sgimed_document_id}, {e}", exc_info=True)
            raise HTTPException(500, "Failed to fetch document. please contact an administrator")

    # Report ID from Health Reports
    else:
        doc = get_sgimed_report(document_id)

    # Ensure document fetched only allowed within the user's family
    check_family_access(db, user, doc.patient.id)
    # Get the file from the external link
    response = requests.get(str(doc.file_path.link), stream=True)
    if response.status_code != 200:
        logging.error(f"File not found on SGiMed. Patient: {user.sgimed_patient_id}, Req ID: {document_id}, Document: {doc.id}, {response.status_code}")
        raise HTTPException(404, "Failed to fetch document. please contact an administrator")
        
    # Stream the file
    return StreamingResponse(
        response.iter_content(chunk_size=8192),
        media_type=response.headers["Content-Type"],
        headers={
            "Content-Disposition": f'attachment; filename="pinnaclesg_{document_id}.{doc.file_ext_name}"'
        }
    )

class DocumentHTMLResp(BaseModel):
    html: str

@router.get("/{document_id}/html", response_model=DocumentHTMLResp)
async def get_document_html(document_id: str, code: str, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)    
    validate_edocs_access(db, user)
    doc_db = get_document_db(db, user, code, document_id)

    # Ensure document fetched only allowed within the user's family
    check_family_access(db, user, doc_db.sgimed_patient_id)

    if doc_db.document_type == DocumentType.INVOICE:
        html = get_invoice_html(doc_db.sgimed_document_id)
        return DocumentHTMLResp(html=html)
    elif doc_db.document_type == DocumentType.MC:
        html = get_mc_html(doc_db.sgimed_document_id)
        return DocumentHTMLResp(html=html)
    else:
        raise HTTPException(400, "This document is not available for html")

# Commented as PDF generation is left to client side (Patient App)
# @router.post('/{document_id}/pdf')
# async def test_html_to_pdf(document_id: str, req: DownloadDocumentReq, background_tasks: BackgroundTasks, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
#     '''
#     https://apitemplate.io/blog/how-to-convert-html-to-pdf-using-python/#pyppeteer
#     '''
#     user = validate_user(db, firebase_uid)
#     validate_edocs_access(db, user)
#     doc_db = get_document_db(db, user, req.code, document_id)
#     if doc_db.document_type == DocumentType.INVOICE:
#         html = get_invoice_html(doc_db.sgimed_document_id)
#     elif doc_db.document_type == DocumentType.MC:
#         html = get_mc_html(doc_db.sgimed_document_id)
#     else:
#         raise HTTPException(400, "This document is not available for html")

#     # Dependencies for Creation
#     from pyppeteer import launch

#     temp_path = f'document_{time.time()}.pdf'

#     try:
#         # Generate PDF
#         browser = await launch()
#         page = await browser.newPage()
#         await page.setContent(html)
#         await page.pdf({'path': temp_path, 'format': 'A4'})
#         await browser.close()
        
#         # Cleanup the file if required
#         background_tasks.add_task(os.unlink, temp_path)
#         # Return PDF as FileResponse
#         return FileResponse(
#             path=temp_path,
#             filename=f"pinnaclesg_{document_id}.pdf",
#             media_type="application/pdf"
#         )
#     except Exception as e:
#         logging.error(f"Failed to generate PDF: {e}", exc_info=True)
#         raise HTTPException(500, f"Failed to generate PDF")
