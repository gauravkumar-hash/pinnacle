import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from utils import sg_datetime
from utils.fastapi import CreateResp, SuccessResp
from models import get_db
from models.pinnacle import Branch, PinnacleAccount, PublicHoliday
from models.model_enums import Role

from utils.fastapi import SelectOption
from utils.integrations.sgimed import get_doctors
from utils.supabase_auth import SupabaseUser, get_superadmin
from config import ADMIN_WEB_URL, supabase
from datetime import date

router = APIRouter(dependencies=[Depends(get_superadmin)])

class AccountResp(BaseModel):
    id: str
    branch_id: Optional[str] = None
    branch_name: Optional[str] = None
    name: str
    email: str
    role: Role
    enable_notifications: bool

@router.get("/accounts", response_model=list[AccountResp])
def fetch_accounts(db: Session = Depends(get_db), user: SupabaseUser = Depends(get_superadmin)):
    records = db.query(PinnacleAccount).filter(PinnacleAccount.deleted == False).all()
    return [
        AccountResp(
            id=str(record.id),
            branch_id=str(record.branch_id),
            branch_name=record.branch.name if record.branch_id else None,
            name=record.name,
            email=record.email,
            role=record.role,
            enable_notifications=record.enable_notifications
        )
        for record in records if str(record.id) != user.id
    ]

class ToggleNotificationsParams(BaseModel):
    account_id: str
    enable_notifications: bool

@router.post("/accounts/toggle_notifications", response_model=SuccessResp)
def toggle_account_notifications(req: ToggleNotificationsParams, db: Session = Depends(get_db)):
    record = db.query(PinnacleAccount).filter(
            PinnacleAccount.id == req.account_id,
            PinnacleAccount.deleted == False
        ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Account not found.")
    
    record.enable_notifications = req.enable_notifications
    db.commit()
    return SuccessResp(success=True)

class BranchResp(BaseModel):
    id: str
    sgimed_branch_id: str
    name: str

class AccountCreateOptions(BaseModel):
    roles: list[SelectOption]
    branches: list[BranchResp]

@router.get("/accounts/options", response_model=AccountCreateOptions)
def fetch_create_account_options(db: Session = Depends(get_db)):
    account_roles = [SelectOption(value=role.value, label=role.value.title()) for role in Role.__members__.values()]
    branches = db.query(Branch).filter(Branch.deleted == False).all()
    return AccountCreateOptions(
        roles=account_roles,
        branches=[BranchResp(id=str(branch.id), sgimed_branch_id=branch.sgimed_branch_id, name=branch.name) for branch in branches]
    )

class SGiMedDoctorResp(BaseModel):
    sgimed_id: str
    sgimed_branch_id: str
    name: str
    email: Optional[str] = None

@router.get("/doctors", response_model=list[SGiMedDoctorResp])
def fetch_sgimed_doctors(db = Depends(get_db)):
    # Note: id = sgimed_id, branch_id = sgimed_branch_id
    sgimed_doctors = get_doctors()
    existing_doctors = db.query(PinnacleAccount).filter(PinnacleAccount.role == Role.DOCTOR, PinnacleAccount.deleted == False).all()
    existing_sgimed_ids = [doctor.sgimed_id for doctor in existing_doctors]

    return [
        SGiMedDoctorResp(
            sgimed_id=row.id,
            name=row.name,
            sgimed_branch_id=row.branch_id,
            email=row.email
        )
        for row in sgimed_doctors if row.id not in existing_sgimed_ids
    ]

class CreateAccountReq(BaseModel):
    role: Role
    sgimed_id: Optional[str] = None # Only for doctor
    branch_id: Optional[str] = None # Required except for superadmin
    name: str
    email: EmailStr

@router.post("/accounts/create", response_model=CreateResp)
def create_account(req: CreateAccountReq, db = Depends(get_db)):
    if req.role == Role.DOCTOR and not req.sgimed_id:
        raise HTTPException(status_code=400, detail="Doctor ID is required.")
    if (req.role == Role.DOCTOR or req.role == Role.ADMIN) and not req.branch_id:
        raise HTTPException(status_code=400, detail="Branch ID is required.")
    
    record = db.query(PinnacleAccount).filter(PinnacleAccount.email == req.email, PinnacleAccount.deleted == False).first()
    if record:
        raise HTTPException(status_code=400, detail="Email is already used.")
    
    if req.role == Role.DOCTOR:
        record = db.query(PinnacleAccount).filter(PinnacleAccount.sgimed_id == req.sgimed_id, PinnacleAccount.deleted == False).first()
        if record:
            raise HTTPException(status_code=400, detail="Doctor already exists.")
    
    try:
        url = f"{ADMIN_WEB_URL}/set_password"
        resp = supabase.auth.admin.invite_user_by_email(req.email, { "redirect_to": url, "data": { "role": req.role.value } })

        # If the doctor was deleted before in the database and re-added having the same id in SGiMed database, restore the record with the new values.
        record = db.query(PinnacleAccount).filter(PinnacleAccount.sgimed_id == req.sgimed_id, PinnacleAccount.deleted == True).first()
        if record:
            record.role = req.role
            record.supabase_uid=resp.user.id
            record.branch_id = req.branch_id
            record.name = req.name
            record.email = req.email
            record.deleted = False
        # If record exists, but the id is different, create a new record even if the email is duplicated.
        else:
            record = PinnacleAccount(
                role=req.role,
                sgimed_id=req.sgimed_id,
                supabase_uid=resp.user.id,
                name=req.name,
                branch_id=req.branch_id,
                email=req.email
            )
            db.add(record)
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return CreateResp(id=str(record.id))

class DeleteAccountParams(BaseModel):
    ids: list[str] # The IDs are unique UUIDs for each row

@router.post("/accounts/delete", response_model=SuccessResp)
def delete_accounts(params: DeleteAccountParams, db: Session = Depends(get_db)):
    records = db.query(PinnacleAccount).filter(PinnacleAccount.id.in_(params.ids)).all()
    errors = []
    for record in records:
        try:
            supabase.auth.admin.delete_user(str(record.supabase_uid))
            record.deleted = True
        except Exception:
            logging.error(f"Failed to delete user from Supabase. Supabase User ID: {record.id}, Email: {record.email}")
            errors.append(record.email)

    db.commit()    
    if errors:
        raise HTTPException(status_code=500, detail=f"Failed to delete the following users: {', '.join(errors)}")

    return SuccessResp(success=True)

@router.get("/accounts/{account_id}/reset_password", response_model=SuccessResp)
def reset_password(account_id: str, db: Session = Depends(get_db)):
    record = db.query(PinnacleAccount).filter(PinnacleAccount.id == account_id, PinnacleAccount.deleted == False).first()
    if not record:
        raise HTTPException(status_code=404, detail="Account not found.")
    
    try:
        url = f"{ADMIN_WEB_URL}/set_password"
        resp = supabase.auth.reset_password_email(record.email, { "redirect_to": url })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    return SuccessResp(success=True)

class PublicHolidayResp(BaseModel):
    id: str
    date: date
    remarks: Optional[str] = None

@router.get("/public_holidays", response_model=list[PublicHolidayResp])
async def get_public_holidays(db: Session = Depends(get_db)):
    holidays = db.query(PublicHoliday).filter(PublicHoliday.date >= sg_datetime.now().date()).all()
    return [
            PublicHolidayResp(
                id=str(holiday.id),
                date=holiday.date,
                remarks=holiday.remarks
            )
            for holiday in holidays
        ]

class PublicHolidayCreate(BaseModel):
    id: Optional[str] = None
    date: date 
    remarks: Optional[str] = None 

@router.post("/public_holidays/upsert", response_model=CreateResp)
async def upsert_public_holiday(req: PublicHolidayCreate, db: Session = Depends(get_db)):
    duplicate_date = db.query(PublicHoliday).filter(PublicHoliday.date == req.date, PublicHoliday.id != req.id).first()
    if duplicate_date:
        raise HTTPException(status_code=400, detail="Date already exists.")

    # Update
    if req.id:
        record = db.query(PublicHoliday).filter(PublicHoliday.id == req.id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Holiday not found.")
        record.date = req.date
        record.remarks = req.remarks
        db.commit()
    # Create
    else:
        record = PublicHoliday(date=req.date, remarks=req.remarks)
        db.add(record)
    
    db.commit()    
    return CreateResp(id=str(record.id))

@router.delete("/public_holidays/{public_holiday_id}", response_model=SuccessResp)
def delete_public_holiday(public_holiday_id: str, db: Session = Depends(get_db)):
    record = db.query(PublicHoliday).filter(PublicHoliday.id == public_holiday_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Holiday not found.")
    
    db.delete(record)
    db.commit()
    return SuccessResp(success=True)