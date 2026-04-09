from datetime import datetime, timedelta, time as dt_time
import logging
import time
from typing import Literal, Optional
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
import jwt
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from config import SGIMED_SA_PCP_BRANCH_ID, ZOOM_APP_KEY, ZOOM_APP_SECRET
from models import get_db
from models.model_enums import CollectionMethod, DayOfWeek, FileViewerType, PatientType, TeleconsultStatus
from models.patient import Account
from models.payments import CorporateCode, PaymentMethod
from models.pinnacle import Branch, Content
from models.teleconsult import Teleconsult
from repository.family_nok import get_patients
from services.user import user_is_pcp
from routers.patient.actions.teleconsult_utils import get_grouped_teleconsults, user_triggered_queue_status_change
from repository.payments import PaymentMethodDetail, create_postpayment_record, create_prepayment, get_default_payment
from repository.teleconsult import upsert_teleconsult
from routers.patient.actions.teleconsult_flow_backend import prepayment_success_webhook
from routers.patient.teleconsult import TeleconsultPaymentResp
from routers.patient.utils import validate_firebase_token, validate_user
from services.visits import DocumentHtml, get_invoice_document_html, get_mc_document_html
from utils.fastapi import SuccessResp
from utils.sg_datetime import sg
from utils.system_config import TeleconsultWarningMessage, get_delivery_require_branch_picker, get_teleconsult_warning_message, get_telemed_app_branch
from utils import sg_datetime
from services.teleconsult import combine_breakdown_with_gst, fetch_prepayment_rate, PaymentBreakdown, PaymentTotal
from utils.supabase_s3 import SignedURLResponse
from routers.delivery.actions.delivery import retrieve_delivery_note_action_with_signed_url

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class PrepaymentRateReq(BaseModel):
    code: Optional[str] = None
    family_ids: list[str] = []
    include_user: bool

class PrepaymentRateResp(BaseModel):
    is_pcp: bool = False # This allows the frontend to use DEFERRED_PAYMENT to pay only after the consult
    code: Optional[str] = None
    breakdown: list[PaymentBreakdown]
    total: float
    address: str
    user_allergy: Optional[str] = None
    allergies: dict
    tnc: str
    payment_method: PaymentMethodDetail
    collection_method_messages: Optional[dict[str, str]] = None
    require_branch_picker_methods: list[str] = ['delivery', 'pickup']

@router.post('/prepayment/rate', response_model=PrepaymentRateResp)
def get_rate(req: PrepaymentRateReq, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    patients = get_patients(db, user, req.include_user, req.family_ids)
    if not patients:
        raise HTTPException(status_code=400, detail="Invalid patients")

    is_pcp = False
    rate_code = None
    subtotals: list[PaymentTotal] = []
    for patient in patients:
        is_pcp, _rate_code, subtotal = fetch_prepayment_rate(db, patient.nric, req.code)
        if _rate_code == req.code:
            rate_code = _rate_code
        # if is_pcp and req.family_ids:
        #     raise HTTPException(status_code=400, detail="PCP rate cannot be used with family members")

        subtotals.append(subtotal)
    
    total = combine_breakdown_with_gst(subtotals)

    # Get the TnC text
    tnc = db.query(Content).filter(Content.id == 'teleconsult_prepayment').first()
    tnc = tnc.content if tnc else ''

    # Get collection method messages depending on time of day
    # curr_hour = sg_datetime.now().hour
    # collection_method_messages = None
    # if curr_hour >= 18:  # After 6pm
    collection_method_messages = {
        "delivery": "Kindly note :\n- A $9 (before GST) fee will apply.\n- Delivery orders placed after 9 pm on weekdays and after 7 pm on weekends and Public Holidays will be processed on the next business day."
    }

    return PrepaymentRateResp(
        is_pcp=is_pcp,
        code=rate_code,
        breakdown=total.breakdown,
        total=total.total,
        address=user.get_address(),
        user_allergy=user.allergy,
        allergies={ p.id: p.allergy for p in patients if p.id != user.id },
        tnc=tnc,
        payment_method=get_default_payment(db, user),
        collection_method_messages=collection_method_messages,
        require_branch_picker_methods=get_delivery_require_branch_picker(db, user)
    )

class AvailableBranch(BaseModel):
    id: str
    name: str
    category: str
    availability: str
    msg_key: Optional[str] = "default"

class AvailableBranchesResp(BaseModel):
    messages: dict[str, str] = {
        # Delivery - Legacy code since Delivery does not have Branch Picker
        "delivery_default": "Kindly note the following:\n[]()\n1\\. A $9 (before GST) fee will apply.\n[]()\n2\\. Delivery orders placed after 9 pm on weekdays and after 7 pm on weekends and Public Holidays will be processed on the next business day.",
        "delivery_clinic_closed": "Kindly note the following:\n[]()\n1\\. A $9 (before GST) fee will apply.\n[]()\n2\\. Delivery orders placed after 9 pm on weekdays and after 7 pm on weekends and Public Holidays will be processed on the next business day.",
        # Pickup
        "pickup_default": "Kindly note the following:\n[]()\n1\\. Your selected clinic will serve as the location where you collect your medications.",
        "pickup_clinic_closed": "Kindly note the following:\n[]()\n1\\. Your selected clinic will serve as the location where you collect your medications.\n[]()\n**Clinic is currently closed, pick up is only available during clinic operating hours**"
    }
    branches: list[AvailableBranch]

@router.get('/branches', response_model=AvailableBranchesResp)
def get_available_branches(mode: CollectionMethod = CollectionMethod.DELIVERY, db: Session = Depends(get_db)):
    branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False).all()
    curr_dt = sg_datetime.now()
    
    def map_branch(branch: Branch):
        availability = 'Closed'
        msg_key = f'{mode.value}_clinic_closed'
        operating = branch.is_operating(db, curr_dt, mode)
        if operating:
            print(branch.id, branch.name, "Current Operating Hour")
            availability = 'Same Day'
            msg_key = f'{mode.value}_default'
        else:
            operating = branch.get_next_operating_hour(db, curr_dt, mode)
            if operating:
                availability = 'Same Day'
                msg_key = f'{mode.value}_default'
            else:
                for i in range(1, 4):
                    next_dt = curr_dt + timedelta(days=i)
                    next_dt = datetime.combine(next_dt.date(), dt_time()) # Starting at midnight
                    operating = branch.get_next_operating_hour(db, next_dt, mode)
                    if operating:
                        availability = list(DayOfWeek)[next_dt.weekday()].value
                        break

        return AvailableBranch(
            id=str(branch.id),
            name=branch.name,
            category=branch.category,
            availability=availability,
            msg_key=msg_key
        )

    return AvailableBranchesResp(
        branches=[map_branch(branch) for branch in branches]
    )

class JoinQueueReq(BaseModel):
    family_ids: list[str] = []
    include_user: bool
    code: Optional[str] = None
    branch_id: Optional[str] = None
    user_allergy: Optional[str] = None
    allergies: dict = {}
    payment_method: Optional[PaymentMethod] = None
    collection_method: Optional[CollectionMethod] = None

class JoinQueueResp(BaseModel):
    prepayment_required: bool
    payment_provider_params: dict
    redirect_pathname: Optional[Literal['/teleconsult/prepayment/stripe_paynow', '/payments/2c2p/payment_cvc', '/teleconsult/prepayment/stripe_card']] = None

def check_teleconsult_exists(db: Session, user: Account):
    # If Teleconsult is ongoing, created by user. Redirect to Teleconsult
    record = db.query(Teleconsult.id).filter(
            or_(
                Teleconsult.account_id == str(user.id),
                Teleconsult.created_by == str(user.id)
            ),
            Teleconsult.status.not_in([
                TeleconsultStatus.PREPAYMENT,
                TeleconsultStatus.CHECKED_OUT,
            ])
        ).first()
    
    return record is not None

@router.post('/queue/join', response_model=JoinQueueResp)
def join_queue(req: JoinQueueReq, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    # If there is an ongoing session, redirect user to Teleconsult.
    if check_teleconsult_exists(db, user):
        return JoinQueueResp(
            prepayment_required=False,
            payment_provider_params={}
        )

    # Not requesting for self and family members
    if not req.include_user and not req.family_ids:
        raise HTTPException(status_code=400, detail="Invalid request")

    # Retreive all the patients involved. User is always the first patient
    patients = get_patients(db, user, req.include_user, req.family_ids)
    if not patients:
        raise HTTPException(status_code=400, detail="Invalid patients")

    # Get user address
    address = user.get_address()

    # Group ID is used to group teleconsult records
    group_id = None
    if req.family_ids:
        group_id = str(uuid.uuid4())

    # Fetch Branch. For PCP users, the branch is fixed
    branch = None
    if user_is_pcp(db, user.nric):
        if not req.include_user or len(patients) > 1:
            raise HTTPException(status_code=400, detail="PCP rate cannot be used with family members")
        branch = db.query(Branch).filter(Branch.id == SGIMED_SA_PCP_BRANCH_ID).first()
    elif not req.collection_method:
        raise HTTPException(status_code=400, detail="Collection method is required")
    else:
        branch = get_telemed_app_branch(db, user, req.collection_method,req.branch_id)

    if not branch:
        raise HTTPException(status_code=400, detail="Branch not found")
    
    # Check if prepayment is required
    def check_prepayment(code):
        prepayment_required = True
        if req.code:
            code = db.query(CorporateCode).filter(
                    CorporateCode.code == code.upper(),
                    CorporateCode.skip_prepayment == True,
                    CorporateCode.deleted == False,
                ).first()
            if code:
                prepayment_required = False
        return prepayment_required


    prepayment_required = check_prepayment(req.code)

    # Create Teleconsult records
    teleconsults: list[Teleconsult] = []
    rates: list[PaymentTotal] = []
    rate_code = None
    for ind, patient in enumerate(patients):
        # Update Account Allergy
        patient.allergy = req.allergies.get(str(patient.id), None) if patient.id != user.id else req.user_allergy
        # Create new teleconsult record
        is_pcp, rate_code, subtotal = fetch_prepayment_rate(db, patient.nric, req.code)
        payment_total = combine_breakdown_with_gst([subtotal])
        rates.append(payment_total)
        # # PCP accounts are assigned to a specific branch. All others are assigned to selected branch
        # if not is_pcp and not req.branch_id:
        #     raise HTTPException(400, "Invalid teleconsult. Please select a branch")
        
        patient_type = PatientType.MIGRANT_WORKER if is_pcp else PatientType.PRIVATE_PATIENT
        teleconsult = upsert_teleconsult(
            db,
            patient,
            patient_type,
            patient.allergy,
            rate_code,
            payment_total,
            address,
            str(branch.id), 
            CollectionMethod.DELIVERY if is_pcp else req.collection_method,
            group_id,
            ind if group_id else None,
            str(user.id) if group_id else None
        )
        teleconsults.append(teleconsult)
    
    # Create Payment records and transaction with payment provider
    try:
        payment_method = req.payment_method if prepayment_required else PaymentMethod.DEFERRED_PAYMENT
        payment_method_id = None
        if not payment_method:
            default_payment = get_default_payment(db, user)
            payment_method = default_payment.method
            payment_method_id = default_payment.id

        payments, payment_provider_params = create_prepayment(
            db,
            user,
            teleconsults,
            rates,
            payment_method,
            payment_method_id,
            rate_code
        ) 
    except Exception as e:
        raise HTTPException(status_code=500, detail=e)

    if not prepayment_required:
        prepayment_success_webhook(db, payments)

    redirect_pathnames: dict[PaymentMethod, Literal['/teleconsult/prepayment/stripe_paynow', '/payments/2c2p/payment_cvc', '/teleconsult/prepayment/stripe_card']] = {
        PaymentMethod.PAYNOW_STRIPE: '/teleconsult/prepayment/stripe_paynow',
        PaymentMethod.CARD_2C2P: '/payments/2c2p/payment_cvc',
        PaymentMethod.CARD_STRIPE: '/teleconsult/prepayment/stripe_card',
    }

    # Return Payment Parameters
    return JoinQueueResp(
        prepayment_required=prepayment_required,
        payment_provider_params=payment_provider_params,
        redirect_pathname=redirect_pathnames.get(payment_method, '/teleconsult/prepayment/stripe_paynow')
    )

class PrescriptionDict(BaseModel):
    item_name: str
    instructions: str
    precautions: str
    subtitle: Optional[str] = None

class DocumentDict(BaseModel):
    id: str
    filetype: FileViewerType
    icon: str = 'document'
    title: str
    url: str
    filename: str
    subtitle: Optional[str] = None

class TeleconsultResp(BaseModel):
    id: str
    time_subtitle: str
    status: TeleconsultStatus
    queue_status: str
    payment_breakdown: list[PaymentBreakdown]
    payments: list[TeleconsultPaymentResp]
    total: float
    balance: float
    address: str
    allow_address_change: bool
    # Consult Start & Ended
    room_id: Optional[str] = None
    doctor: Optional[str] = None
    # Consult Ended 
    invoices: list[DocumentDict]
    prescriptions: list[PrescriptionDict] = []
    documents: list[DocumentDict] = []
    hide_invoice: bool
    collection_method: Optional[CollectionMethod] = None
    branch_name: str
    allergies: list[str] = []
    allow_add_dependants: bool

def get_teleconsult_resp(db: Session, user: Account, teleconsult_id: Optional[str] = None) -> Optional[TeleconsultResp]:
    family_ids = user.get_linked_account_ids()
    # This is because for SSE as it is always ongoing, it should not maintain a database connection
    teleconsult = None
    if teleconsult_id:
        teleconsult = db.query(Teleconsult).filter(            
            Teleconsult.id == teleconsult_id,
            or_(
                Teleconsult.account_id == user.id,
                and_(
                    Teleconsult.created_by == user.id,
                    Teleconsult.account_id.in_(family_ids)
                )
            )
        ).first()
    # Fetching latest record to be processed
    else:
        teleconsult = db.query(Teleconsult).filter(
            Teleconsult.account_id.in_(family_ids),
            Teleconsult.status.not_in([TeleconsultStatus.PREPAYMENT, TeleconsultStatus.CHECKED_OUT]),
        ).order_by(Teleconsult.updated_at.desc()).first()

    if not teleconsult:
        print("Not Found")
        return None
    
    teleconsults = get_grouped_teleconsults(db, teleconsult, user)
    if not teleconsults:
        raise HTTPException(500, 'Failed to get grouped teleconsults')

    # Setup all the post documents
    invoices = []
    hide_invoice = False
    prescriptions = []
    documents = []
    if teleconsult.status in [TeleconsultStatus.OUTSTANDING, TeleconsultStatus.CHECKED_OUT] and teleconsult.invoices:
        # If invoice is hidden it should not be shown
        hide_invoice = teleconsult.invoices[0].hide_invoice
        if not hide_invoice:
            invoices = [
                DocumentDict(
                    id=f'invoice-{str(t.id)}',
                    title="Invoice",
                    url=f"/api/teleconsult/v2/invoice?id={t.id}",
                    filename="Invoice.pdf",
                    subtitle=f"For {t.account.name}" if t.group_id else None,
                    filetype=FileViewerType.HTML,
                )
                for t in teleconsults
                if t.invoices
            ]
        # Populate Prescriptions & MC if available when status is CHECKED_OUT
        # if teleconsult.status == TeleconsultStatus.CHECKED_OUT:
        if teleconsult.invoices[0].show_details:
            prescriptions = [
                PrescriptionDict(
                    item_name=p['item_name'] if 'item_name' in p else '',
                    instructions=p['instructions'] if 'instructions' in p else '',
                    precautions=p['precautions'] if 'precautions' in p else '',
                    subtitle=f'For {t.account.name}' if t.group_id else None
                )
                for t in teleconsults if t.invoices
                for p in t.invoices[0].prescriptions
            ]

            documents = [
                DocumentDict(
                    id=f'mc-{t.id}',
                    icon="mc",
                    title="Medical Certificate (MC)",
                    url=f"/api/teleconsult/v2/mc?id={t.id}",
                    filename="Medical Certificate.pdf",
                    subtitle=f'For {t.account.name}' if t.group_id else None,
                    filetype=FileViewerType.HTML,
                )
                for t in teleconsults
                if t.invoices and t.invoices[0].mc_html
            ]
            
    if teleconsult.teleconsult_delivery and teleconsult.teleconsult_delivery.is_delivery_note_exists:
        documents += [
            DocumentDict(
                id=f'delivery-note-{str(teleconsult.id)}',
                icon="document",
                title="Delivery Note",
                url=f"/api/teleconsult/v2/delivery_note?id={teleconsult.id}",
                filename="Delivery Note.pdf",
                filetype=FileViewerType.URL,
            )
        ]

    time_subtitle = f'Checked In: {sg(teleconsult.checkin_time).strftime("%d %b %Y, %I:%M%p")}'
    if teleconsult.checkout_time:
        time_subtitle = f'Checked Out: {sg(teleconsult.checkout_time).strftime("%d %b %Y, %I:%M%p")}'
    elif teleconsult.teleconsult_end_time:
        time_subtitle = f'Consult Ended: {sg(teleconsult.teleconsult_end_time).strftime("%d %b %Y, %I:%M%p")}'
    elif teleconsult.teleconsult_start_time:
        time_subtitle = f'Consult Started: {sg(teleconsult.teleconsult_start_time).strftime("%d %b %Y, %I:%M%p")}'

    if teleconsult.group_id and not (len(teleconsults) == 1 and teleconsults[0].account_id == user.id):
        time_subtitle += '\nConsultation For: **' + ' '.join([t.account.name.strip() if t.account_id != user.id else 'Myself' for t in teleconsults]) + '**'

    total = sum([t.total for t in teleconsults])
    balance = sum([t.balance for t in teleconsults])

    # OUTSTANDING and CHECKED_OUT state can differ as this is dependant on the SGiMed invoice webhook
    status = teleconsult.status
    queue_status = teleconsult.queue_status
    if teleconsult.status in [TeleconsultStatus.OUTSTANDING, TeleconsultStatus.CHECKED_OUT]:
        # If any of the teleconsult is in consult end, then the status should be consult end
        if any(t.status in [TeleconsultStatus.CONSULT_END, TeleconsultStatus.CHECKED_IN] for t in teleconsults):
            status = TeleconsultStatus.CONSULT_END
            queue_status = 'Preparing prescription and MC (if any)'
        # If any of the teleconsult is in outstanding, then the status should be outstanding
        elif any(t.status == TeleconsultStatus.OUTSTANDING for t in teleconsults): 
            status = TeleconsultStatus.OUTSTANDING
            queue_status = 'Please make payment'

    payment_breakdown = []
    if not hide_invoice:
        if not teleconsult.group_id:
            payment_breakdown = [
                PaymentBreakdown.model_validate(row)
                for row in teleconsult.payment_breakdown
            ]
        else:
            payment_breakdown = combine_breakdown_with_gst([
                PaymentTotal(breakdown=[PaymentBreakdown.model_validate(row) for row in t.payment_breakdown], total=t.total)
                for t in teleconsults
            ]).breakdown

    # Fetch payments
    payments = []
    payments_dict = {}
    for t in teleconsults:
        for payment in t.get_successful_payments():
            if payment.payment_method == PaymentMethod.DEFERRED_PAYMENT:
                continue
            if payment.payment_id not in payments_dict:
                payments_dict[payment.payment_id] = TeleconsultPaymentResp(
                    payment_amount=0.0,
                    payment_method=payment.payment_method,
                    remarks=payment.remarks,
                    updated_at=payment.updated_at
                )

            payments_dict[payment.payment_id].payment_amount += payment.payment_amount

    payments = sorted(payments_dict.values(), key=lambda x: x.updated_at)
    allergies = [f"{t.account.name} - {t.allergy}" for t in teleconsults if t.allergy]

    # Check if allow add dependants
    allow_add_dependants = False
    if status == TeleconsultStatus.CHECKED_IN and not user_is_pcp(db, user.nric):
        # Check has Family Members and if all already added
        active_queue_acc_ids = [q.account_id for q in teleconsults]
        family_member_acc_ids = [fm.nok_id for fm in user.family_members]
        allow_add_dependants = len(set(family_member_acc_ids) - set(active_queue_acc_ids)) > 0

    return TeleconsultResp(
        id=str(teleconsult.id),
        time_subtitle=time_subtitle,
        status=status,
        queue_status=queue_status,
        doctor=teleconsult.doctor.name if teleconsult.doctor_id else None,
        payment_breakdown=payment_breakdown,
        payments=payments,
        total=total,
        balance=balance,
        address=teleconsult.address,
        allow_address_change=status != TeleconsultStatus.CHECKED_OUT,
        invoices=invoices,
        prescriptions=prescriptions,
        documents=documents,
        hide_invoice=hide_invoice,
        collection_method=teleconsult.collection_method,
        branch_name=teleconsult.branch.name,
        allergies=allergies,
        allow_add_dependants=allow_add_dependants,
    )

# This endpoint is just for getting teleconsult record
@router.get('/details', response_model=TeleconsultResp)
def get_details(id: Optional[str] = None, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    resp = get_teleconsult_resp(db, user, id)
    if not resp:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    return resp

class CancelParams(BaseModel):
    id: str

@router.post('/cancel', response_model=SuccessResp)
def cancel_teleconsult(params: CancelParams, background_tasks: BackgroundTasks, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(
            Teleconsult.id == params.id, 
            or_(Teleconsult.account_id == str(user.id), Teleconsult.created_by == str(user.id)), 
            Teleconsult.status.in_([TeleconsultStatus.CHECKED_IN, TeleconsultStatus.MISSED])
        ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    teleconsults = get_grouped_teleconsults(db, record, user)
    for teleconsult in teleconsults:
        teleconsult.status = TeleconsultStatus.CANCELLED
        teleconsult.queue_status = "You may wish to join the queue again"

    db.commit()
    for teleconsult in teleconsults:
        background_tasks.add_task(user_triggered_queue_status_change, str(teleconsult.id))
    return SuccessResp(success=True)

class RejoinParams(BaseModel):
    id: str

@router.post('/rejoin', response_model=SuccessResp)
def rejoin_teleconsult(params: RejoinParams, background_tasks: BackgroundTasks, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(
            Teleconsult.id == params.id,
            or_(Teleconsult.account_id == str(user.id), Teleconsult.created_by == str(user.id)),
            Teleconsult.status.in_([TeleconsultStatus.MISSED, TeleconsultStatus.CANCELLED])
        ).first()
    if not record:
        log_record = db.query(Teleconsult).filter(Teleconsult.id == params.id).first()
        logging.error(f"Teleconsult not found. User ID: {user.id}, Teleconsult ID: {params.id}, Status: {log_record.status if log_record else None}")
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    teleconsults = get_grouped_teleconsults(db, record, user)
    for teleconsult in teleconsults:
        teleconsult.additional_status = teleconsult.status
        teleconsult.status = TeleconsultStatus.CHECKED_IN
        teleconsult.queue_status = "Please wait for your turn"
        teleconsult.doctor_id = None
        teleconsult.notifications_sent = []
        teleconsult.teleconsult_start_time = None
        teleconsult.teleconsult_join_time = None
        teleconsult.teleconsult_end_time = None
        teleconsult.checkin_time = sg_datetime.now()
    db.commit()
    
    for teleconsult in teleconsults:
        background_tasks.add_task(user_triggered_queue_status_change, str(teleconsult.id))

    return SuccessResp(success=True)

def get_family_queues(user: Account, db: Session):
    queue = db.query(Teleconsult).filter(
        or_(Teleconsult.account_id == user.id, Teleconsult.created_by == user.id),
        Teleconsult.status == TeleconsultStatus.CHECKED_IN
    ).first()

    if not queue:
        logging.error(f"Teleconsult Family: Queue record not found for user {user.id}")
        raise HTTPException(status_code=404, detail="Queue not found")
    
    queues = get_grouped_teleconsults(db, queue, user)    
    return queues

class FamilyInTeleconsultRow(BaseModel):
    id: str
    name: str
    allergy: Optional[str] = None
    # in_queue: bool

@router.get('/family', response_model=list[FamilyInTeleconsultRow])
def get_family(user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    queues = get_family_queues(user, db)
    in_queue_ids = [q.account_id for q in queues]
    
    records = []
    if user.id not in in_queue_ids:
        records.append(
            FamilyInTeleconsultRow(
                id=str(user.id),
                name='Myself',
                allergy=user.allergy
            )
        )

    for fm in user.family_members:
        if fm.nok_account.id not in in_queue_ids:
            records.append(
                FamilyInTeleconsultRow(
                    id=str(fm.nok_account.id),
                    name=f"{fm.nok_account.name} ({fm.relation.value})",
                    allergy=fm.nok_account.allergy
                )
            )

    return records


class AddFamilyReq(BaseModel):
    patient_ids_allergies: dict
    
@router.post('/family', response_model=SuccessResp)
def add_family(req: AddFamilyReq, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    patient_ids = list(req.patient_ids_allergies.keys())
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
    if len(set(patient_ids) - available_user_ids) > 0:
        logging.error(f"Teleconsult Add Family: Invalid patients selected. User ID: {user.id}, Patient IDs: {patient_ids}")
        raise HTTPException(status_code=400, detail="Invalid patients selected")
    
    # Retrieve the patient accounts
    patients = db.query(Account).filter(Account.id.in_(patient_ids)).all()
    teleconsults = []
    rates = []
    rate_code = None
    for i, patient in enumerate(patients):
        # Update Account Allergy
        patient.allergy = req.patient_ids_allergies.get(str(patient.id), None)
        # Create new teleconsult record
        is_pcp, rate_code, subtotal = fetch_prepayment_rate(db, patient.nric, q.corporate_code)
        payment_total = combine_breakdown_with_gst([subtotal])
        rates.append(payment_total)
        # Create Record
        patient_type = PatientType.PRIVATE_PATIENT
        teleconsult = upsert_teleconsult(
            db,
            patient,
            patient_type,
            patient.allergy,
            rate_code,
            payment_total,
            q.address,
            str(q.branch.id), 
            q.collection_method,
            q.group_id,
            len(queues) + i,
            q.created_by
        )
        teleconsults.append(teleconsult)
        
    # Create payment records and add queues into SGiMed
    payments, payment_provider_params = create_prepayment(
        db,
        user,
        teleconsults,
        rates,
        PaymentMethod.DEFERRED_PAYMENT,
        None,
        rate_code,
        existing_teleconsult_session=True
    )
    prepayment_success_webhook(db, payments)

    return SuccessResp(success=True)

class VideoParams(BaseModel):
    id: str
class VideoResp(BaseModel):
    sessionName: str
    token: str
    userName: str
    # sessionPassword: Optional[str]
    sessionIdleTimeoutMins: int
    audioOptions: dict
    videoOptions: dict
    elapsed_time: int
    warning_config: Optional[TeleconsultWarningMessage] = None
    clinic_info: Optional[str] = None

def get_token(session_name: str):
    try:
        iat = int(time.time()) - 60  # 1 minute before
        exp = iat + 60 * 60 * 1  # 1 hour expiry
        payload = {
            'app_key': ZOOM_APP_KEY,
            'version': 1,
            # 'user_identity': user.name,
            'iat': iat,
            'exp': exp,
            'tpc': session_name,
            'role_type': 1,
            'cloud_recording_option': 1,
        }
        
        print(payload)

        token = jwt.encode(
            payload,
            ZOOM_APP_SECRET,
            algorithm='HS256'
        )
        return token
    except Exception as e:
        print(e)
        return None

@router.post('/video', response_model=VideoResp)
def get_video_token(params: VideoParams, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    # For Test Account only
    if params.id == 'test':
        session_name = 'test'
        token = get_token(session_name)
        if not token:
            raise HTTPException(status_code=500, detail="Failed to generate token")

        return VideoResp(
            sessionName=session_name,
            # sessionPassword="",
            token=token,
            userName=user.name,
            audioOptions={ "connect": True, "mute": False, "autoAdjustSpeakerVolume": False },
            videoOptions={ "localVideoOn": True },
            sessionIdleTimeoutMins=10,
            elapsed_time=0,
            warning_config=None,
            clinic_info="Consulting with Dr Test Doctor\nPinnacle Family Clinic (Test)",
        )
    
    record = None
    try:    
        record = db.query(Teleconsult).filter(
            Teleconsult.id == params.id,
            or_(Teleconsult.account_id == str(user.id), Teleconsult.created_by == str(user.id)), 
            Teleconsult.status == TeleconsultStatus.CONSULT_START
        ).first()
    except Exception:
        logging.error(f"Failed to get teleconsult. ID: {params.id}, User ID: {user.id}")

    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    # Calculate elapsed time and update teleconsult_join_time
    elapsed_time = 0
    if record.teleconsult_join_time:
        elapsed_time = int((sg_datetime.now() - sg(record.teleconsult_join_time)).total_seconds())
    else:
        record.teleconsult_join_time = sg_datetime.now()
        db.commit()

    session_name = str(record.group_id if record.group_id else record.id)
    print(f"Patient Zoom Room: {session_name}")
    
    token = get_token(session_name)
    if not token:
        raise HTTPException(status_code=500, detail="Failed to generate token")
    
    # Get warning config
    warning_config = get_teleconsult_warning_message(db)
    
    # Format clinic info
    clinic_info = None
    if record.doctor_id and record.doctor:
        doctor_name = record.doctor.name
        # Check if branch exists and is not hidden
        if record.branch_id and record.branch and not record.branch.hidden:
            clinic_name = record.branch.name
        else:
            clinic_name = "Pinnacle Family Clinic"
        clinic_info = f"Consulting with Dr {doctor_name}\n{clinic_name}"
    
    return VideoResp(
            sessionName=session_name,
            # sessionPassword="",
            token=token,
            userName=user.name,
            audioOptions={ "connect": True, "mute": False, "autoAdjustSpeakerVolume": False },
            videoOptions={ "localVideoOn": True },
            sessionIdleTimeoutMins=10,
            elapsed_time=elapsed_time,
            warning_config=warning_config,
            clinic_info=clinic_info,
        )

@router.get('/invoice', response_model=DocumentHtml)
def get_invoice(id: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(
        Teleconsult.id == id,
        Teleconsult.account_id.in_(user.get_linked_account_ids()),
    ).first()
    if not record or not record.invoices:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    if record.invoices[0].hide_invoice:
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    return get_invoice_document_html(record.invoices[0].invoice_html)

@router.get('/mc', response_model=DocumentHtml)
def get_mc(id: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(
        Teleconsult.id == id,
        Teleconsult.account_id.in_(user.get_linked_account_ids()),
    ).first()
    if not record or not record.invoices or not record.invoices[0].mc_html:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    return get_mc_document_html(record.invoices[0].mc_html)

@router.get("/delivery_note", response_model=SignedURLResponse)
async def retrieve_delivery_note_route(id: str, user: Account = Depends(validate_user), db: Session = Depends(get_db)):
    try:
        teleconsult = db.query(Teleconsult).filter(
            Teleconsult.id == id,
            Teleconsult.account_id.in_(user.get_linked_account_ids()),
        ).first()
        if not teleconsult or not teleconsult.teleconsult_delivery or not teleconsult.teleconsult_delivery.is_delivery_note_exists or not teleconsult.teleconsult_delivery.delivery_note_file_path:
            raise HTTPException(status_code=404, detail="Invalid request")

        data = retrieve_delivery_note_action_with_signed_url(teleconsult.teleconsult_delivery.delivery_note_file_path)
        return data
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreatePostpaymentReq(BaseModel):
    id: str
    payment_method: Optional[PaymentMethod] = None

# Legacy Endpoint for v1.3.1 and below
@router.post('/postpayment/create', response_model=dict)
def create_postpayment(req: CreatePostpaymentReq, user = Depends(validate_user), db: Session = Depends(get_db)):
    user_id = str(user.id)
    teleconsult = db.query(Teleconsult).filter(
            Teleconsult.id == req.id,
            or_(Teleconsult.account_id == user_id, Teleconsult.created_by == user_id)
        ).first()
    if not teleconsult:
        raise HTTPException(status_code=404, detail="Record not found")
    # if not teleconsult.balance or teleconsult.status != TeleconsultStatus.OUTSTANDING:
    #     raise HTTPException(status_code=400, detail="Not outstanding teleconsult")    

    teleconsults = get_grouped_teleconsults(db, teleconsult, user)

    payment_method = req.payment_method if req.payment_method else PaymentMethod.PAYNOW_STRIPE
    payments, payment_provider_params = create_postpayment_record(db, user, teleconsults, payment_method)
    return payment_provider_params

class CreatePostpaymentV2Req(BaseModel):
    id: str

class CreatePostpaymentResp(BaseModel):
    payment_provider_params: dict
    redirect_pathname: Optional[Literal['/teleconsult/postpayment/stripe_paynow', '/payments/2c2p/payment_cvc', '/teleconsult/postpayment/stripe_card']] = None

@router.post('/postpayment/v2/create', response_model=CreatePostpaymentResp)
def create_postpayment_v2(req: CreatePostpaymentV2Req, user = Depends(validate_user), db: Session = Depends(get_db)):
    user_id = str(user.id)
    teleconsult = db.query(Teleconsult).filter(
            Teleconsult.id == req.id,
            or_(Teleconsult.account_id == user_id, Teleconsult.created_by == user_id)
        ).first()
    if not teleconsult:
        raise HTTPException(status_code=404, detail="Record not found")

    # if not teleconsult.balance or teleconsult.status != TeleconsultStatus.OUTSTANDING:
    #     raise HTTPException(status_code=400, detail="Not outstanding teleconsult")    

    teleconsults = get_grouped_teleconsults(db, teleconsult, user)
    default_payment = get_default_payment(db, user)
    payment_method = default_payment.method
    payment_method_id = default_payment.id
    
    payments, payment_provider_params = create_postpayment_record(db, user, teleconsults, payment_method, payment_method_id)
    redirect_pathnames: dict[PaymentMethod, Literal['/teleconsult/postpayment/stripe_paynow', '/payments/2c2p/payment_cvc', '/teleconsult/postpayment/stripe_card']] = {
        PaymentMethod.PAYNOW_STRIPE: '/teleconsult/postpayment/stripe_paynow',
        PaymentMethod.CARD_STRIPE: '/teleconsult/postpayment/stripe_card',
        PaymentMethod.CARD_2C2P: '/payments/2c2p/payment_cvc',
    }
    return CreatePostpaymentResp(
        payment_provider_params=payment_provider_params,
        redirect_pathname=redirect_pathnames.get(payment_method, '/teleconsult/postpayment/stripe_paynow')
    )
