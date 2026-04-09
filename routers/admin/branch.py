from datetime import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pyfa_converter_v2 import FormDepends
from models import get_db, Branch, OperatingHour
from models.model_enums import BranchType, DayOfWeek
from pydantic import BaseModel
from models.pinnacle import Service
from routers.admin.actions.branch import BranchDetails, get_branch_details
from utils.integrations.sgimed import BranchRecord
from utils.supabase_auth import get_superadmin
from sqlalchemy.orm import Session
from utils.integrations import sgimed
from utils.fastapi import HTTPJSONException
import os.path as osp
from config import SUPABASE_UPLOAD_BUCKET, supabase
import uuid
import re

router = APIRouter(dependencies=[Depends(get_superadmin)])

class FetchBranchesResponse(BaseModel):
    branches: list[BranchRecord]

@router.get('/sgimed', response_model=FetchBranchesResponse)
def get_sgimed_branches():
    branches = sgimed.get_branches()
    return FetchBranchesResponse(
        branches=[branch for branch in branches if branch.is_enabled]
    )

class BranchListDetails(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    image_url: Optional[str] = None
    is_open: bool
    is_toggleable: bool
    branch_type: BranchType

class SuccessResponse(BaseModel):
    success: bool

@router.get("", response_model=list[BranchListDetails])
def get_branches(db: Session = Depends(get_db)):
    branches = db.query(Branch).filter(Branch.deleted == False, Branch.hidden == False).all()
    return [
        get_branch_details(db, branch)
        for branch in branches
    ]

class BranchOptions(BaseModel):
    services: list[str]

class BranchResponse(BaseModel):
    data: BranchDetails
    options: BranchOptions

@router.get("/{branch_id}", response_model=BranchResponse)
def get_branch(branch_id: str, db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    services = db.query(Service).filter(Service.sgimed_branch_id == branch.sgimed_branch_id).all()
    details = get_branch_details(db, branch)
    details.services = [s.label for s in branch.services]

    return BranchResponse(
        data=details,
        options=BranchOptions(services=[s.label for s in services]),
    )

class BranchUpdateReq(BaseModel):
    # If all the fields are None, it will throw an Error. one of the fields is required to have a value
    # placeholder: str 
    address: Optional[str] = None
    url: Optional[str] = None
    # Using Optional[list[str]] throws a 422 error
    services: list[str] = []
    # https://fastapi.tiangolo.com/tutorial/request-files/#optional-file-upload    
    image: UploadFile | None = None

@router.put("/{branch_id}", response_model=SuccessResponse)
async def update_branch(branch_id: str, params: BranchUpdateReq = FormDepends(BranchUpdateReq), db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    
    if params.address:
        branch.address = params.address

    if params.url:
        branch.url = params.url

    if params.image and params.image.filename:
        image_filename = f'branches/{branch.name}{osp.splitext(params.image.filename)[-1]}'
        image_bytes = await params.image.read()
        content_type = params.image.content_type if params.image.content_type else 'image/jpeg'
        resp = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(file=image_bytes, path=image_filename, file_options={"content-type": content_type, "upsert": 'true'})
        branch.image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(image_filename)

    # Update services
    if params.services:
        def update_services(services):
            new_services = set(services)
            services = { s.label: s for s in branch.services }
            existing_services = set(services.keys())

            # Compute the changes
            new_records = new_services - existing_services
            old_records = existing_services - new_services

            # Add new records
            for label in new_records:
                service = db.query(Service).filter(Service.label == label, Service.sgimed_branch_id == branch.sgimed_branch_id).first()
                if not service:
                    raise HTTPException(status_code=404, detail=f"Service {label} not found")
                branch.services.append(service)
            # Remove old records
            for label in old_records:
                service = services[label]
                branch.services.remove(service)

        update_services([svc for svc in params.services if svc])

    db.commit()

    return SuccessResponse(success=True)

@router.post('/services', response_model=SuccessResponse)
def update_services(db: Session = Depends(get_db)):
    db_services = { s.sgimed_appointment_type_id: s for s in db.query(Service).all() }    
    sgimed_services = { s.id: s for s in sgimed.get_services() }
    
    db_services_set = set(db_services.keys())
    sgimed_services_set = set(sgimed_services.keys())
    
    # Compute the changes
    new_records = sgimed_services_set - db_services_set
    old_records = db_services_set - sgimed_services_set
    existing_records = db_services_set & sgimed_services_set
    
    # Add new records
    for id in new_records:
        service = sgimed_services[id]
        # TODO: Current method is matching only "telemed" string. This may change.
        is_for_telemed = 'telemed' in service.name.lower()
        new_service = Service(
            label=service.name,
            sgimed_branch_id=service.branch_id,
            sgimed_appointment_type_id=service.id,
            is_for_visit=service.is_for_visit if not is_for_telemed else False,
            is_for_appointment=service.is_for_appointment if not is_for_telemed else False,
            is_for_telemed=is_for_telemed,
        )
        db.add(new_service)

    # Update existing records
    for id in existing_records:
        db_service = db_services[id]
        sgimed_service = sgimed_services[id]
        # TODO: Current method is matching only "telemed" string. This may change.
        is_for_telemed = 'telemed' in sgimed_service.name.lower()
        db_service.sgimed_branch_id=sgimed_service.branch_id
        db_service.label = sgimed_service.name
        db_service.is_for_visit = sgimed_service.is_for_visit if not is_for_telemed else False
        db_service.is_for_appointment = sgimed_service.is_for_appointment if not is_for_telemed else False
        db_service.is_for_telemed = is_for_telemed
    
    # Delete old records
    for id in old_records:
        db.delete(db_services[id])

    db.commit()
    return SuccessResponse(success=True)

class OperatingHourDetails(BaseModel):
    id: int
    day: DayOfWeek
    start_time: time
    end_time: time
    cutoff_time: Optional[int] = None

class OperatingHourOptions(BaseModel):
    days: list[DayOfWeek]

class BranchOperatingHourResponse(BaseModel):
    data: list[OperatingHourDetails]
    options: OperatingHourOptions

@router.get("/{branch_id}/operating_hours", response_model=BranchOperatingHourResponse)
def get_operating_hours(branch_id: str, db: Session = Depends(get_db)):
    operating_hours = db.query(OperatingHour).filter(OperatingHour.branch_id == branch_id).all()
    
    return BranchOperatingHourResponse(
        data=[OperatingHourDetails.model_validate(operating_hour.as_dict()) for operating_hour in operating_hours],
        options=OperatingHourOptions(days=[day for day in DayOfWeek])
    )

class CreateResponse(BaseModel):
    id: str

class BranchCreateRequest(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None
    category: str
    image: UploadFile | None = None

@router.post("", response_model=CreateResponse)
async def create_branch(params: BranchCreateRequest = FormDepends(BranchCreateRequest), db: Session = Depends(get_db)):
    # Create new branch with all provided fields
    branch = Branch(
        id=uuid.uuid4(),
        name=params.name,
        address=params.address,
        phone=params.phone,
        whatsapp=params.whatsapp,
        email=params.email,
        url=params.url,
        category=params.category,
        branch_type=BranchType.MAIN,  # Default to MAIN type
        hidden=False,
        deleted=False
    )
    
    # Handle image upload if provided
    if params.image and params.image.filename:
        # Sanitize the branch name for filename
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', params.name)
        image_filename = f'branches/{sanitized_name}_{uuid.uuid4()}{osp.splitext(params.image.filename)[-1]}'
        image_bytes = await params.image.read()
        content_type = params.image.content_type if params.image.content_type else 'image/jpeg'
        resp = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=image_bytes, 
            path=image_filename, 
            file_options={"content-type": content_type, "upsert": 'true'}
        )
        
        # Validate the upload response
        if hasattr(resp, 'error') and resp.error:
            raise HTTPJSONException(
                title="Image Upload Failed",
                message=f"Failed to upload image: {resp.error}",
                status_code=500
            )
        
        branch.image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(image_filename)
    
    db.add(branch)
    db.commit()

    return CreateResponse(id=str(branch.id))

class BranchOperatingHourCreate(BaseModel):
    day: DayOfWeek
    start_time: time
    end_time: time
    cutoff_time: int = 0

@router.post("/{branch_id}/operating_hours", response_model=CreateResponse)
def create_clinic_operating_hour(branch_id: str, req: BranchOperatingHourCreate, db: Session = Depends(get_db)):
    operating_hour = OperatingHour(
            branch_id=branch_id,
            day=req.day,
            start_time=req.start_time,
            end_time=req.end_time,
            cutoff_time=req.cutoff_time
        )

    db.add(operating_hour)
    db.commit()
    return CreateResponse(id=str(operating_hour.id))

@router.put("/{branch_id}/operating_hours/{operating_id}", response_model=SuccessResponse)
def update_operating_hour(branch_id: str, operating_id: int, req: BranchOperatingHourCreate, db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    operating_hour = db.query(OperatingHour).filter(OperatingHour.branch_id == branch.id, OperatingHour.id == operating_id).first()
    if not operating_hour:
        raise HTTPException(status_code=404, detail="Operating hour not found")
    operating_hour.day = req.day
    operating_hour.start_time = req.start_time
    operating_hour.end_time = req.end_time
    operating_hour.cutoff_time = req.cutoff_time
    db.commit()
    return SuccessResponse(success=True)

class DeleteOperatingHoursParams(BaseModel):
    ids: list[int]

@router.delete("/{branch_id}/operating_hours/delete", response_model=SuccessResponse)
def delete_operating_hour(branch_id: str, params: DeleteOperatingHoursParams, db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    hours = db.query(OperatingHour).filter(OperatingHour.branch_id == branch.id, OperatingHour.id.in_(params.ids)).all()
    if not len(hours) == len(params.ids):
        raise HTTPException(status_code=404, detail="Not all operating hours were found")
    
    for row in hours:
        db.delete(row) 
    db.commit()
    return SuccessResponse(success=True)
