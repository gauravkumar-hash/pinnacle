from fastapi import APIRouter, Depends
from models import get_db, active_db_conn
from models.pinnacle import Content
from utils.fastapi import SuccessResp

router = APIRouter()

@router.get('/health', response_model=SuccessResp)
def health_check(db = Depends(get_db)):
    print("Health Check")
    record = db.query(Content).first()
    return SuccessResp(success=True)

@router.get('/db_conn')
def db_conns():
    return active_db_conn
