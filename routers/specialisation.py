from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from models.specialisation import Specialisation
from models.specialist import Specialist
from models.service import ClinicService
from schemas.specialisation import (
    SpecialisationCreate,
    SpecialisationUpdate,
    SpecialisationResponse
)
from models import get_db
from config import SUPABASE_UPLOAD_BUCKET, supabase
import os.path as osp
import uuid
import re

router = APIRouter(prefix="/specialisations", tags=["Specialisations"])


def _get_active_specialists(record: Specialisation, db: Session):
    return (
        db.query(Specialist)
        .filter(Specialist.specialisation_id == record.id, Specialist.active == True)
        .order_by(Specialist.display_order)
        .all()
    )


def _get_active_services(record: Specialisation, db: Session):
    return (
        db.query(ClinicService)
        .filter(ClinicService.specialisation_id == record.id, ClinicService.active == True)
        .order_by(ClinicService.display_order.asc(), ClinicService.id.asc())
        .all()
    )


def _specialisation_response(
    record: Specialisation,
    db: Session,
    include_specialists: bool,
    include_services: bool,
    include_items: bool,
):
    data = {
        "id": record.id,
        "name": record.name,
        "slug": record.slug,
        "description": record.description,
        "icon_url": record.icon_url,
        "banner_url": record.banner_url,
        "display_mode": record.display_mode,
        "display_order": record.display_order,
        "active": record.active,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
    if include_specialists:
        data["specialists"] = _get_active_specialists(record, db)
    if include_services:
        data["services"] = _get_active_services(record, db)
    if include_items:
        if record.display_mode == "services":
            data["services"] = _get_active_services(record, db)
        else:
            data["specialists"] = _get_active_specialists(record, db)
    return data


@router.get("/", response_model=List[SpecialisationResponse])
def get_all(
    include_specialists: bool = False,
    include_services: bool = False,
    include_items: bool = False,
    db: Session = Depends(get_db),
):
    records = db.query(Specialisation).order_by(Specialisation.display_order).all()
    return [
        _specialisation_response(
            r,
            db,
            include_specialists,
            include_services,
            include_items,
        )
        for r in records
    ]


@router.get("/active", response_model=List[SpecialisationResponse])
def get_active(
    include_specialists: bool = False,
    include_services: bool = False,
    include_items: bool = False,
    db: Session = Depends(get_db),
):
    records = (
        db.query(Specialisation)
        .filter(Specialisation.active == True)
        .order_by(Specialisation.display_order)
        .all()
    )
    return [
        _specialisation_response(
            r,
            db,
            include_specialists,
            include_services,
            include_items,
        )
        for r in records
    ]


@router.get("/{specialisation_id}", response_model=SpecialisationResponse)
def get_one(
    specialisation_id: int,
    include_specialists: bool = False,
    include_services: bool = False,
    include_items: bool = False,
    db: Session = Depends(get_db),
):
    record = db.query(Specialisation).filter(Specialisation.id == specialisation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialisation not found")
    return _specialisation_response(
        record,
        db,
        include_specialists,
        include_services,
        include_items,
    )


@router.post("/", response_model=SpecialisationResponse)
async def create(
    name: str = Form(...),
    slug: str = Form(...),
    description: str = Form(""),
    display_mode: str = Form("doctors"),
    display_order: int = Form(0),
    active: str = Form("true"),
    icon: Optional[UploadFile] = None,
    banner: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    icon_url = None
    banner_url = None
    
    # Convert string boolean to actual boolean
    active_bool = active.lower() == "true" if isinstance(active, str) else bool(active)
    
    # Handle icon upload
    if icon and icon.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', slug)
        icon_filename = f'specialisations/icons/{sanitized_name}_{uuid.uuid4()}{osp.splitext(icon.filename)[-1]}'
        icon_bytes = await icon.read()
        content_type = icon.content_type if icon.content_type else 'image/jpeg'
        
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=icon_bytes,
            path=icon_filename,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        icon_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(icon_filename)
    
    # Handle banner upload
    if banner and banner.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', slug)
        banner_filename = f'specialisations/banners/{sanitized_name}_{uuid.uuid4()}{osp.splitext(banner.filename)[-1]}'
        banner_bytes = await banner.read()
        content_type = banner.content_type if banner.content_type else 'image/jpeg'
        
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=banner_bytes,
            path=banner_filename,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        banner_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(banner_filename)
    
    record = Specialisation(
        name=name,
        slug=slug,
        description=description if description else None,
        icon_url=icon_url,
        banner_url=banner_url,
        display_mode=display_mode if display_mode in ("doctors", "services") else "doctors",
        display_order=display_order,
        active=active_bool
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{specialisation_id}", response_model=SpecialisationResponse)
async def update(
    specialisation_id: int,
    name: str = Form(""),
    slug: str = Form(""),
    description: str = Form(""),
    display_mode: Optional[str] = Form(None),
    display_order: Optional[int] = Form(None),
    active: Optional[str] = Form(None),
    icon: Optional[UploadFile] = None,
    banner: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    record = db.query(Specialisation).filter(Specialisation.id == specialisation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialisation not found")
    
    # Handle icon upload
    if icon and icon.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', slug or record.slug)
        icon_filename = f'specialisations/icons/{sanitized_name}_{uuid.uuid4()}{osp.splitext(icon.filename)[-1]}'
        icon_bytes = await icon.read()
        content_type = icon.content_type if icon.content_type else 'image/jpeg'
        
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=icon_bytes,
            path=icon_filename,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        record.icon_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(icon_filename)
    
    # Handle banner upload
    if banner and banner.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', slug or record.slug)
        banner_filename = f'specialisations/banners/{sanitized_name}_{uuid.uuid4()}{osp.splitext(banner.filename)[-1]}'
        banner_bytes = await banner.read()
        content_type = banner.content_type if banner.content_type else 'image/jpeg'
        
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=banner_bytes,
            path=banner_filename,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        record.banner_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(banner_filename)
    
    # Update other fields
    if name:
        record.name = name
    if slug:
        record.slug = slug
    if description:
        record.description = description
    if display_mode is not None:
        if display_mode not in ("doctors", "services"):
            raise HTTPException(status_code=422, detail="display_mode must be 'doctors' or 'services'")
        record.display_mode = display_mode
    if display_order is not None:
        record.display_order = display_order
    if active is not None:
        record.active = active.lower() == "true" if isinstance(active, str) else bool(active)
    
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{specialisation_id}")
def delete(specialisation_id: int, db: Session = Depends(get_db)):
    record = db.query(Specialisation).filter(Specialisation.id == specialisation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Specialisation not found")
    db.delete(record)
    db.commit()
    return {"message": "Specialisation deleted"}
