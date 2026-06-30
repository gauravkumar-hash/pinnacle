from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional, List, Literal
from datetime import datetime
from models.appointment_request import RequestStatus
from .service import ServiceBasic


class SpecialistBasic(BaseModel):
    id: int
    name: str
    title: Optional[str] = None
    image_url: Optional[str] = None

    model_config = {"from_attributes": True}


class AppointmentRequestBase(BaseModel):
    specialisation_id: int
    specialist_id: Optional[int] = None
    service_id: Optional[int] = None
    patient_name: str
    patient_dob: Optional[str] = None
    contact_number: str
    email: EmailStr
    preferred_days: Optional[str] = None
    preferred_time: Optional[str] = None
    reason: Optional[str] = None


class AppointmentRequestCreate(AppointmentRequestBase):
    @model_validator(mode="after")
    def validate_single_booking_target(self):
        has_specialist = self.specialist_id is not None
        has_service = self.service_id is not None
        if has_specialist == has_service:
            raise ValueError("Provide exactly one of specialist_id or service_id")
        return self


class AppointmentRequestStatusUpdate(BaseModel):
    status: RequestStatus
    status_message: Optional[str] = None


class AppointmentRescheduleRequest(BaseModel):
    preferred_days: str
    preferred_time: str


class AppointmentCancelRequest(BaseModel):
    reason: str


class AppointmentRequestResponse(AppointmentRequestBase):
    id: int
    booking_type: Literal["doctor", "service", "unknown"]
    status: RequestStatus
    status_message: Optional[str] = None
    submitted_at: datetime
    updated_at: Optional[datetime] = None
    specialist: Optional[SpecialistBasic] = None
    service: Optional[ServiceBasic] = None
    date: str
    time_slot: str

    model_config = {"from_attributes": True}
