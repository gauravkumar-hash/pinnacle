from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from models.appointment_request import RequestStatus


class SpecialistBasic(BaseModel):
    id: int
    name: str
    title: Optional[str] = None
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AppointmentRequestBase(BaseModel):
    specialisation_id: int        # was category_id — match the model field name
    specialist_id: int
    patient_name: str
    patient_dob: Optional[str] = None
    contact_number: str
    email: EmailStr
    preferred_days: Optional[str] = None
    preferred_time: Optional[str] = None
    reason: Optional[str] = None


class AppointmentRequestCreate(AppointmentRequestBase):
    pass


class AppointmentRequestStatusUpdate(BaseModel):
    status: RequestStatus
    status_message: Optional[str] = None


class AppointmentRequestResponse(AppointmentRequestBase):
    id: int
    status: RequestStatus
    status_message: Optional[str] = None
    submitted_at: datetime
    updated_at: Optional[datetime] = None
    specialist: Optional[SpecialistBasic] = None

    model_config = {"from_attributes": True}
