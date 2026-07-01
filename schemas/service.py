from pydantic import BaseModel, EmailStr
from typing import Dict, List, Optional
from datetime import datetime
from .specialist import SpecialisationBasic, DayAvailability


class ServiceBase(BaseModel):
    specialisation_id: int
    service_name: str
    clinic_name: str
    consultation_fee: Optional[str] = None
    clinic_photo_path: Optional[str] = None
    banner_image_path: Optional[str] = None

    bio: Optional[str] = None
    service_details: Optional[str] = None
    languages: Optional[str] = None
    years_of_practice: Optional[int] = None
    hospital_affiliations: Optional[str] = None
    board_certifications: Optional[str] = None
    awards: Optional[str] = None
    insurance_tpa: Optional[str] = None
    insurance_shield_plan: Optional[str] = None

    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    available_days: Optional[str] = None
    available_time_slots: Optional[str] = None
    day_availability: Optional[Dict[str, DayAvailability]] = None

    active: bool = True
    display_order: int = 0


class ServiceCreate(ServiceBase):
    pass


class ServiceUpdate(BaseModel):
    specialisation_id: Optional[int] = None
    service_name: Optional[str] = None
    clinic_name: Optional[str] = None
    consultation_fee: Optional[str] = None
    clinic_photo_path: Optional[str] = None
    banner_image_path: Optional[str] = None

    bio: Optional[str] = None
    service_details: Optional[str] = None
    languages: Optional[str] = None
    years_of_practice: Optional[int] = None
    hospital_affiliations: Optional[str] = None
    board_certifications: Optional[str] = None
    awards: Optional[str] = None
    insurance_tpa: Optional[str] = None
    insurance_shield_plan: Optional[str] = None

    contact_name: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    available_days: Optional[str] = None
    available_time_slots: Optional[str] = None
    day_availability: Optional[Dict[str, DayAvailability]] = None

    active: Optional[bool] = None


class ServiceBasic(BaseModel):
    id: int
    service_name: str
    clinic_name: str

    model_config = {"from_attributes": True}


class ServiceResponse(ServiceBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    specialisation: Optional[SpecialisationBasic] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_name(cls, obj):
        data = cls.model_validate(obj)
        data.specialisation_name = obj.specialisation.name if obj.specialisation else None
        return data
