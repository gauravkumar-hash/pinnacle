from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db, PinnacleAccount
from utils.supabase_auth import SupabaseUser, get_doctor_or_superadmin

router = APIRouter()

class PushTokenReq(BaseModel):
    push_token: str

class SuccessResponse(BaseModel):
    success: bool

@router.post("/token")
async def register_expo_token(req: PushTokenReq, user: SupabaseUser = Depends(get_doctor_or_superadmin), db: Session = Depends(get_db)):
    account = db.query(PinnacleAccount).filter(PinnacleAccount.id == user.id, PinnacleAccount.deleted == False).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    ## Only add into database if it is new push token
    ## WARN : Sqlalchemy session unable to detect list append and remove, have to use .copy() and reassign new list
    if req.push_token not in account.push_token:
        # For now always only assign to the latest token
        updated_list = account.push_token.copy()
        updated_list.append(req.push_token)
        account.push_token = updated_list
        # account.push_token = [req.push_token]
        db.commit()

    return SuccessResponse(success=True)

@router.delete("/token")
async def remove_expo_token(token: str, user: SupabaseUser = Depends(get_doctor_or_superadmin), db: Session = Depends(get_db)):
    account = db.query(PinnacleAccount).filter(PinnacleAccount.id == user.id, PinnacleAccount.deleted == False).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if token in account.push_token:
        updated_token = account.push_token.copy()
        updated_token.remove(token)
        account.push_token = updated_token
        db.commit()

    return SuccessResponse(success=True)
