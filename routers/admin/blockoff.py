from datetime import time, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from models import get_db, Branch, Blockoff
from pydantic import BaseModel
from routers.admin.branch import CreateResponse
from utils import sg_datetime
from utils.supabase_auth import SupabaseUser, get_superadmin
from sqlalchemy.orm import Session
from utils.fastapi import SuccessResp

router = APIRouter(dependencies=[Depends(get_superadmin)])

class BranchSelectOption(BaseModel):
    value: str
    label: str

class BlockOffResp(BaseModel):
    id: str
    branches: list[BranchSelectOption]
    date: date
    start_time: time
    end_time: time
    remarks: Optional[str] = None
    enabled: bool

@router.get("/", response_model=list[BlockOffResp])
def get_blockoffs(db: Session = Depends(get_db), user = Depends(get_superadmin)):
    blockoffs = db.query(Blockoff).filter(
            Blockoff.date >= sg_datetime.now().date(),
            Blockoff.allow_toggle == False
        ).all()
    return [
        BlockOffResp(
            id=str(blockoff.id),
            branches=[
                BranchSelectOption(value=str(branch.id), label=branch.name) for branch in blockoff.branches
            ],
            date=blockoff.date,
            start_time=blockoff.start_time,
            end_time=blockoff.end_time,
            remarks=blockoff.remarks,
            enabled=blockoff.enabled
        ) for blockoff in blockoffs]

class BlockoffOptions(BaseModel):
    branch_ids: list[BranchSelectOption]

@router.get("/options", response_model=BlockoffOptions)
def get_blockoff_options(db: Session = Depends(get_db)):
    branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False).all()
    return BlockoffOptions(
        branch_ids=[BranchSelectOption(value=str(branch.id), label=branch.name) for branch in branches]
    )

class BlockoffCreate(BaseModel):
    branch_ids: list[str]
    start_date: date
    start_time: time
    end_time: time
    remarks: Optional[str] = None

@router.post("/", response_model=CreateResponse)
def create_blockoff(req: BlockoffCreate, db: Session = Depends(get_db), user = Depends(get_superadmin)):
    if not req.branch_ids:
        raise HTTPException(status_code=400, detail="Branch ids are required")

    branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False, Branch.id.in_(req.branch_ids)).all()
    if not len(req.branch_ids) == len(branches):
        raise HTTPException(status_code=404, detail="Some branches are not found")

    blockoff = Blockoff(
        date=req.start_date,
        start_time=req.start_time,
        end_time=req.end_time,
        remarks=req.remarks,
        created_by=user.id,
    )
    blockoff.branches = branches
    db.add(blockoff)
    db.commit()
    return CreateResponse(id=str(blockoff.id))

class BlockoffUpdate(BaseModel):
    branch_ids: Optional[list[str]] = None
    start_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    remarks: Optional[str] = None

@router.put("/{blockoff_id}", response_model=SuccessResp)
def update_blockoff(blockoff_id: str, req: BlockoffUpdate, db: Session = Depends(get_db)):
    blockoff = db.query(Blockoff).filter(Blockoff.id == blockoff_id).first()
    if not blockoff:
        raise HTTPException(status_code=404, detail="Block off not found")

    if req.branch_ids:
        branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False, Branch.id.in_(req.branch_ids)).all()
        if not len(req.branch_ids) == len(branches):
            raise HTTPException(status_code=404, detail="Some branches are not found")
        blockoff.branches = branches
    
    if req.start_date:
        blockoff.date = req.start_date
    if req.start_time:
        blockoff.start_time = req.start_time
    if req.end_time:
        blockoff.end_time = req.end_time
    blockoff.remarks = req.remarks
    db.commit()
    
    return SuccessResp(success=True)

@router.delete("/{blockoff_id}", response_model=SuccessResp)
def delete_blockoff(blockoff_id: str, db: Session = Depends(get_db)):
    blockoff = db.query(Blockoff).filter(Blockoff.id == blockoff_id).first()
    if not blockoff:
        raise HTTPException(status_code=404, detail="Block off not found")
    db.delete(blockoff)
    db.commit()
    return SuccessResp(success=True)

class BlockOffToggleReq(BaseModel):
    branch_id: str
    enable: bool

@router.post("/toggle_blockoff", response_model=SuccessResp, status_code=200)
async def toggle_block_off(req: BlockOffToggleReq, user: SupabaseUser = Depends(get_superadmin), db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == req.branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    # Find if there exists a current block off
    curr_dt = sg_datetime.now()
    curr_time = curr_dt.time()
    blockoff = db.query(Blockoff).join(Blockoff.branches).filter(
        Branch.id == branch.id,
        Blockoff.date == curr_dt.date(),
        Blockoff.start_time <= curr_time,
        Blockoff.end_time > curr_time,
        Blockoff.allow_toggle == True,
    ).first()
    
    # If there is block off, use current block off to toggle off by activate block off
    if blockoff:
        blockoff.enabled = not req.enable

    # Create a block off using current session operating hour
    else:
        # If there is no block off, something wrong here since admin only able toggle on when it has been toggle off before
        if req.enable:
            raise HTTPException(status_code=400, detail="Clinic is not toggled off, unable to toggle on.")

        operating_hour = branch.get_operating_hours(db)
        if not operating_hour:
            raise HTTPException(status_code=400, detail="Clinic is closed.")
        curr_blockoff = Blockoff(
            date=curr_dt.date(),
            start_time=operating_hour.start_time,
            end_time=operating_hour.end_time,
            allow_toggle=True,
            enabled=True,
            branches=[branch],
            created_by=user.id
        )
        db.add(curr_blockoff)

    db.commit()

    return SuccessResp(
        success=True
    )
