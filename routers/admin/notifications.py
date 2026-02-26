from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from models import get_db
from models.patient import Account, AccountFirebase
from utils.fastapi import SuccessResp
from utils.notifications import send_patient_notification
from utils.supabase_auth import get_superadmin

router = APIRouter(dependencies=[Depends(get_superadmin)])

class NotificationSearchReq(BaseModel):
    search: str

class NotificationPatientRow(BaseModel):
    id: str
    name: str
    nric: str

class NotificationPatientResp(BaseModel):
    rows: list[NotificationPatientRow]

@router.post('/users/search', response_model=NotificationPatientResp)
def search_users(req: NotificationSearchReq, db: Session = Depends(get_db)):
    qry = db.query(Account.id, Account.name, Account.nric, AccountFirebase.push_token) \
        .join(AccountFirebase, AccountFirebase.account_id == Account.id, isouter=True) \
        .where(AccountFirebase.push_token != None)

    filters = []
    if req.search:
        filters.append(Account.name.ilike(f"%{req.search}%"))
        filters.append(Account.nric.ilike(f"%{req.search}%"))
        qry = qry.filter(or_(*filters))

    qry = qry.limit(10)
    return NotificationPatientResp(
        rows=[
            NotificationPatientRow(id=str(record.id), name=record.name, nric=record.nric)
            for record in qry.all()
        ]
    )

class NotificationReq(BaseModel):
    ids: list[str]
    title: str
    message: str

@router.post('/send')
def send_notification(req: NotificationReq, db: Session = Depends(get_db)):
    users = db.query(Account).filter(Account.id.in_(req.ids)).all()
    for i, user in enumerate(users):
        # TODO: Issue it as background task or make it async
        send_patient_notification(
            user,
            req.title,
            req.message,
        )

    return SuccessResp(success=True)
