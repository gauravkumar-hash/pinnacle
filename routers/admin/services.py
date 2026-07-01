from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Literal, Optional, Union
from models.service import ClinicService
from models.specialist import Specialist
from schemas.service import ServiceResponse
from schemas.specialist import SpecialistResponse
from models import get_db
from config import SUPABASE_UPLOAD_BUCKET, supabase
import os.path as osp
import uuid
import re

router = APIRouter(tags=["Services"])


@router.get("/", response_model=List[ServiceResponse])
def get_all(db: Session = Depends(get_db)):
    return db.query(ClinicService).order_by(ClinicService.display_order.asc(), ClinicService.id.asc()).all()


@router.get("/active", response_model=List[ServiceResponse])
def get_active(db: Session = Depends(get_db)):
    return (
        db.query(ClinicService)
        .filter(ClinicService.active == True)
        .order_by(ClinicService.display_order.asc(), ClinicService.id.asc())
        .all()
    )


@router.get("/by-specialisation/{specialisation_id}", response_model=List[ServiceResponse])
def get_by_specialisation(specialisation_id: int, db: Session = Depends(get_db)):
    return (
        db.query(ClinicService)
        .options(joinedload(ClinicService.specialisation))
        .filter(
            ClinicService.specialisation_id == specialisation_id,
            ClinicService.active == True
        )
        .order_by(ClinicService.display_order.asc(), ClinicService.id.asc())
        .all()
    )


@router.get("/{service_id}", response_model=Union[ServiceResponse, SpecialistResponse])
def get_one(
    service_id: int,
    type: Literal["service", "specialist"] = "service",
    db: Session = Depends(get_db),
):
    if type == "specialist":
        record = db.query(Specialist).filter(Specialist.id == service_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Specialist not found")
        return record
    record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ClinicService not found")
    return record


@router.post("/", response_model=ServiceResponse)
async def create(
    specialisation_id: int = Form(...),
    service_name: str = Form(...),
    clinic_name: str = Form(...),
    consultation_fee: float = Form(0.0),
    bio: str = Form(""),
    service_details: str = Form(""),
    languages: str = Form(""),
    years_of_practice: Optional[int] = Form(None),
    hospital_affiliations: str = Form(""),
    board_certifications: str = Form(""),
    awards: str = Form(""),
    insurance_tpa: str = Form(""),
    insurance_shield_plan: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    available_days: str = Form(""),
    available_time_slots: str = Form(""),
    active: str = Form("true"),
    display_order: int = Form(0),
    clinic_photo: Optional[UploadFile] = None,
    banner_image: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """Create a new service with optional image upload"""
    
    # Convert string boolean to actual boolean
    active_bool = active.lower() == "true" if isinstance(active, str) else bool(active)
    
    clinic_photo_url = None
    if clinic_photo and clinic_photo.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', service_name)
        filename = f'services/{sanitized_name}_clinic_{uuid.uuid4()}{osp.splitext(clinic_photo.filename)[-1]}'
        bytes_data = await clinic_photo.read()
        ctype = clinic_photo.content_type if clinic_photo.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        clinic_photo_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)
        
    banner_image_url = None
    if banner_image and banner_image.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', service_name)
        filename = f'services/{sanitized_name}_banner_{uuid.uuid4()}{osp.splitext(banner_image.filename)[-1]}'
        bytes_data = await banner_image.read()
        ctype = banner_image.content_type if banner_image.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        banner_image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)

    record = ClinicService(
        specialisation_id=specialisation_id,
        service_name=service_name,
        clinic_name=clinic_name,
        consultation_fee=consultation_fee,
        clinic_photo_path=clinic_photo_url,
        banner_image_path=banner_image_url,
        bio=bio if bio else None,
        service_details=service_details if service_details else None,
        languages=languages if languages else None,
        years_of_practice=years_of_practice,
        hospital_affiliations=hospital_affiliations if hospital_affiliations else None,
        board_certifications=board_certifications if board_certifications else None,
        awards=awards if awards else None,
        insurance_tpa=insurance_tpa if insurance_tpa else None,
        insurance_shield_plan=insurance_shield_plan if insurance_shield_plan else None,
        contact_name=contact_name if contact_name else None,
        contact_email=contact_email if contact_email else None,
        contact_phone=contact_phone if contact_phone else None,
        available_days=available_days if available_days else None,
        available_time_slots=available_time_slots if available_time_slots else None,
        active=active_bool,
        display_order=display_order
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{service_id}", response_model=ServiceResponse)
async def update(
    service_id: int,
    specialisation_id: Optional[int] = Form(None),
    service_name: str = Form(""),
    clinic_name: str = Form(""),
    consultation_fee: Optional[float] = Form(None),
    bio: str = Form(""),
    service_details: str = Form(""),
    languages: str = Form(""),
    years_of_practice: Optional[int] = Form(None),
    hospital_affiliations: str = Form(""),
    board_certifications: str = Form(""),
    awards: str = Form(""),
    insurance_tpa: str = Form(""),
    insurance_shield_plan: str = Form(""),
    contact_name: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    available_days: str = Form(""),
    available_time_slots: str = Form(""),
    active: Optional[str] = Form(None),
    display_order: Optional[int] = Form(None),
    clinic_photo: Optional[UploadFile] = None,
    banner_image: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """Update a service with optional image upload"""
    record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ClinicService not found")
    
    if clinic_photo and clinic_photo.filename:
        current_name = service_name if service_name else record.service_name
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', current_name)
        filename = f'services/{sanitized_name}_clinic_{uuid.uuid4()}{osp.splitext(clinic_photo.filename)[-1]}'
        bytes_data = await clinic_photo.read()
        ctype = clinic_photo.content_type if clinic_photo.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        record.clinic_photo_path = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)

    if banner_image and banner_image.filename:
        current_name = service_name if service_name else record.service_name
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', current_name)
        filename = f'services/{sanitized_name}_banner_{uuid.uuid4()}{osp.splitext(banner_image.filename)[-1]}'
        bytes_data = await banner_image.read()
        ctype = banner_image.content_type if banner_image.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        record.banner_image_path = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)
    
    # Update other fields if provided
    if specialisation_id is not None:
        record.specialisation_id = specialisation_id
    if service_name:
        record.service_name = service_name
    if clinic_name:
        record.clinic_name = clinic_name
    if consultation_fee is not None:
        record.consultation_fee = consultation_fee
    if bio:
        record.bio = bio
    if service_details:
        record.service_details = service_details
    if languages:
        record.languages = languages
    if years_of_practice is not None:
        record.years_of_practice = years_of_practice
    if hospital_affiliations:
        record.hospital_affiliations = hospital_affiliations
    if board_certifications:
        record.board_certifications = board_certifications
    if awards:
        record.awards = awards
    if insurance_tpa:
        record.insurance_tpa = insurance_tpa
    if insurance_shield_plan:
        record.insurance_shield_plan = insurance_shield_plan
    if contact_name:
        record.contact_name = contact_name
    if contact_email:
        record.contact_email = contact_email
    if contact_phone:
        record.contact_phone = contact_phone
    if available_days:
        record.available_days = available_days
    if available_time_slots:
        record.available_time_slots = available_time_slots
    if active is not None:
        record.active = active.lower() == "true" if isinstance(active, str) else bool(active)
    if display_order is not None:
        record.display_order = display_order
    
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{service_id}")
def delete(service_id: int, db: Session = Depends(get_db)):
    record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ClinicService not found")
    db.delete(record)
    db.commit()
    return {"message": "ClinicService deleted"}
