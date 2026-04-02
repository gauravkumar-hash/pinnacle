from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


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
    display_order: Optional[int] = None
    active: Optional[bool] = None


class SpecialistResponse(SpecialistBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}