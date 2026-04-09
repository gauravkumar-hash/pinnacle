from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from models.specialist import Specialist
from schemas.specialist import SpecialistCreate, SpecialistUpdate, SpecialistResponse
from models import get_db
from config import SUPABASE_UPLOAD_BUCKET, supabase
import os.path as osp
import uuid
import re

router = APIRouter(prefix="/specialists", tags=["Specialists"])


@router.get("/", response_model=List[SpecialistResponse])
def get_all(db: Session = Depends(get_db)):
    return db.query(Specialist).order_by(Specialist.display_order).all()


@router.get("/active", response_model=List[SpecialistResponse])
def get_active(db: Session = Depends(get_db)):
    return (
        db.query(Specialist)
        .filter(Specialist.active == True)
        .order_by(Specialist.display_order)
        .all()
    )


@router.get("/by-specialisation/{specialisation_id}", response_model=List[SpecialistResponse])
def get_by_specialisation(specialisation_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Specialist)
        .options(joinedload(Specialist.specialisation))
        .filter(
            Specialist.specialisation_id == specialisation_id,
            Specialist.active == True
        )
        .order_by(Specialist.display_order)
        .all()
    )


@router.get("/{specialist_id}", response_model=SpecialistResponse)
def get_one(specialist_id: int, db: Session = Depends(get_db)):
    record = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialist not found")
    return record


@router.post("/", response_model=SpecialistResponse)
async def create(
    specialisation_id: int = Form(...),
    title: str = Form(""),
    name: str = Form(...),
    credentials: str = Form(""),
    short_bio: str = Form(""),
    full_bio: str = Form(""),
    languages: str = Form(""),
    appointment_email: str = Form(...),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    available_days: str = Form(""),
    available_time_slots: str = Form(""),
    insurance: str = Form(""),
    display_order: int = Form(0),
    active: str = Form("true"),
    image: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """Create a new specialist with optional image upload"""
    image_url = None
    
    # Convert string boolean to actual boolean
    active_bool = active.lower() == "true" if isinstance(active, str) else bool(active)
    
    # Handle image upload if provided
    if image and image.filename:
        # Sanitize the specialist name for filename
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        image_filename = f'specialists/{sanitized_name}_{uuid.uuid4()}{osp.splitext(image.filename)[-1]}'
        image_bytes = await image.read()
        content_type = image.content_type if image.content_type else 'image/jpeg'
        
        resp = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=image_bytes,
            path=image_filename,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(image_filename)
    
    # Create specialist record
    record = Specialist(
        specialisation_id=specialisation_id,
        title=title if title else None,
        name=name,
        image_url=image_url,
        credentials=credentials if credentials else None,
        short_bio=short_bio if short_bio else None,
        full_bio=full_bio if full_bio else None,
        languages=languages if languages else None,
        appointment_email=appointment_email,
        contact_email=contact_email if contact_email else None,
        contact_phone=contact_phone if contact_phone else None,
        available_days=available_days if available_days else None,
        available_time_slots=available_time_slots if available_time_slots else None,
        insurance=insurance if insurance else None,
        display_order=display_order,
        active=active_bool
    )
    
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{specialist_id}", response_model=SpecialistResponse)
async def update(
    specialist_id: int,
    specialisation_id: Optional[int] = Form(None),
    title: str = Form(""),
    name: str = Form(""),
    credentials: str = Form(""),
    short_bio: str = Form(""),
    full_bio: str = Form(""),
    languages: str = Form(""),
    appointment_email: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    available_days: str = Form(""),
    available_time_slots: str = Form(""),
    insurance: str = Form(""),
    display_order: Optional[int] = Form(None),
    active: Optional[str] = Form(None),
    image: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """Update a specialist with optional image upload"""
    record = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialist not found")
    
    # Handle image upload if provided
    if image and image.filename:
        # Sanitize the specialist name for filename
        current_name = name if name else record.name
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', current_name)
        image_filename = f'specialists/{sanitized_name}_{uuid.uuid4()}{osp.splitext(image.filename)[-1]}'
        image_bytes = await image.read()
        content_type = image.content_type if image.content_type else 'image/jpeg'
        
        resp = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=image_bytes,
            path=image_filename,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        record.image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(image_filename)
    
    # Update other fields if provided
    if specialisation_id is not None:
        record.specialisation_id = specialisation_id
    if title:
        record.title = title
    if name:
        record.name = name
    if credentials:
        record.credentials = credentials
    if short_bio:
        record.short_bio = short_bio
    if full_bio:
        record.full_bio = full_bio
    if languages:
        record.languages = languages
    if appointment_email:
        record.appointment_email = appointment_email
    if contact_email:
        record.contact_email = contact_email
    if contact_phone:
        record.contact_phone = contact_phone
    if available_days:
        record.available_days = available_days
    if available_time_slots:
        record.available_time_slots = available_time_slots
    if insurance:
        record.insurance = insurance
    if display_order is not None:
        record.display_order = display_order
    if active is not None:
        record.active = active.lower() == "true" if isinstance(active, str) else bool(active)
    
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{specialist_id}")
def delete(specialist_id: int, db: Session = Depends(get_db)):
    record = db.query(Specialist).filter(Specialist.id == specialist_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialist not found")
    db.delete(record)
    db.commit()
    return {"message": "Specialist deleted"}
