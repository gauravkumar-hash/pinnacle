from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_

from models import get_db
from models.model_enums import TeleconsultStatus, VisitType, WalkinQueueStatus
from models.patient import Account
from models.teleconsult import Teleconsult
from models.walkin import WalkInQueue
from routers.patient.actions.walkin import get_grouped_walkins, get_walkin_queues_numbers, get_walkin_queues_status
from routers.patient.utils import validate_firebase_token, validate_user
from sqlalchemy.orm import Session

from utils import sg_datetime

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class ActivityRouteResp(BaseModel):
    route: Optional[Literal['/teleconsult', '/walkin', '/teleconsult/consultation', '/walkin/consultation']] = None
    ongoing: Optional[str] = None

@router.get('/route', response_model=ActivityRouteResp)
def get_allowed_route(visit_type: VisitType, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    if visit_type == VisitType.APPOINTMENT:
        raise HTTPException(400, "Appointment is not supported")

    user = validate_user(db, firebase_uid)
    
    # This is to handle the case where user is already in an active activity
    activity = get_active_activity(db, user)
    if activity and activity.type != visit_type:
        return ActivityRouteResp(ongoing=activity.type)
    
    # # NOTE: This is temporary code to be removed after Teleconsult is live
    # if visit_type == VisitType.TELECONSULT and sg_datetime.now() < sg_datetime.midnight(date(2024, 9, 16)): 
    #     raise HTTPJSONException("Teleconsult Live on 16 Sep", "Teleconsult is going live on 16 Sep. Thank you for your patience.")
    
    # This is to handle the case where cancelled state is considered as active
    activity = get_active_activity(db, user, visit_type)
    if not activity:
        return ActivityRouteResp(route='/' + visit_type.value)
    elif activity.type == visit_type:
        return ActivityRouteResp(route='/' + visit_type.value + '/consultation')
    else:
        return ActivityRouteResp(ongoing=activity.type)

class ActivityDetail(BaseModel):
    id: str
    type: VisitType
    title: str
    content: str
    boldContent: Optional[str] = None
    tag: str

class ActivityResp(BaseModel):
    activity: Optional[ActivityDetail] = None

def get_active_activity(db: Session, user: Account, visit_type: Optional[VisitType] = None):
    ids = user.get_linked_account_ids()

    # This is because if the route is called from Teleconsult, Cancelled Teleconsult should be considered as active
    teleconsult_statuses = [TeleconsultStatus.PREPAYMENT, TeleconsultStatus.CHECKED_OUT]
    if not visit_type == VisitType.TELECONSULT:
        teleconsult_statuses.append(TeleconsultStatus.CANCELLED)

    # TODO: For Consideration, Missed State should show as an activity but not block the user from going to Walkin or having an active Walkin record.
    # Currently requires user to cancel the missed state before creating a walkin
    teleconsult = db.query(Teleconsult).filter(
            Teleconsult.account_id.in_(ids),
            Teleconsult.status.notin_(teleconsult_statuses),
        ).first()
    if teleconsult:
        return ActivityDetail(
                id=str(teleconsult.id),
                type=VisitType.TELECONSULT,
                title='Telemedicine Consultation',
                content=teleconsult.queue_status,
                tag=teleconsult.status.value
            )
    
    # Implement walk-in activity
    queue = db.query(WalkInQueue).filter(
            or_(WalkInQueue.account_id == user.id, WalkInQueue.created_by == user.id),
            WalkInQueue.status.in_([WalkinQueueStatus.PENDING, WalkinQueueStatus.CHECKED_IN, WalkinQueueStatus.CONSULT_START]),
            WalkInQueue.created_at > sg_datetime.midnight(),
        ).first()

    queues = None
    if queue:
        queues = get_grouped_walkins(db, queue, user)

    if queue and queues:
        status, queue_status = get_walkin_queues_status(queues)
        queue_number = get_walkin_queues_numbers(queues, status)

        if status in [WalkinQueueStatus.PENDING, WalkinQueueStatus.CHECKED_IN, WalkinQueueStatus.CONSULT_START]:
            return ActivityDetail(
                    id=str(queue.id),
                    type=VisitType.WALKIN,
                    title=f'Queue Request ({queue.branch.name})',
                    content=queue_status,
                    boldContent=queue_number,
                    tag=status.value
                )

    return None

@router.get("/", response_model=ActivityResp)
def get_activity(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    return ActivityResp(activity=get_active_activity(db, user))
