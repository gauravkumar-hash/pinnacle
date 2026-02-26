from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from models import get_db, StAndrew
from .utils import get_current_user

router = APIRouter()

class MigrantWorkerBase(BaseModel):
    nric: str
    comp_code: Optional[str] = None
    company_name: Optional[str] = None
    uen: Optional[str] = None
    employee_no: Optional[str] = None
    employee_name: str
    passport: Optional[str] = None
    sector: Optional[str] = None
    pcp_start: Optional[str] = None
    pcp_end: Optional[str] = None
    checkup_mwoc: Optional[str] = None
    status: Optional[str] = None
    created_date_time: Optional[str] = None
    termination_date: Optional[str] = None
    handphone_no: Optional[str] = None

def migrant_workers_dict(migrant_workers):
    migrant_workers_dict = {}
    keys_in_base = MigrantWorkerBase.__annotations__.keys()

    for worker in migrant_workers:
        worker_dict = {}
        for key in keys_in_base:
            if hasattr(worker, key):
                worker_dict[key] = getattr(worker, key)
                
        migrant_workers_dict[worker.nric] = worker_dict

    return migrant_workers_dict

@router.post("/migrant-workers-options")
async def migrant_workers_options(migrant_worker: List[MigrantWorkerBase], current_user = Depends(get_current_user), db = Depends(get_db)): 
    current_workers = migrant_workers_dict(db.query(StAndrew).all())
    uploaded_workers = migrant_workers_dict(migrant_worker)

    res = {
        "INSERT": [],
        "UPDATE": [],
        "DELETE": [],
        "total_num_rows": 0
    }

    common_workers = set(current_workers.keys()) & set(uploaded_workers.keys())

    for nric in common_workers:
        if current_workers[nric] != uploaded_workers[nric]:
            res['UPDATE'].append(nric)  

    new_workers = set(uploaded_workers.keys()) - set(current_workers.keys())
    for nric in new_workers:
        res['INSERT'].append(nric)

    removed_workers = set(current_workers.keys()) - set(uploaded_workers.keys())
    for nric in removed_workers:
        res['DELETE'].append(nric)

    res['total_num_rows'] = len(current_workers)

    return res

# for upload
class MigrantWorkerUpload(BaseModel):
    INSERT: Optional[List[MigrantWorkerBase]] = None
    UPDATE: Optional[List[MigrantWorkerBase]] = None
    DELETE: Optional[List[str]] = None

def migrant_worker_insert(migrant_workers: List[MigrantWorkerBase], db: Session):
    db.add_all([StAndrew(**worker.model_dump()) for worker in migrant_workers])

def migrant_worker_update(migrant_workers: List[MigrantWorkerBase], db: Session):
    rows = db.query(StAndrew).filter(StAndrew.nric.in_([mw.nric for mw in migrant_workers])).delete()
    print(f"Rows Deleted: {rows}")
    db.add_all([StAndrew(**worker.model_dump()) for worker in migrant_workers])

def migrant_worker_delete(migrant_workers_nric: List[str], db: Session):    
    rows = db.query(StAndrew).filter(StAndrew.nric.in_(migrant_workers_nric)).delete()
    print(f"Rows Deleted: {rows}")

@router.post("/migrant-workers-publish")
async def publish_migrant_workers(migrant_worker_options: MigrantWorkerUpload, current_user = Depends(get_current_user), db = Depends(get_db)): 
    handlers = {
        "INSERT": migrant_worker_insert,
        "UPDATE": migrant_worker_update,
        "DELETE": migrant_worker_delete
    }
    try:
        for key, handler in handlers.items():
            items = getattr(migrant_worker_options, key)
            if items:
                handler(items, db)
        
        db.commit()
        return { "success": True }
    except Exception as e:
        db.rollback()
        print(f"Exception occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
