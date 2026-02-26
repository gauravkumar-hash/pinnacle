import enum
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models.model_enums import VisitType, TeleconsultStatus, WalkinQueueStatus
from models.payments import Invoice
from models.teleconsult import Teleconsult
from models.walkin import WalkInQueue
from routers.patient.actions.walkin import get_walkin_queues_numbers, get_walkin_queues_status
from services.visits import DocumentHtml, get_invoice_document_html, get_mc_document_html
from .utils import validate_firebase_token, validate_user
from models import get_db
from utils.sg_datetime import sg

router = APIRouter()

class DocType(enum.Enum):
    INVOICE = 'invoice'
    MC = 'mc'

class VisitsResp(BaseModel):
    id: Optional[str] = None # If None, means ongoing
    type: VisitType | DocType
    title: str
    content: Optional[str] = None
    boldContent: Optional[str] = None
    subtitle: Optional[str] = None
    tag: Optional[str] = None

@router.get('/teleconsults', response_model=list[VisitsResp])
def get_teleconsults(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)

    qry = db.query(Teleconsult)
    # Get all MCs for the user and family members
    user_queries = [Teleconsult.account_id == user.id]
    user_queries += [
        and_(Teleconsult.account_id == family_member.nok_id, Teleconsult.created_at >= family_member.created_at)
        for family_member in user.family_members
    ]
    teleconsults = qry.filter(or_(*user_queries)).order_by(Teleconsult.created_at.desc()).all()

    # Group Teleconsults
    grouped_teleconsults = {}
    for teleconsult in teleconsults:
        if teleconsult.status == TeleconsultStatus.PREPAYMENT:
            continue

        if teleconsult.group_id:
            if teleconsult.group_id not in grouped_teleconsults:
                grouped_teleconsults[teleconsult.group_id] = []
            grouped_teleconsults[teleconsult.group_id].append(teleconsult)
        else:
            grouped_teleconsults[teleconsult.id] = [teleconsult]

    # Generate Responses
    resp: list[VisitsResp] = []
    for teleconsults in sorted(grouped_teleconsults.values(), key=lambda x: x[0].checkin_time, reverse=True):
        record = teleconsults[0]
        subtitle = (f'Checked Out: {sg(record.checkout_time).strftime("%d %b %Y, %I:%M%p")}' if record.checkout_time else f'Checked In: {sg(record.checkin_time).strftime("%d %b %Y, %I:%M%p")}')
        if record.group_id and not (len(teleconsults) == 1 and teleconsults[0].account_id == user.id):
            subtitle += f"\nConsultation For: **{' '.join([r.account.name if r.account_id != user.id else 'Myself' for r in sorted(teleconsults, key=lambda x: x.index)])}**"

        resp.append(VisitsResp(
            id=str(record.id) if record.status in [TeleconsultStatus.CHECKED_OUT] else None,
            type=VisitType.TELECONSULT,
            title='Telemedicine Consultation',
            subtitle=subtitle,
            content=record.queue_status,
            tag=record.status.value
        ))

    return resp

@router.get('/walkins', response_model=list[VisitsResp])
def get_walkins(firebase_uid = Depends(validate_firebase_token), db = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    qry = db.query(WalkInQueue)
    # Get all MCs for the user and family members
    user_queries = [WalkInQueue.account_id == user.id]
    user_queries += [
        and_(WalkInQueue.account_id == family_member.nok_id, WalkInQueue.created_at >= family_member.created_at)
        for family_member in user.family_members
    ]
    queues = qry.filter(or_(*user_queries)).order_by(WalkInQueue.created_at.desc()).all()

    # Group Teleconsults
    grouped_queues = {}
    for queue in queues:
        if queue.group_id:
            if queue.group_id not in grouped_queues:
                grouped_queues[queue.group_id] = []
            grouped_queues[queue.group_id].append(queue)
        else:
            grouped_queues[queue.id] = [queue]

    # Generate Responses
    resp: list[VisitsResp] = []
    for queues in sorted(grouped_queues.values(), key=lambda x: x[0].created_at, reverse=True):
        queues = sorted(queues, key=lambda x: x.index if x.index else 0)
        status, queue_status = get_walkin_queues_status(queues)
        queue = queues[0]

        if not queue.checkout_time:
            subtitle = f'Requested: {sg(queue.created_at).strftime("%d %b %Y, %I:%M%p")}'
        else:
            subtitle = f'Checked Out: {sg(queue.checkout_time).strftime("%d %b %Y, %I:%M%p")}'
        if len(queues) > 1 or queues[0].account_id != user.id:
            subtitle += f"\nConsultation For: **{' '.join([r.account.name if r.account_id != user.id else 'Myself' for r in queues])}**"
        
        queue_number = get_walkin_queues_numbers(queues, status)
        
        resp.append(VisitsResp(
            id=str(queue.id) if status not in [WalkinQueueStatus.PENDING, WalkinQueueStatus.CHECKED_IN, WalkinQueueStatus.CONSULT_START] else None,
            type=VisitType.WALKIN,
            title=f'Queue Request ({queue.branch.name})',
            subtitle=subtitle,
            content=queue_status,
            boldContent=queue_number,
            tag=status.value
        ))
    return resp

@router.get('/invoices', response_model=list[VisitsResp])
def get_invoices(firebase_uid = Depends(validate_firebase_token), db = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    qry = db.query(Invoice).filter(Invoice.show_details == True, Invoice.hide_invoice == False)
    # Get all MCs for the user and family members
    user_queries = [Invoice.account_id == str(user.id)]
    user_queries += [
        and_(Invoice.account_id == str(family_member.nok_id), Invoice.created_at >= family_member.created_at)
        for family_member in user.family_members
    ]    
    invoices = qry.filter(or_(*user_queries)).order_by(Invoice.created_at.desc()).all()

    def generate_response(record):
        subtitle = sg(record.created_at).strftime("%d %b %Y, %I:%M%p")
        if record.account_id != user.id:
            subtitle += f"\nFor: **{record.account.name}**"
        
        return VisitsResp(
            id=str(record.id),
            type=DocType.INVOICE,
            title='Invoice',
            subtitle=subtitle,
            content=f'S${record.amount:.2f}'
        )
    
    return list(map(generate_response, invoices))

@router.get('/mcs', response_model=list[VisitsResp])
def get_mcs(firebase_uid = Depends(validate_firebase_token), db = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    qry = db.query(Invoice).filter(Invoice.mc_html != None, Invoice.show_details == True)
    # Get all MCs for the user and family members
    user_queries = [Invoice.account_id == str(user.id)]
    user_queries += [
        and_(Invoice.account_id == str(family_member.nok_id), Invoice.created_at >= family_member.created_at)
        for family_member in user.family_members
    ]    
    invoices = qry.filter(or_(*user_queries)).order_by(Invoice.created_at.desc()).all()

    def generate_response(record):
        subtitle = sg(record.created_at).strftime("%d %b %Y, %I:%M%p")
        if record.account_id != user.id:
            subtitle += f"\nFor: **{record.account.name}**"
        return VisitsResp(
            id=str(record.id),
            type=DocType.MC,
            title='Medical certificate (MC)',
            subtitle=subtitle
        )
    
    return list(map(generate_response, invoices))

@router.get('/invoice', response_model=DocumentHtml)
def get_invoice(doc_id: str, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    record = db.query(Invoice).filter(
        Invoice.id == doc_id,
        Invoice.account_id.in_([user.id, *user.get_linked_account_ids()])
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    return get_invoice_document_html(record.invoice_html)

@router.get('/mc', response_model=DocumentHtml)
def get_mc(doc_id: str, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    record = db.query(Invoice).filter(
        Invoice.id == doc_id,
        Invoice.account_id.in_([user.id, *user.get_linked_account_ids()])
    ).first()
    if not record or not record.mc_html:
        raise HTTPException(status_code=404, detail="Record not found")
    
    return get_mc_document_html(record.mc_html)
