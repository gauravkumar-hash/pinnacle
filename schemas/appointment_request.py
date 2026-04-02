from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from models.appointment_request import RequestStatus


class AppointmentRequestBase(BaseModel):
    specialisation_id: int
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

    model_config = {"from_attributes": True}