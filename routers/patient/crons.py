from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from config import CRON_API_KEY
from models import get_db
from models.teleconsult import Teleconsult, TeleconsultStatus
from utils import sg_datetime

router = APIRouter()

# The following will validate all public facing requests like login
auth_scheme = HTTPBearer()
def validate_token(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if token.credentials != CRON_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")

@router.get('/teleconsults/reset')
def reset_teleconsults(db = Depends(get_db)):
    responses = []

    curr_time = sg_datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    responses.append(f"Retrieving teleconsults before {curr_time}")
    print(responses[-1])

    records = db.query(Teleconsult).filter(
            Teleconsult.status.in_((TeleconsultStatus.CANCELLED, TeleconsultStatus.MISSED)),
            Teleconsult.created_at < curr_time
        ).all()
    
    for record in records:
        responses.append(f"{record.id}: {record.status}, {record.created_at}")
        print(responses[-1])
        record.status = TeleconsultStatus.CHECKED_OUT
        record.checkout_time = sg_datetime.now()
        
    responses.append(f"{curr_time}: Checked out {len(records)} teleconsults (CANCELLED/MISSED) successfully")
    print(responses[-1])
    db.commit()
    
    return responses
