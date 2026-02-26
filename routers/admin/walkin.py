from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from fastapi import APIRouter, Depends
from models import get_db
from models.model_enums import WalkinQueueStatus
from models.walkin import WalkInQueue
from utils import sg_datetime
from utils.supabase_auth import get_superadmin
from datetime import date, datetime, timedelta

router = APIRouter(dependencies=[Depends(get_superadmin)])

class WalkinAdminResp(BaseModel):
    id: str
    created_at: datetime
    sgimed_patient_id: str
    sgimed_visit_id: str
    queue_number: Optional[str] = None
    patient_name: str
    patient_nric: str
    branch_name: str
    corporate_code: Optional[str] = None
    hide_invoice: Optional[bool] = None
    status: WalkinQueueStatus

@router.get('/', response_model=list[WalkinAdminResp])
def get_walkins(date: date, db: Session = Depends(get_db)) -> list[WalkinAdminResp]:
    curr_midnight_time = sg_datetime.midnight(date)
    walkins = db.query(WalkInQueue).options(joinedload(WalkInQueue.account)).filter(
            WalkInQueue.created_at >= curr_midnight_time,
            WalkInQueue.created_at < curr_midnight_time + timedelta(days=1)
        ).all()
    
    return [
        WalkinAdminResp(
            id=str(walkin.id),
            created_at=walkin.created_at,
            sgimed_patient_id=walkin.account.sgimed_patient_id if walkin.account.sgimed_patient_id else "",
            sgimed_visit_id=walkin.sgimed_visit_id if walkin.sgimed_visit_id else "",
            queue_number=walkin.queue_number,
            patient_name=walkin.account.name,
            patient_nric=walkin.account.nric,
            branch_name=walkin.branch.name,
            status=walkin.status
        )
        for walkin in walkins
    ]
