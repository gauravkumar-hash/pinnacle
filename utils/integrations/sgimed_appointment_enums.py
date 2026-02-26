from typing import Optional
from pydantic import BaseModel

class Pager(BaseModel):
    p: int
    n: int
    pages: int
    rows: int

class SgimedAppointmentPatient(BaseModel):
    id: str
    name: str
    email: Optional[str]
    nric: Optional[str]
    mobile: Optional[str]

class SgimedAppointmentGuest(BaseModel):
    name: Optional[str]
    nric: Optional[str]
    phone: Optional[str]
    email: Optional[str]

class SgimedIdName(BaseModel):
    id: str
    name: Optional[str]

class SgimedAppointmentCode(BaseModel):
    title: str
    value: str
    color: str

class GetSgimedAppointmentResp(BaseModel):
    id: str
    subject: Optional[str]
    description: Optional[str]
    location: Optional[str]
    patient: Optional[SgimedAppointmentPatient]
    guest: Optional[SgimedAppointmentGuest]
    branch_id: str
    doctor: Optional[SgimedIdName]
    appointment_type: SgimedIdName
    facility: Optional[SgimedIdName]
    calendars: list[SgimedIdName]
    is_all_day: bool
    is_informed: bool
    is_cancelled: bool
    is_queued: bool
    is_confirmed: bool
    confirm_user: Optional[str]
    confirm_time: Optional[str]
    start_date: str
    start_time: str
    end_date: str
    end_time: str
    last_edited: str
    created_at: str
    code_top: Optional[SgimedAppointmentCode]
    code_bottom: Optional[SgimedAppointmentCode]
    code_right: Optional[SgimedAppointmentCode]
    code_left: Optional[SgimedAppointmentCode]
    code_background: Optional[SgimedAppointmentCode]
