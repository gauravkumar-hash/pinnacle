import logging
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from config import WALK_IN_START_TIME_DELAY
from models import get_db, get_user
from models.document import Document
from models.model_enums import CollectionMethod, DocumentType, FileViewerType, WalkinQueueStatus
from models.patient import Account, FamilyNok
from models.pinnacle import Branch, Service
from models.walkin import WalkInQueue
from routers.patient.actions.walkin import get_grouped_walkins, get_walkin_queues_numbers, get_walkin_queues_status
from routers.patient.teleconsult_family import DocumentDict, PrescriptionDict
from routers.patient.utils import validate_firebase_token, validate_user
from services.visits import DocumentHtml, get_invoice_document_html, get_mc_document_html
from utils import sg_datetime
from utils.fastapi import SuccessResp
from utils.integrations.sgimed import cancel_pending_queue, create_pending_queue, create_sgimed_walkin_queue, update_queue_instructions, upsert_patient_in_sgimed

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

@router.get("/services", response_model=list[str])
def get_services(db: Session = Depends(get_db)):
    services = db.query(Service).filter(Service.is_for_visit == True).all()
    return list(set(map(lambda x: x.label, services)))

class AvailableBranchesResp(BaseModel):
    id: str
    name: str
    category: str
    availability: str

@router.get("/branches", response_model=list[AvailableBranchesResp])
def get_available_branches(service: str, db: Session = Depends(get_db)):
    services = db.query(Service).filter(Service.label == service, Service.is_for_visit == True).all()
    services_sgimed_branch_ids = [service.sgimed_branch_id for service in services]
    branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False).all()
    curr_dt = sg_datetime.now()
    
    def map_branch(branch: Branch):
        availability = 'Not Supported'
        if branch.sgimed_branch_id in services_sgimed_branch_ids:
            availability = 'Closed'
            operating = branch.is_operating(db, curr_dt, CollectionMethod.WALKIN)
            if operating:
                curr_time = curr_dt.time()
                curr_time_mins = curr_time.hour * 60 + curr_time.minute
                operating_time_mins = operating.start_time.hour * 60 + operating.start_time.minute
                mins_diff = curr_time_mins - operating_time_mins
                if mins_diff >= WALK_IN_START_TIME_DELAY:
                    availability = 'Open'
                else:
                    availability = f'Closed (Starting in {WALK_IN_START_TIME_DELAY - mins_diff} mins)'
            else:
                operating = branch.get_next_operating_hour(db, curr_dt, CollectionMethod.WALKIN)
                if operating:
                    start_time_format = "%-I%p" if operating.start_time.minute == 0 else "%-I:%M%p"
                    availability = f'Closed (Opens at {operating.start_time.strftime(start_time_format)})'

        return AvailableBranchesResp(
            id=str(branch.id),
            name=branch.name,
            category=branch.category,
            availability=availability,
        )

    return [map_branch(branch) for branch in branches]


class WalkinQueueCreate(BaseModel):
    patient_ids: Optional[list[str]] = None
    include_user: Optional[bool] = None
    service: str
    branch_id: str

class WalkinQueueResponse(BaseModel):
    id: str
    partial_errors: list[str]

@router.post("/request", response_model=WalkinQueueResponse)
def create_walkin_queue(req: WalkinQueueCreate, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = get_user(db, firebase_uid)
    if not user:
        raise HTTPException(status_code=403, detail="Invalid user")

    # Ensure that branch exists
    branch = db.query(Branch).filter(Branch.id == req.branch_id).first()
    if not branch:
        raise HTTPException(status_code=400, detail="Branch not found")
    
    curr_dt = sg_datetime.now()
    operating = branch.is_operating(db, curr_dt, CollectionMethod.WALKIN)
    if not operating:
        raise HTTPException(status_code=400, detail="Clinic is closed.")
    
    service = db.query(Service).filter(Service.label == req.service, Service.sgimed_branch_id == branch.sgimed_branch_id).first()
    if not service:
        raise HTTPException(status_code=400, detail="Service not supported by clinic")

    # Retrieve all the patients from the database
    patients: list[Account] = []
    
    # v1 code where '' equates to include_user
    if req.include_user or (req.include_user is None and (not req.patient_ids or '' in req.patient_ids)):
        patients.append(user)

    # If patient_ids are provided, then the patients are the family members
    if req.patient_ids:
        patient_ids = [r for r in req.patient_ids if r != '']
        records = db.query(FamilyNok).join(FamilyNok.nok_account).filter(FamilyNok.account_id == user.id, FamilyNok.nok_id.in_(patient_ids), FamilyNok.deleted == False).all()
        # Ensure that all the patients are valid family members
        if len(records) != len(patient_ids):
            raise HTTPException(status_code=400, detail="Invalid patients")
        
        patients += [r.nok_account for r in records]
        
    # Create a queue record in SGiMed using the Online Queue Type. It can fail when it is full
    sgimed_pending_queue_id = None
    queue_number = None
    status = WalkinQueueStatus.PENDING
    queue_status = "Waiting for queue number"
    group_id = str(uuid.uuid4())
    
    errors = []
    sgimed_pending_queues = []    
    # Upsert patient information and create pending queue record
    for patient in patients:
        upsert_patient_in_sgimed(db, patient, branch=branch)

        if not patient.sgimed_patient_id:
            raise HTTPException(status_code=400, detail="Failed to create queue. Please contact customer support if error persists")

        try:
            sgimed_pending_queue_id, queue_number = create_pending_queue(
                patient_id=patient.sgimed_patient_id,
                branch_id=branch.sgimed_branch_id,
                appointment_type_id=service.sgimed_appointment_type_id,
                date=sg_datetime.now().strftime("%Y-%m-%d"),
            )
            sgimed_pending_queues.append((patient, sgimed_pending_queue_id, queue_number))
        except Exception as e:
            # When SGiMed is full, it will return a message that there is no available queue number now
            if 'There is no available queue number now' in str(e):
                errors.append('Clinic has rejected your request as it is currently busy.')
            else:
                logging.error(f"Failed to create walkin queue. {e}")
                errors.append('Failed to create queue. Please contact customer support if error persists.')
                # raise HTTPException(status_code=400, detail="Failed to create queue. Please try again later.")
            continue
    
    # If there are errors creating the pending queues, cancel all of them
    if errors:
        for _, sgimed_pending_queue_id, _ in sgimed_pending_queues:
            cancel_pending_queue(sgimed_pending_queue_id)
        logging.error(f"Walkin Queue Error: {branch.name}. {errors}")
        raise HTTPException(status_code=500, detail='\n'.join(list(set(errors))))

    # Create the required records in the database
    walkin_queues = []
    for i, row in enumerate(sgimed_pending_queues):
        patient, sgimed_pending_queue_id, queue_number = row
        walkin_queue = WalkInQueue(
            branch_id=branch.id,
            account_id=patient.id,
            queue_number=queue_number,
            sgimed_pending_queue_id=sgimed_pending_queue_id,
            service=req.service,
            status=status,
            queue_status=queue_status,
        )
        # If there are multiple patients or if the first patient is not the user, then group the queue
        if len(patients) > 1 or patient.id != user.id:
            walkin_queue.group_id = group_id
            walkin_queue.index = i
            walkin_queue.created_by = str(user.id)
        db.add(walkin_queue)
        walkin_queues.append(walkin_queue)
    db.commit()

    # If no records, throw error
    if not walkin_queues:
        logging.error(f"Failed to create queue. Please try again later. User ID: {user.id}, Patient IDs: {req.patient_ids}")
        raise HTTPException(status_code=500, detail="Failed to create queue. Please contact customer support")

    # Return only the first queue id, and all the errors encountered
    return WalkinQueueResponse(id=str(walkin_queues[0].id), partial_errors=list(set(errors)))

class WalkinDetailsResp(BaseModel):
    id: str
    branch_id: str
    branch_name: str
    subtitle: Optional[str] = None
    status: WalkinQueueStatus
    queue_number: Optional[str] = None
    branch_queue_number: Optional[str] = None
    queue_status: str    
    # Checked Out Details
    invoices: list[DocumentDict] = []
    invoice: Optional[DocumentDict] = None # For v1 compatibility
    prescriptions: list[PrescriptionDict] = []
    documents: list[DocumentDict] = []
    last_update: Optional[str] = None
    allow_add_dependants: bool

@router.get("/details", response_model=WalkinDetailsResp)
def get_walkin_details(id: Optional[str] = None, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    ids = user.get_linked_account_ids()
    
    queue = None
    if id:
        queue = db.query(WalkInQueue).filter(
            or_(WalkInQueue.account_id == user.id, WalkInQueue.created_by == user.id),
            WalkInQueue.id == id
        ).first()
    # Fetching latest record to be processed
    else:
        queue = db.query(WalkInQueue).filter(
            or_(WalkInQueue.account_id == user.id, WalkInQueue.created_by == user.id),
            WalkInQueue.status.in_([WalkinQueueStatus.PENDING, WalkinQueueStatus.CHECKED_IN, WalkinQueueStatus.CONSULT_START])
        ).order_by(WalkInQueue.updated_at.desc()).first()

    queues = None
    if queue:
        queues = get_grouped_walkins(db, queue, user)

    if not queue or not queues:
        raise HTTPException(status_code=404, detail="Queue not found")
    
    status, queue_status = get_walkin_queues_status(queues)
    
    subtitle = ''
    if status in [WalkinQueueStatus.PENDING, WalkinQueueStatus.REJECTED, WalkinQueueStatus.CANCELLED]:
        subtitle = f'Requested: {sg_datetime.sg(queue.created_at).strftime("%d %b %Y, %I:%M%p")}'
    elif status in [WalkinQueueStatus.CHECKED_IN, WalkinQueueStatus.CONSULT_START] and queue.checkin_time:
        subtitle = f'Checked In: {sg_datetime.sg(queue.checkin_time).strftime("%d %b %Y, %I:%M%p")}'
    elif status == WalkinQueueStatus.CHECKED_OUT and queue.checkout_time:
        subtitle = f'Checked Out: {sg_datetime.sg(queue.checkout_time).strftime("%d %b %Y, %I:%M%p")}'
    
    if queue.group_id and not (len(queues) == 1 and queues[0].account_id == user.id):
        subtitle += f"\nConsultation For: **{' '.join([r.account.name.strip() if r.account_id != user.id else 'Myself' for r in queues])}**"

    # Setup all the post documents
    invoices = []
    prescriptions = []
    documents = []
    has_dependants = len(queues) > 1 or queues[0].account_id != user.id
    if status in [WalkinQueueStatus.CHECKED_OUT]:
        docs = db.query(Document) \
            .options(
                joinedload(Document.account).load_only(Account.name),
            ) \
            .filter(
                Document.sgimed_visit_id.in_([q.sgimed_visit_id for q in queues]),
                Document.document_type.in_([DocumentType.INVOICE, DocumentType.MC]),
                Document.hidden == False
            ) \
            .all()

        invoices = [
            DocumentDict(
                id=f'invoice-{str(d.id)}',
                title="Invoice",
                url=f"/api/walkin/invoice?id={d.id}",
                filename="Invoice.pdf",
                subtitle=f"For {d.account.name}" if has_dependants and d.account else None,
                filetype=FileViewerType.HTML,
            )
            for d in docs
            if d.document_type == DocumentType.INVOICE
        ]
        
        # NOTE: Only show MC
        documents = [
            DocumentDict(
                id=f'mc-{str(d.id)}',
                icon="mc",
                title="Medical Certificate (MC)",
                url=f"/api/walkin/mc?id={d.id}",
                filename="Medical Certificate.pdf",
                subtitle=f"For {d.account.name}" if has_dependants and d.account else None,
                filetype=FileViewerType.HTML,
            )
            for d in docs
            if d.document_type == DocumentType.MC
        ]
        
        prescriptions = [
            PrescriptionDict(
                item_name=p['item_name'] if 'item_name' in p else '',
                instructions=p['instructions'] if 'instructions' in p else '',
                precautions=p['precautions'] if 'precautions' in p else '',
                subtitle=f'For {q.account.name}' if q.group_id else None
            )
            for q in queues if q.invoices
            for p in q.invoices[0].prescriptions
        ]

    queue_number = get_walkin_queues_numbers(queues, status)

    # Check if allow add dependants
    allow_add_dependants = False
    if status == WalkinQueueStatus.CHECKED_IN:
        # Check has Family Members and if all already added
        active_queue_acc_ids = [q.account_id for q in queues]
        family_member_acc_ids = [fm.nok_id for fm in user.family_members]
        allow_add_dependants = len(set(family_member_acc_ids) - set(active_queue_acc_ids)) > 0

    return WalkinDetailsResp(
        id=str(queue.id),
        branch_id=str(queue.branch_id),
        branch_name=queue.branch.name,
        subtitle=subtitle,
        status=status,
        queue_status=queue_status,
        queue_number=queue_number,
        branch_queue_number=queue.branch.walk_in_curr_queue_number,
        invoices=invoices,
        invoice=invoices[0] if invoices else None,
        prescriptions=prescriptions,
        documents=documents,
        allow_add_dependants=allow_add_dependants,
        last_update=sg_datetime.sg(queue.updated_at).strftime("%I:%M%p") if queue.status == WalkinQueueStatus.CHECKED_IN else None,
    )

class CancelResp(BaseModel):
    id: str

@router.get('/cancel', response_model=CancelResp)
def cancel_walkin(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    ids = user.get_linked_account_ids()
    
    queue = db.query(WalkInQueue).filter(
            WalkInQueue.account_id.in_(ids),
            WalkInQueue.status.in_([WalkinQueueStatus.PENDING, WalkinQueueStatus.CHECKED_IN])
        ).first()
    
    queues = None
    if queue:
        queues = get_grouped_walkins(db, queue, user)

    if not queue or not queues:
        raise HTTPException(status_code=404, detail="Queue not found")

    for q in queues:
        # For Pending State
        if q.status == WalkinQueueStatus.PENDING:
            cancel_pending_queue(q.sgimed_pending_queue_id)
        # For Checked In State
        if q.status == WalkinQueueStatus.CHECKED_IN and q.sgimed_visit_id:
            update_queue_instructions(q.sgimed_visit_id, WalkinQueueStatus.CANCELLED.value)
        
        # Cancel the queue in SGiMed
        q.status = WalkinQueueStatus.CANCELLED
        q.queue_status = "Cancelled"
    db.commit()

    return CancelResp(id=str(queue.id))

def get_family_queues(user: Account, db: Session):
    queue = db.query(WalkInQueue).filter(
        or_(WalkInQueue.account_id == user.id, WalkInQueue.created_by == user.id),
        WalkInQueue.status == WalkinQueueStatus.CHECKED_IN
    ).first()

    if not queue:
        logging.error(f"Walkin Queue Family: Queue record not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Queue not found")
    
    queues = get_grouped_walkins(db, queue, user)    
    return queues

class FamilyInQueueRow(BaseModel):
    id: str
    name: str
    # in_queue: bool

@router.get('/family', response_model=list[FamilyInQueueRow])
def get_family(user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    queues = get_family_queues(user, db)
    in_queue_ids = [q.account_id for q in queues]
    
    records = []
    if user.id not in in_queue_ids:
        records.append(
            FamilyInQueueRow(
                id=str(user.id),
                name='Myself'
            )
        )

    for fm in user.family_members:
        if fm.nok_account.id not in in_queue_ids:
            records.append(
                FamilyInQueueRow(
                    id=str(fm.nok_account.id),
                    name=f"{fm.nok_account.name} ({fm.relation.value})"
                )
            )

    return records

class AddFamilyReq(BaseModel):
    patient_ids: list[str]
    
@router.post('/family', response_model=SuccessResp)
def add_family(req: AddFamilyReq, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    queues = get_family_queues(user, db)
    # If group_id is None, make sure the first record is updated with group_id
    q = queues[0]
    if not q.group_id:
        group_id = str(uuid.uuid4())
        q.group_id = group_id
        q.index = 0
        q.created_by = str(user.id)

    # Validate that patient_ids to be added are all valid and not yet added to the queue already
    available_user_ids = set(user.get_linked_account_ids()) - set([str(q.account_id) for q in queues])
    if len(set(req.patient_ids) - available_user_ids) > 0:
        logging.error(f"Walkin Add Family: Invalid patients selected. User ID: {user.id}, Patient IDs: {req.patient_ids}")
        raise HTTPException(status_code=400, detail="Invalid patients selected")
    
    # Retrieve the patient accounts
    patients = db.query(Account).filter(Account.id.in_(req.patient_ids)).all()
    for i, patient in enumerate(patients):
        upsert_patient_in_sgimed(db, patient, branch=q.branch)
        if not patient.sgimed_patient_id:
            raise HTTPException(status_code=400, detail="Failed to create queue. Please contact customer support if error persists")

        # Create queue in SGiMed    
        visit_id, queue_number = create_sgimed_walkin_queue(
            patient.sgimed_patient_id,
            q.branch.sgimed_branch_id,
            q.get_sgimed_appointment_type_id(db)
        )

        # Create database record
        new_queue = WalkInQueue(
            branch_id=q.branch_id,
            account_id=patient.id,
            queue_number=queue_number,
            sgimed_visit_id=visit_id,
            sgimed_pending_queue_id='', # For Checked In, directly added to the queue
            service=q.service,
            status=q.status,
            queue_status=q.status,
            group_id=q.group_id,
            index=len(queues) + i,
            created_by=q.created_by,
            checkin_time=sg_datetime.now(),
        )
        db.add(new_queue)
    db.commit()
    
    return SuccessResp(success=True)

@router.get('/invoice', response_model=DocumentHtml)
def get_invoice(id: str, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    record = db.query(Document).filter(
            Document.id == id,
            Document.hidden == False,
            Document.document_type == DocumentType.INVOICE,
            Document.sgimed_patient_id.in_(user.get_linked_sgimed_patient_ids()),
        ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return get_invoice_document_html(record.sgimed_document_id)

@router.get('/mc', response_model=DocumentHtml)
def get_mc(id: str, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    record = db.query(Document).filter(
            Document.id == id,
            Document.hidden == False,
            Document.document_type == DocumentType.MC,
            Document.sgimed_patient_id.in_(user.get_linked_sgimed_patient_ids()),
        ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Medical Certificate not found")

    return get_mc_document_html(record.sgimed_document_id)
