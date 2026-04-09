from enum import Enum
import json
import math
from typing import Self
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session
from models import get_db
from models.patient import Account
from models.redis_models import RedisLoginState
from utils.fastapi import SuccessResp
from utils.integrations.sgimed import update_patient_data
from utils.supabase_auth import get_superadmin
from config import redis_client

router = APIRouter(dependencies=[Depends(get_superadmin)])

class Pager(BaseModel):
    p: int = 1
    rows: int
    n: int = 20
    pages: int = 0
    
    @model_validator(mode='after')
    def check_passwords_match(self) -> Self:
        self.pages = math.ceil(self.rows / self.n)
        return self

class PatientDetailsDiff(BaseModel):
    user_id: str
    sgimed_patient_id: str
    nric: str
    app: dict
    sgimed: dict

class PatientDiffResp(BaseModel):
    pager: Pager
    data: list[PatientDetailsDiff]

@router.get('/diff', response_model=PatientDiffResp)
def get_patient_diffs(page: int = 1, db: Session = Depends(get_db)):
    qry = db.query(Account).filter(Account.sgimed_diff != None)
    pager = Pager(p=page, rows=qry.count())
    offset = (pager.p - 1) * pager.n
    limit = pager.n
    accounts = qry.order_by(Account.created_at).offset(offset).limit(limit).all()

    return PatientDiffResp(
        pager=pager,
        data=[
            PatientDetailsDiff(
                user_id=str(acc.id),
                sgimed_patient_id=acc.sgimed_patient_id,
                nric=acc.nric,
                app={ k: v for k, v in acc.as_dict().items() if k in acc.sgimed_diff },
                sgimed=acc.sgimed_diff
            )
            for acc in accounts
            if acc.sgimed_diff and acc.sgimed_patient_id
        ]
    )

class UpdateDest(str, Enum):
    APP = 'app'
    SGIMED = 'sgimed'

class UpdatePatientDiff(BaseModel):
    user_id: str
    update_dest: UpdateDest

@router.post('/diff', response_model=SuccessResp)
def update_patient_diff(data: UpdatePatientDiff, db: Session = Depends(get_db)):
    acc = db.query(Account).filter(Account.id == data.user_id).first()
    if not acc:
        raise HTTPException(400, 'User not found')
    if not acc.sgimed_diff or not acc.sgimed_patient_id:
        raise HTTPException(400, 'User does not have patient_id or any data differences')

    # Update App or SGiMed
    db_diff = { k: v for k, v in acc.as_dict().items() if k in acc.sgimed_diff }
    if data.update_dest == UpdateDest.APP:
        print(f"Updating Database {acc.id}: New: {acc.sgimed_diff}, Old: {db_diff}")
        acc.update_vars(acc.sgimed_diff)
    elif data.update_dest == UpdateDest.SGIMED:
        print(f"Updating SGiMed {acc.sgimed_patient_id}: New: {db_diff}, Old: {acc.sgimed_diff}")
        update_patient_data(acc.sgimed_patient_id, db_diff)

    # Reset Differences and commit
    acc.reset_diff()
    db.commit()

    return SuccessResp(success=True)

@router.get('/otps', response_model=list[RedisLoginState])
def get_auth_otps():
    all_keys: list[str] = redis_client.keys('*') # type: ignore
    all_values: list[str] = redis_client.mget(all_keys) # type: ignore

    return [
        RedisLoginState.model_validate(json.loads(val))
        for val in all_values
    ]
