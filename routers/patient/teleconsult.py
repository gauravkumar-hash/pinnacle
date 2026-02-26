import asyncio
from datetime import datetime, timedelta, time as dt_time
import logging
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel
import json
from sse_starlette import EventSourceResponse
import time
import jwt
from sqlalchemy.orm import Session

from config import SGIMED_SA_PCP_BRANCH_ID, ZOOM_APP_KEY, ZOOM_APP_SECRET
from models import AccountFirebase, Payment, SessionLocal, Teleconsult, TeleconsultStatus, get_db, PaymentStatus, PaymentMethod, Account
from models.model_enums import CollectionMethod, DayOfWeek, PatientType
from models.payments import CorporateCode, PaymentProvider, PaymentType
from models.pinnacle import Branch, Content
from routers.patient.actions.teleconsult_flow_backend import prepayment_success_webhook
from services.visits import DocumentHtml, get_invoice_document_html, get_mc_document_html
from utils import sg_datetime
from utils.fastapi import SuccessResp, ExceptionCode, HTTPJSONException
from utils.stripe import fetch_payment_sheet, generate_stripe_paynow_link
from .actions import teleconsult_utils
from .utils import session_manager, validate_firebase_token, validate_user
from services.teleconsult import combine_breakdown_with_gst, fetch_prepayment_rate, get_corporate_membership, PaymentBreakdown

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class PrepaymentRateResp(BaseModel):
    is_pcp: bool = False # This allows the frontend to use DEFERRED_PAYMENT to pay only after the consult
    code: Optional[str] = None
    breakdown: list[PaymentBreakdown]
    total: float
    address: str
    allergy: Optional[str] = None
    tnc: str

@router.get('/prepayment/rate', response_model=PrepaymentRateResp)
def get_rate(code: Optional[str] = None, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    record = db.query(AccountFirebase).filter(AccountFirebase.firebase_uid == firebase_uid).first()
    if not record:
        raise HTTPException(status_code=403, detail="Invalid user")
    
    is_pcp, rate_code, _rate = fetch_prepayment_rate(db, record.account.nric, code)
    rate = combine_breakdown_with_gst([_rate])
    tnc = db.query(Content).filter(Content.id == 'teleconsult_prepayment').first()
    tnc = tnc.content if tnc else ''
        
    return PrepaymentRateResp(
        is_pcp=is_pcp,
        code=rate_code,
        breakdown=rate.breakdown,
        total=rate.total,
        address=record.account.get_address(),
        allergy=record.account.allergy,
        tnc=tnc,
    )
    # return PrepaymentRateResp.model_validate(rate)

@router.get('/prepayment/validate_code', response_model=SuccessResp)
def validate_corporate_code(code: str, user = Depends(validate_user), db: Session = Depends(get_db)):
    membership = get_corporate_membership(str(user.id), code)
    if not membership or membership.code != code.upper():
        raise HTTPException(
            400,
            "Please enter a valid corporate code.",
        )

    return SuccessResp(success=True)

class AvailableBranchesResp(BaseModel):
    id: str
    name: str
    category: str
    availability: str

@router.get('/branches', response_model=list[AvailableBranchesResp])
def get_available_branches(mode: CollectionMethod = CollectionMethod.DELIVERY, db: Session = Depends(get_db)):
    branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False).all()
    curr_dt = sg_datetime.now()
    
    def map_branch(branch: Branch):
        availability = 'Closed'
        operating = branch.is_operating(db, curr_dt, mode)
        if operating:
            print(branch.id, branch.name, "Current Operating Hour")
            availability = 'Same Day'
        else:
            operating = branch.get_next_operating_hour(db, curr_dt, mode)
            if operating:
                availability = 'Same Day'
            else:
                for i in range(1, 4):
                    next_dt = curr_dt + timedelta(days=i)
                    next_dt = datetime.combine(next_dt.date(), dt_time()) # Starting at midnight
                    operating = branch.get_next_operating_hour(db, next_dt, mode)
                    if operating:
                        availability = list(DayOfWeek)[next_dt.weekday()].value
                        break

        return AvailableBranchesResp(
            id=str(branch.id),
            name=branch.name,
            category=branch.category,
            availability=availability,
        )

    return [map_branch(branch) for branch in branches]

class JoinQueueReq(BaseModel):
    code: Optional[str] = None
    branch_id: Optional[str] = None
    allergy: Optional[str] = None
    collection_method: Optional[CollectionMethod] = None

class JoinQueueResp(BaseModel):
    prepayment_required: bool

@router.post('/queue/join', response_model=JoinQueueResp)
def join_queue(params: JoinQueueReq, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    prepayment_required = True
    if params.code:
        code = db.query(CorporateCode).filter(
                CorporateCode.code == params.code.upper(),
                CorporateCode.skip_prepayment == True,
                CorporateCode.deleted == False,
            ).first()
        if code:
            prepayment_required = False
            
            branch = db.query(Branch).filter(Branch.id == params.branch_id).first()
            if not branch:
                raise HTTPException(status_code=400, detail="Branch not found")
            
            # Update Account Allergy
            user.allergy = params.allergy
            # Create new teleconsult record
            is_pcp, rate_code, _rate = fetch_prepayment_rate(db, user.nric, params.code)
            rate = combine_breakdown_with_gst([_rate])
            payment_breakdown = [b.model_dump() for b in rate.breakdown]
            teleconsult = db.query(Teleconsult).filter(Teleconsult.account_id == user.id, Teleconsult.status == TeleconsultStatus.PREPAYMENT).first()
            if teleconsult:
                teleconsult.patient_type = PatientType.PRIVATE_PATIENT
                teleconsult.corporate_code = rate_code
                teleconsult.payment_breakdown = payment_breakdown
                teleconsult.total = rate.total
                teleconsult.address = user.get_address()
                teleconsult.branch_id = str(branch.id)
                teleconsult.collection_method=params.collection_method
            else:
                teleconsult = Teleconsult(
                    account_id=str(user.id),
                    patient_type=PatientType.PRIVATE_PATIENT,
                    corporate_code=rate_code,
                    payment_breakdown=payment_breakdown,
                    total=rate.total,
                    balance=rate.total,
                    status=TeleconsultStatus.PREPAYMENT,
                    address=user.get_address(),
                    branch_id=str(branch.id),
                    collection_method=params.collection_method,
                )
                db.add(teleconsult)
            
            payment = Payment(
                payment_id=rate_code,
                account_id=str(user.id),
                payment_breakdown=payment_breakdown,
                payment_type=PaymentType.PREPAYMENT,
                payment_method=PaymentMethod.DEFERRED_PAYMENT,
                payment_amount=0.0,
                status=PaymentStatus.PAYMENT_SUCCESS,
                teleconsults=[teleconsult]
            )
            db.add(payment)
            db.commit()

            prepayment_success_webhook(db, [payment])
            db.commit()
    
    return JoinQueueResp(prepayment_required=prepayment_required)

class CreatePrepaymentReq(BaseModel):
    code: Optional[str] = None
    total: float
    payment_method: PaymentMethod
    branch_id: Optional[str] = None
    allergy: Optional[str] = None
    collection_method: Optional[CollectionMethod] = None

@router.post('/prepayment/create', response_model=dict)
async def create_prepayment(
    params: CreatePrepaymentReq,
    user: Account = Depends(validate_user),
    db: Session = Depends(get_db)
):
    is_pcp, rate_code, _rate = fetch_prepayment_rate(db, user.nric, params.code)
    rate = combine_breakdown_with_gst([_rate])
    if rate.total != params.total:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.PREPAYMENT_RATE_CHANGE,
            title="Prepayment rate has changed",
            message="Please review the new rates.",
        )

    # PCP accounts are assigned to a specific branch. All others are assigned to selected branch
    if not is_pcp and not params.branch_id:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.PREPAYMENT_RATE_CHANGE,
            title="Invalid Teleconsult",
            message="Please select a branch",
        ) 

    # Update Account Allergy
    user.allergy = params.allergy
    payment_breakdown = [b.model_dump() for b in rate.breakdown]
    # Create Teleconsult for PREPAYMENT
    branch_id = SGIMED_SA_PCP_BRANCH_ID if is_pcp else params.branch_id
    teleconsult = db.query(Teleconsult).filter(Teleconsult.account_id == user.id, Teleconsult.status == TeleconsultStatus.PREPAYMENT).first()
    if teleconsult:
        teleconsult.patient_type = PatientType.MIGRANT_WORKER if is_pcp else PatientType.PRIVATE_PATIENT
        teleconsult.corporate_code=rate_code
        teleconsult.payment_breakdown=payment_breakdown
        teleconsult.total=rate.total
        teleconsult.address=user.get_address()
        teleconsult.branch_id=branch_id
        teleconsult.collection_method=CollectionMethod.DELIVERY if is_pcp else params.collection_method
    else:
        teleconsult = Teleconsult(
            account_id=user.id,
            patient_type=PatientType.MIGRANT_WORKER if is_pcp else PatientType.PRIVATE_PATIENT,
            corporate_code=rate_code,
            payment_breakdown=payment_breakdown,
            total=rate.total,
            status=TeleconsultStatus.PREPAYMENT,
            address=user.get_address(),
            branch_id=branch_id,
            collection_method=CollectionMethod.DELIVERY if is_pcp else params.collection_method,
        )
        db.add(teleconsult)
    db.commit()
    
    # # Testing Webhook without trigger to Stripe
    # TESTING = True
    # if TESTING: # params.payment_method == PaymentMethod.DEFERRED_PAYMENT:
    #     payment = Payment(
    #         payment_id=str(uuid.uuid4()),
    #         account_id=record.account.id,
    #         payment_breakdown=rate['breakdown'],
    #         payment_method=PaymentMethod.DEFERRED_PAYMENT,
    #         payment_amount=0.0,
    #         status=PaymentStatus.PAYMENT_SUCCESS
    #     )
    #     db.add(payment)
    #     db.commit()
        
    #     return {
    #         "success": prepayment_success_webhook(db, payment)
    #     }

    # Stripe Credit/Debit Card Flow
    if params.payment_method == PaymentMethod.CARD_STRIPE:
        stripe_body = fetch_payment_sheet(db, user, amount=rate.total)
        if not stripe_body:
            raise HTTPException(status_code=500, detail="Failed to initate Credit / Debit Card Payment")

        payment = Payment(
            payment_id=stripe_body['payment_intent']['id'],
            account_id=user.id,
            payment_breakdown=payment_breakdown,
            payment_type=PaymentType.PREPAYMENT,
            payment_method=PaymentMethod.CARD_STRIPE,
            payment_provider=PaymentProvider.APP_STRIPE,
            payment_amount=rate.total,
            status=PaymentStatus.PAYMENT_CREATED,
            teleconsults=[teleconsult]
        )
        db.add(payment)
        db.commit()
        stripe_body['id'] = payment.id
        return stripe_body
    
    # Stripe PayNow Flow
    elif params.payment_method == PaymentMethod.PAYNOW_STRIPE:
        stripe_session = generate_stripe_paynow_link(db, user, rate.total)
        print(stripe_session)
        payment = Payment(
            payment_id=stripe_session.id,
            account_id=user.id,
            payment_breakdown=payment_breakdown,
            payment_type=PaymentType.PREPAYMENT,
            payment_method=PaymentMethod.PAYNOW_STRIPE,
            payment_provider=PaymentProvider.APP_STRIPE,
            payment_amount=rate.total,
            status=PaymentStatus.PAYMENT_CREATED,
            teleconsults=[teleconsult]
        )
        db.add(payment)
        db.commit()
        
        return {
            "url": stripe_session.url,
            "id": payment.id
        }
    
    # elif params.payment_method == PaymentMethod.NETS_CLICK:
    else:
        logging.error(f"Unhandle payment method: {params.payment_method}")
        raise HTTPException(status_code=500, detail="Payment method not supported")


@router.get('/payment/cancel')
def cancel_pending_payments(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    record = db.query(AccountFirebase).filter(AccountFirebase.firebase_uid == firebase_uid).first()
    if not record:
        raise HTTPException(status_code=403, detail="Invalid user")
    
    payments = db.query(Payment).filter(Payment.account_id == record.account.id, Payment.status == PaymentStatus.PAYMENT_CREATED).all()
    for payment in payments:
        payment.status = PaymentStatus.PAYMENT_CANCELED
    print(f"Canceling payments: {len(payments)}")
    db.commit()    
    return {
        "success": True
    }

class TeleconsultPaymentResp(BaseModel):
    payment_amount: float
    payment_method: PaymentMethod
    remarks: Optional[dict[str, Any]] = None
    updated_at: datetime

class PrescriptionDict(BaseModel):
    item_name: str
    instructions: str
    precautions: str

class DocumentDict(BaseModel):
    icon: str = 'document'
    title: str
    url: str
    filename: str

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
    invoice: Optional[DocumentDict] = None # URL
    prescriptions: list[PrescriptionDict] = []
    documents: list[DocumentDict] = []
    hide_invoice: bool

def get_teleconsult_resp(db: Session, account_id: str, teleconsult_id: Optional[str] = None) -> Optional[TeleconsultResp]:
    # This is because for SSE as it is always ongoing, it should not maintain a database connection
    teleconsult = None
    if teleconsult_id:
        teleconsult = db.query(Teleconsult).filter(
            Teleconsult.account_id == account_id,
            Teleconsult.id == teleconsult_id
        ).first()
    # Fetching latest record to be processed
    else:
        teleconsult = db.query(Teleconsult).filter(
            Teleconsult.account_id == account_id,
            Teleconsult.status != TeleconsultStatus.CHECKED_OUT
        ).order_by(Teleconsult.updated_at.desc()).first()

    if not teleconsult:
        return None
    
    # Setup all the post documents
    invoice = None
    hide_invoice = False
    prescriptions = []
    documents = []
    if teleconsult.status in [TeleconsultStatus.OUTSTANDING, TeleconsultStatus.CHECKED_OUT] and teleconsult.invoices:
        # If invoice is hidden it should not be shown
        hide_invoice = teleconsult.invoices[0].hide_invoice
        if not hide_invoice:
            invoice = DocumentDict(
                title="Invoice",
                url=f"/api/teleconsult/invoice?id={teleconsult.id}",
                filename="Invoice.pdf"
            )
        # Populate Prescriptions & MC if available when status is CHECKED_OUT
        # if teleconsult.status == TeleconsultStatus.CHECKED_OUT:
        if teleconsult.invoices[0].show_details:
            prescriptions = [
                PrescriptionDict(
                    item_name=p['item_name'] if 'item_name' in p else '',
                    instructions=p['instructions'] if 'instructions' in p else '',
                    precautions=p['precautions'] if 'precautions' in p else ''
                )
                for p in teleconsult.invoices[0].prescriptions    
            ]
            if teleconsult.invoices[0].mc_html:
                documents = [
                    DocumentDict(
                        icon="document",
                        title="Medical Certificate (MC)",
                        url=f"/api/teleconsult/mc?id={teleconsult.id}",
                        filename="Medical Certificate.pdf"
                    )
                ]

    time_subtitle = f'Checked In: {sg_datetime.sg(teleconsult.checkin_time).strftime("%d %b %Y, %I:%M%p")}'
    if teleconsult.checkout_time:
        time_subtitle = f'Checked Out: {sg_datetime.sg(teleconsult.checkout_time).strftime("%d %b %Y, %I:%M%p")}'
    elif teleconsult.teleconsult_end_time:
        time_subtitle = f'Consult Ended: {sg_datetime.sg(teleconsult.teleconsult_end_time).strftime("%d %b %Y, %I:%M%p")}'
    elif teleconsult.teleconsult_start_time:
        time_subtitle = f'Consult Started: {sg_datetime.sg(teleconsult.teleconsult_start_time).strftime("%d %b %Y, %I:%M%p")}'

    return TeleconsultResp(
        id=str(teleconsult.id),
        time_subtitle=time_subtitle,
        status=teleconsult.status,
        queue_status=teleconsult.queue_status,
        doctor=teleconsult.doctor.name if teleconsult.doctor_id else None,
        payment_breakdown=[
            PaymentBreakdown.model_validate(row)
            for row in teleconsult.payment_breakdown
        ] if not hide_invoice else [],
        payments=[
            TeleconsultPaymentResp(
                payment_amount=payment.payment_amount,
                payment_method=payment.payment_method,
                remarks=payment.remarks,
                updated_at=payment.updated_at
            )
            for payment in teleconsult.get_successful_payments()
            # This is to prevent showing deferred payment on the frontend UI
            if payment.payment_method != PaymentMethod.DEFERRED_PAYMENT
        ],
        total=teleconsult.total,
        balance=teleconsult.balance,
        address=teleconsult.address,
        allow_address_change=teleconsult.status != TeleconsultStatus.CHECKED_OUT,
        invoice=invoice,
        prescriptions=prescriptions,
        documents=documents,
        hide_invoice=hide_invoice,
    )

# This endpoint is just for getting teleconsult record
@router.get('/details', response_model=TeleconsultResp)
async def get_details(id: Optional[str] = None, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    record = db.query(AccountFirebase).filter(AccountFirebase.firebase_uid == firebase_uid).first()
    if not record:
        raise HTTPException(status_code=403, detail="Invalid user")
    
    resp = get_teleconsult_resp(db, str(record.account.id), id)
    if not resp:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    return resp

# This endpoint is for listening to the most recent record of teleconsult
@router.get("/sse")
async def get_status(id: Optional[str] = None, firebase_uid = Depends(validate_firebase_token)):
    account_id = None
    with SessionLocal() as db:
        record = db.query(AccountFirebase).filter(AccountFirebase.firebase_uid == firebase_uid).first()
        if not record:
            raise HTTPException(status_code=403, detail="Invalid user")
        account_id = str(record.account.id)

    # # Either get teleconsult with an ID or the latest record with checked in
    # teleconsult = None
    # if id:
    #     teleconsult = db.query(Teleconsult).filter(
    #         Teleconsult.id == id,
    #         Teleconsult.account_id == record.account.id
    #     ).first()   
    # else:
    #     # Retry 6 times for 30 seconds total because some teleconsult might be still pending
    #     for i in range(6):
    #         teleconsult = db.query(Teleconsult).filter(
    #             Teleconsult.account_id == record.account.id
    #         ).order_by(Teleconsult.created_at.desc()).first()
    #         if teleconsult and teleconsult.status in [TeleconsultStatus.CHECKED_IN, TeleconsultStatus.CONSULT_START, TeleconsultStatus.CONSULT_END]:
    #             break
    #         else:
    #             await asyncio.sleep(5)
    
    async def connect_queue(account_id: str):
        session_id, queue = session_manager.add_client(account_id)
        try:
            while True:
                with SessionLocal() as db:
                    resp = get_teleconsult_resp(db, account_id)

                sse_resp = {
                    "teleconsult": None if not resp else json.loads(resp.model_dump_json())
                }
                yield {
                    "data": json.dumps(sse_resp)
                }
                # Queue is just to block until when a new message is received
                message = await queue.get()
        except asyncio.CancelledError:
            session_manager.delete_client(id, session_id)

    return EventSourceResponse(connect_queue(account_id))
    
class CancelParams(BaseModel):
    id: str

@router.post('/cancel', response_model=SuccessResp)
def cancel_teleconsult(params: CancelParams, background_tasks: BackgroundTasks, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)

    record = db.query(Teleconsult).filter(Teleconsult.id == params.id, Teleconsult.account_id == user.id, Teleconsult.status.in_([TeleconsultStatus.CHECKED_IN, TeleconsultStatus.MISSED])).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    record.status = TeleconsultStatus.CANCELLED
    record.queue_status = "You may wish to join the queue again"
    db.commit()
    background_tasks.add_task(teleconsult_utils.user_triggered_queue_status_change, str(record.id))
    return SuccessResp(success=True)

class RejoinParams(BaseModel):
    id: str

@router.post('/rejoin', response_model=SuccessResp)
def rejoin_teleconsult(params: RejoinParams, background_tasks: BackgroundTasks, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    record = db.query(Teleconsult).filter(Teleconsult.id == params.id, Teleconsult.account_id == user.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    
    if record.status not in [TeleconsultStatus.MISSED, TeleconsultStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Teleconsult cannot be rejoined")
    
    record.additional_status = record.status
    record.status = TeleconsultStatus.CHECKED_IN
    record.queue_status = "Please wait for your turn"
    record.doctor_id = None
    record.notifications_sent = []
    record.teleconsult_start_time = None
    record.teleconsult_end_time = None
    record.checkin_time = sg_datetime.now()
    db.commit()
    background_tasks.add_task(teleconsult_utils.user_triggered_queue_status_change, str(record.id))

    return SuccessResp(success=True)

class TeleconsultsListResp(BaseModel):
    id: str
    checkin_time: datetime
    status: TeleconsultStatus
    queue_status: str

@router.get('/', response_model=list[TeleconsultsListResp])
def get_teleconsults(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    records = db.query(Teleconsult).filter(Teleconsult.account_id == user.id).order_by(Teleconsult.updated_at.desc()).all()
    return [
        TeleconsultsListResp(
            id=str(record.id),
            checkin_time=record.checkin_time,
            status=record.status,
            queue_status=record.queue_status
        )
        for record in records
    ]

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

@router.post('/video', response_model=VideoResp)
def get_video_token(params: VideoParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    record = None
    try:    
        record = db.query(Teleconsult).filter(
            Teleconsult.id == params.id,
            Teleconsult.account_id == user.id, 
            Teleconsult.status == TeleconsultStatus.CONSULT_START
        ).first()
    except Exception:
        logging.error(f"Failed to get teleconsult. ID: {params.id}, User ID: {user.id}")

    if not record:
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    session_name = str(record.id)

    def get_token():
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
        
    token = get_token()
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
        )

@router.get('/invoice', response_model=DocumentHtml)
def get_invoice(id: str, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    record = db.query(Teleconsult).filter(
        Teleconsult.id == id,
        Teleconsult.account_id == user.id,
    ).first()
    if not record or not record.invoices:
        raise HTTPException(status_code=404, detail="Teleconsult not found")
    if record.invoices[0].hide_invoice:
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    return get_invoice_document_html(record.invoices[0].invoice_html)

@router.get('/mc', response_model=DocumentHtml)
def get_mc(id: str, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    record = db.query(Teleconsult).filter(
        Teleconsult.id == id,
        Teleconsult.account_id == user.id
    ).first()
    if not record or not record.invoices or not record.invoices[0].mc_html:
        raise HTTPException(status_code=404, detail="Teleconsult not found")

    return get_mc_document_html(record.invoices[0].mc_html)
    
class CreatePostpaymentReq(BaseModel):
    id: str
    payment_method: PaymentMethod

@router.post('/postpayment/create', response_model=dict)
def create_postpayment(params: CreatePostpaymentReq, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    print(f"Params Received: {params.model_dump()}")
    record = db.query(AccountFirebase).filter(AccountFirebase.firebase_uid == firebase_uid).first()
    if not record:
        raise HTTPException(status_code=403, detail="Invalid user")

    teleconsult = db.query(Teleconsult).filter(Teleconsult.id == params.id, Teleconsult.account_id == record.account.id).first()
    if not teleconsult:
        raise HTTPException(status_code=404, detail="Record not found")
    if not teleconsult.balance:
        raise HTTPException(status_code=400, detail="No outstanding balance")

    # Stripe Credit/Debit Card Flow
    if params.payment_method == PaymentMethod.CARD_STRIPE:
        stripe_body = fetch_payment_sheet(db, record.account, teleconsult.balance)
        if not stripe_body:
            raise HTTPException(status_code=500, detail="Failed to initate Credit / Debit Card Payment")

        payment = Payment(
            payment_id=stripe_body['payment_intent']['id'],
            account_id=record.account.id,
            payment_breakdown=teleconsult.payment_breakdown,
            payment_type=PaymentType.POSTPAYMENT,
            payment_method=PaymentMethod.CARD_STRIPE,
            payment_provider=PaymentProvider.APP_STRIPE,
            payment_amount=teleconsult.balance,
            status=PaymentStatus.PAYMENT_CREATED,
            teleconsults=[teleconsult]
        )
        db.add(payment)
        db.commit()
        stripe_body['id'] = payment.id
        return stripe_body
    
    # Stripe PayNow Flow
    elif params.payment_method == PaymentMethod.PAYNOW_STRIPE:
        stripe_session = generate_stripe_paynow_link(db, record.account, teleconsult.balance)
        print(stripe_session)
        payment = Payment(
            payment_id=stripe_session.id,
            account_id=record.account.id,
            payment_breakdown=teleconsult.payment_breakdown,
            payment_type=PaymentType.POSTPAYMENT,
            payment_method=PaymentMethod.PAYNOW_STRIPE,
            payment_provider=PaymentProvider.APP_STRIPE,
            payment_amount=teleconsult.balance,
            status=PaymentStatus.PAYMENT_CREATED,
            teleconsults=[teleconsult]
        )
        db.add(payment)
        db.commit()
        
        return {
            "url": stripe_session.url,
            "id": payment.id
        }
    
    # elif params.payment_method == PaymentMethod.NETS_CLICK:
    else:
        logging.error(f"Unhandle payment method: {params.payment_method}")
        raise HTTPException(status_code=500, detail="Payment method not supported")
