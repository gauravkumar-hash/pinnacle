from pydantic import BaseModel, EmailStr
from typing import Dict, List, Optional
from datetime import datetime


DayAvailability = List[str]


class SpecialistBase(BaseModel):
    specialisation_id: int
    title: Optional[str] = None
    name: str
    image_url: Optional[str] = None
    credentials: Optional[str] = None
    short_bio: Optional[str] = None
    full_bio: Optional[str] = None
    languages: Optional[str] = None
    appointment_email: EmailStr
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    available_days: Optional[str] = None
    available_time_slots: Optional[str] = None
    day_availability: Optional[Dict[str, DayAvailability]] = None
    clinic_name: str
    clinic_photo_path: Optional[str] = None
    banner_image_path: Optional[str] = None
    consultation_fee: Optional[str] = None
    years_of_practice: Optional[int] = None
    hospital_affiliations: Optional[str] = None
    board_certifications: Optional[str] = None
    awards: Optional[str] = None
    insurance_tpa: Optional[str] = None
    insurance_shield_plan: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    display_order: int = 0
    active: bool = True


class SpecialistCreate(SpecialistBase):
    pass


class SpecialistUpdate(BaseModel):
    specialisation_id: Optional[int] = None
    title: Optional[str] = None
    name: Optional[str] = None
    image_url: Optional[str] = None
    credentials: Optional[str] = None
    short_bio: Optional[str] = None
    full_bio: Optional[str] = None
    languages: Optional[str] = None
    appointment_email: Optional[EmailStr] = None
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = None
    available_days: Optional[str] = None
    available_time_slots: Optional[str] = None
    day_availability: Optional[Dict[str, DayAvailability]] = None
    clinic_name: Optional[str] = None
    clinic_photo_path: Optional[str] = None
    banner_image_path: Optional[str] = None
    consultation_fee: Optional[str] = None
    years_of_practice: Optional[int] = None
    hospital_affiliations: Optional[str] = None
    board_certifications: Optional[str] = None
    awards: Optional[str] = None
    insurance_tpa: Optional[str] = None
    insurance_shield_plan: Optional[str] = None
    cc_emails: Optional[List[str]] = None
    display_order: Optional[int] = None
    active: Optional[bool] = None


class SpecialisationBasic(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


class SpecialistResponse(SpecialistBase):
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
