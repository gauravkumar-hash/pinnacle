from datetime import date, datetime
from pydantic import BaseModel
from models.delivery import DeliveryZone, DeliveryStatus
from typing import Any, Optional

class TeleconsultDeliveryResponse(BaseModel):
    id: str
    zone: DeliveryZone
    address: str
    postal: str
    is_migrant_area: bool
    status: DeliveryStatus
    dispatch_history: list[dict[str, Any]]
    is_migrant: bool
    number_of_packages: Optional[int] = None
    delivery_date: Optional[date] = None
    delivery_attempt: int
    recipient_name: Optional[str] = None
    patient_name: Optional[str] = None
    patient_nric: Optional[str] = None
    sgimed_patient_id: Optional[str] = None
    phone_number: Optional[str] = None
    patient_queue_number: Optional[str] = None
    dispatch_name: Optional[str] = None
    receipt_date: Optional[datetime] = None
    is_delivery_note_exists: bool
    delivery_note_file_path: Optional[str] = None
    consultation_date: Optional[datetime] = None

class TeleconsultDeliveryFamily(TeleconsultDeliveryResponse):
    combined_queue_number: Optional[str] = None
    combined_nric: Optional[str] = None
    combined_name: Optional[str] = None
    combined_sgimed_patient_id: Optional[str] = None
    dispatch_name: Optional[str] = None

class DriverFetchingResponse(BaseModel):
    id: str 
    name: str

class LogisticsFetchingResponse(BaseModel):
    deliveries: list[TeleconsultDeliveryResponse]
    drivers: list[DriverFetchingResponse]

class UpdateTeleconsultDeliveryStatusRequest(BaseModel):
    id: str
    status: DeliveryStatus
    recipient_name: Optional[str] = None
    
class UpdateBulkTeleconsultDeliveryStatusRequest(BaseModel):
    ids: list[str]
    status: DeliveryStatus
    driver_id: str

class UpdateTeleconsultDeliveryRequest(BaseModel):
    id: str
    zone: Optional[DeliveryZone] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    number_of_package: int
    date_of_delivery: date
    number_of_attempt: Optional[int] = None

class DispatchUpdateTeleconsultDeliveryStatusRequest(BaseModel):
    id: str
    success: bool
    recipient_name: Optional[str] = None
