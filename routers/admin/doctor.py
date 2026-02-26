from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from models import get_db
from models.model_enums import Role
from pydantic import BaseModel
from models.pinnacle import PinnacleAccount
from utils.supabase_auth import get_superadmin
from sqlalchemy.orm import Session

router = APIRouter(dependencies=[Depends(get_superadmin)])

class DocterUpdateReq(BaseModel):
    doctor_id: str 
    enable_notifications: Optional[bool] = None
    email: Optional[str] = None
    role: Optional[Role] = None
    name: Optional[str] = None

class SuccessResponse(BaseModel):
    success: bool

@router.post("/update", response_model=SuccessResponse)
async def update_doctor(req: DocterUpdateReq, db: Session = Depends(get_db)):
    account = db.query(PinnacleAccount).filter(PinnacleAccount.id == req.doctor_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="User not found")

    if req.enable_notifications is not None:
        account.enable_notifications = req.enable_notifications
    if req.email is not None:
        account.email = req.email
    if req.role is not None:
        account.role = req.role
    if req.name is not None:
        account.name = req.name

    db.commit()
    return SuccessResponse(
        success=True
    )
