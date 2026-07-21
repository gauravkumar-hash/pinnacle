from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel
from datetime import date, datetime
from utils import sg_datetime
from models.service import ClinicService
from models.specialist import Specialist
from models.specialisation import Specialisation
from models.appointment_request import AppointmentRequest
from schemas.service import ServiceResponse
from schemas.specialist import SpecialistResponse, SpecialisationBasic
from models import get_db
from config import SUPABASE_UPLOAD_BUCKET, supabase
import json
import os.path as osp
import uuid
import re

router = APIRouter(tags=["Services"])


def parse_cc_emails(raw: Optional[str]) -> Optional[List[str]]:
    """Accepts a JSON array string or a comma-separated string of emails."""
    if not raw or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = raw.split(",")
    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise HTTPException(status_code=422, detail="cc_emails must be a JSON array or comma-separated string")
    emails = [str(e).strip() for e in parsed if str(e).strip()]
    return emails or None


def parse_blocked_dates(raw: Optional[str]) -> Optional[List[str]]:
    """Accepts a JSON array string or a comma-separated string of ISO dates."""
    if raw is None:
        return None
    if not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = raw.split(",")
    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise HTTPException(status_code=422, detail="blocked_dates must be a JSON array or comma-separated string of YYYY-MM-DD dates")
    dates = []
    for item in parsed:
        value = str(item).strip()
        if not value:
            continue
        try:
            dates.append(date.fromisoformat(value).isoformat())
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid blocked date '{value}', expected YYYY-MM-DD")
    return sorted(set(dates))


def apply_block(record: Union[ClinicService, Specialist], block_date: Optional[date], blocked: bool) -> str:
    """Add/remove a single blocked date (defaults to today, SG time), pruning past dates."""
    today = sg_datetime.now().date()
    target = block_date or today
    dates = {d for d in (record.blocked_dates or []) if d >= today.isoformat()}
    if blocked:
        dates.add(target.isoformat())
    else:
        dates.discard(target.isoformat())
    record.blocked_dates = sorted(dates)
    flag_modified(record, "blocked_dates")
    return target.isoformat()


class UnifiedServiceResponse(BaseModel):
    """Normalized response for both ClinicService and Specialist lookups."""
    id: int
    type: Literal["service", "specialist"]
    specialisation_id: int
    service_name: str          # maps to ClinicService.service_name or Specialist.name
    clinic_name: str
    consultation_fee: Optional[str] = None
    clinic_logo_path: Optional[str] = None
    banner_image_path: Optional[str] = None
    image_url: Optional[str] = None          # service photo or specialist profile photo
    title: Optional[str] = None              # specialist title e.g. "Assoc Prof"
    credentials: Optional[str] = None
    bio: Optional[str] = None                # maps to ClinicService.bio or Specialist.short_bio
    full_bio: Optional[str] = None           # specialist only
    service_details: Optional[str] = None    # service only
    languages: Optional[str] = None
    years_of_practice: Optional[int] = None
    hospital_affiliations: Optional[str] = None
    board_certifications: Optional[str] = None
    awards: Optional[str] = None
    insurance_tpa: Optional[str] = None
    insurance_shield_plan: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    available_days: Optional[str] = None
    available_time_slots: Optional[str] = None
    day_availability: Optional[Dict[str, Any]] = None
    active: bool
    blocked_dates: Optional[List[str]] = None
    blocked_today: bool = False
    display_order: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    specialisation: Optional[SpecialisationBasic] = None

    model_config = {"from_attributes": True}


def _service_to_unified(record: ClinicService) -> UnifiedServiceResponse:
    return UnifiedServiceResponse(
        id=record.id,
        type="service",
        specialisation_id=record.specialisation_id,
        service_name=record.service_name,
        clinic_name=record.clinic_name,
        consultation_fee=record.consultation_fee,
        clinic_logo_path=record.clinic_logo_path,
        banner_image_path=record.banner_image_path,
        image_url=record.image_url,
        title=None,
        credentials=None,
        bio=record.bio,
        full_bio=None,
        service_details=record.service_details,
        languages=record.languages,
        years_of_practice=record.years_of_practice,
        hospital_affiliations=record.hospital_affiliations,
        board_certifications=record.board_certifications,
        awards=record.awards,
        insurance_tpa=record.insurance_tpa,
        insurance_shield_plan=record.insurance_shield_plan,
        contact_name=record.contact_name,
        contact_email=record.contact_email,
        contact_phone=record.contact_phone,
        cc_emails=record.cc_emails,
        available_days=record.available_days,
        available_time_slots=record.available_time_slots,
        day_availability=record.day_availability,
        active=record.active,
        blocked_dates=record.blocked_dates,
        blocked_today=record.blocked_today,
        display_order=record.display_order,
        created_at=record.created_at,
        updated_at=record.updated_at,
        specialisation=SpecialisationBasic.model_validate(record.specialisation) if record.specialisation else None,
    )


def _specialist_to_unified(record: Specialist) -> UnifiedServiceResponse:
    return UnifiedServiceResponse(
        id=record.id,
        type="specialist",
        specialisation_id=record.specialisation_id,
        service_name=record.name,
        clinic_name=record.clinic_name,
        consultation_fee=record.consultation_fee,
        clinic_logo_path=record.clinic_logo_path,
        banner_image_path=record.banner_image_path,
        image_url=record.image_url,
        title=record.title,
        credentials=record.credentials,
        bio=record.short_bio,
        full_bio=record.full_bio,
        service_details=None,
        languages=record.languages,
        years_of_practice=record.years_of_practice,
        hospital_affiliations=record.hospital_affiliations,
        board_certifications=record.board_certifications,
        awards=record.awards,
        insurance_tpa=record.insurance_tpa,
        insurance_shield_plan=record.insurance_shield_plan,
        contact_name=None,
        contact_email=record.contact_email,
        contact_phone=record.contact_phone,
        cc_emails=record.cc_emails,
        available_days=record.available_days,
        available_time_slots=record.available_time_slots,
        day_availability=record.day_availability,
        active=record.active,
        blocked_dates=record.blocked_dates,
        blocked_today=record.blocked_today,
        display_order=record.display_order,
        created_at=record.created_at,
        updated_at=record.updated_at,
        specialisation=SpecialisationBasic.model_validate(record.specialisation) if record.specialisation else None,
    )


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


@router.get("/{service_id}", response_model=UnifiedServiceResponse)
def get_one(
    service_id: int,
    type: Optional[Literal["service", "specialist"]] = None,
    db: Session = Depends(get_db),
):
    """
    Returns a unified response for both ClinicService and Specialist.
    Pass ?type=specialist or ?type=service to force a specific table.
    Without ?type, tries ClinicService first then Specialist automatically.
    """
    if type == "specialist":
        record = db.query(Specialist).filter(Specialist.id == service_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Specialist not found")
        return _specialist_to_unified(record)

    if type == "service":
        record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Service not found")
        return _service_to_unified(record)

    # Auto-detect: try ClinicService first, then Specialist
    service = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if service:
        return _service_to_unified(service)
    specialist = db.query(Specialist).filter(Specialist.id == service_id).first()
    if specialist:
        return _specialist_to_unified(specialist)
    raise HTTPException(status_code=404, detail="Service or Specialist not found")


@router.post("/", response_model=ServiceResponse)
async def create(
    specialisation_id: int = Form(...),
    service_name: str = Form(...),
    clinic_name: str = Form(...),
    consultation_fee: Optional[str] = Form(None),
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
    cc_emails: Optional[str] = Form(None),
    available_days: str = Form(""),
    available_time_slots: str = Form(""),
    day_availability: Optional[str] = Form(None),
    blocked_dates: Optional[str] = Form(None),
    active: str = Form("true"),
    display_order: int = Form(0),
    image: Optional[UploadFile] = None,
    clinic_logo: Optional[UploadFile] = None,
    banner_image: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """Create a new service with optional image upload"""
    specialisation = (
        db.query(Specialisation)
        .filter(Specialisation.id == specialisation_id)
        .first()
    )
    if not specialisation:
        raise HTTPException(status_code=404, detail="Specialisation not found")
    if specialisation.display_mode != "services":
        raise HTTPException(
            status_code=400,
            detail="This specialisation is set to display doctors/specialists, not services. "
                   "Set its display mode to 'services' before adding a service.",
        )

    # Convert string boolean to actual boolean
    active_bool = active.lower() == "true" if isinstance(active, str) else bool(active)

    image_url = None
    if image and image.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', service_name)
        filename = f'services/{sanitized_name}_{uuid.uuid4()}{osp.splitext(image.filename)[-1]}'
        bytes_data = await image.read()
        ctype = image.content_type if image.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)

    clinic_logo_url = None
    if clinic_logo and clinic_logo.filename:
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', service_name)
        filename = f'services/{sanitized_name}_logo_{uuid.uuid4()}{osp.splitext(clinic_logo.filename)[-1]}'
        bytes_data = await clinic_logo.read()
        ctype = clinic_logo.content_type if clinic_logo.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        clinic_logo_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)
        
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
        image_url=image_url,
        clinic_logo_path=clinic_logo_url,
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
        cc_emails=parse_cc_emails(cc_emails),
        available_days=available_days if available_days else None,
        available_time_slots=available_time_slots if available_time_slots else None,
        day_availability=json.loads(day_availability) if day_availability else None,
        blocked_dates=parse_blocked_dates(blocked_dates),
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
    consultation_fee: Optional[str] = Form(None),
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
    cc_emails: Optional[str] = Form(None),
    available_days: str = Form(""),
    available_time_slots: str = Form(""),
    day_availability: Optional[str] = Form(None),
    blocked_dates: Optional[str] = Form(None),
    active: Optional[str] = Form(None),
    display_order: Optional[int] = Form(None),
    image: Optional[UploadFile] = None,
    clinic_logo: Optional[UploadFile] = None,
    banner_image: Optional[UploadFile] = None,
    db: Session = Depends(get_db)
):
    """Update a service with optional image upload"""
    record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ClinicService not found")

    if specialisation_id is not None:
        specialisation = (
            db.query(Specialisation)
            .filter(Specialisation.id == specialisation_id)
            .first()
        )
        if not specialisation:
            raise HTTPException(status_code=404, detail="Specialisation not found")
        if specialisation.display_mode != "services":
            raise HTTPException(
                status_code=400,
                detail="This specialisation is set to display doctors/specialists, not services. "
                       "Set its display mode to 'services' before moving a service into it.",
            )

    if image and image.filename:
        current_name = service_name if service_name else record.service_name
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', current_name)
        filename = f'services/{sanitized_name}_{uuid.uuid4()}{osp.splitext(image.filename)[-1]}'
        bytes_data = await image.read()
        ctype = image.content_type if image.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        record.image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)

    if clinic_logo and clinic_logo.filename:
        current_name = service_name if service_name else record.service_name
        sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', current_name)
        filename = f'services/{sanitized_name}_logo_{uuid.uuid4()}{osp.splitext(clinic_logo.filename)[-1]}'
        bytes_data = await clinic_logo.read()
        ctype = clinic_logo.content_type if clinic_logo.content_type else 'image/jpeg'
        supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=bytes_data, path=filename, file_options={"content-type": ctype, "upsert": "true"}
        )
        record.clinic_logo_path = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(filename)

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
    record.bio = bio if bio else None
    record.service_details = service_details if service_details else None
    record.languages = languages if languages else None
    if years_of_practice is not None:
        record.years_of_practice = years_of_practice
    record.hospital_affiliations = hospital_affiliations if hospital_affiliations else None
    record.board_certifications = board_certifications if board_certifications else None
    record.awards = awards if awards else None
    record.insurance_tpa = insurance_tpa if insurance_tpa else None
    record.insurance_shield_plan = insurance_shield_plan if insurance_shield_plan else None
    record.contact_name = contact_name if contact_name else None
    record.contact_email = contact_email if contact_email else None
    record.contact_phone = contact_phone if contact_phone else None
    if cc_emails is not None:
        record.cc_emails = parse_cc_emails(cc_emails)
    record.available_days = available_days if available_days else None
    record.available_time_slots = available_time_slots if available_time_slots else None
    if day_availability is not None:
        record.day_availability = json.loads(day_availability)
    if blocked_dates is not None:
        record.blocked_dates = parse_blocked_dates(blocked_dates)
    if active is not None:
        record.active = active.lower() == "true" if isinstance(active, str) else bool(active)
    if display_order is not None:
        record.display_order = display_order

    db.commit()
    db.refresh(record)
    return record


@router.post("/{service_id}/block", response_model=ServiceResponse)
def block_for_date(
    service_id: int,
    block_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
):
    """Block a service for a single date (defaults to today). The service
    stays visible and bookable for other dates — use `active` only for
    permanent deactivation."""
    record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ClinicService not found")
    apply_block(record, block_date, blocked=True)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{service_id}/unblock", response_model=ServiceResponse)
def unblock_for_date(
    service_id: int,
    block_date: Optional[date] = Form(None),
    db: Session = Depends(get_db),
):
    """Remove a blocked date (defaults to today) from a service."""
    record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ClinicService not found")
    apply_block(record, block_date, blocked=False)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{service_id}")
def delete(service_id: int, db: Session = Depends(get_db)):
    record = db.query(ClinicService).filter(ClinicService.id == service_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="ClinicService not found")

    linked_count = db.query(AppointmentRequest).filter(
        AppointmentRequest.service_id == service_id
    ).count()
    if linked_count:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete: {linked_count} appointment request(s) reference this service",
        )

    db.delete(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Cannot delete this service because it is referenced by other records",
        )
    return {"message": "ClinicService deleted"}
