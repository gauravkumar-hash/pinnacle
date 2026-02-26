from pydantic import BaseModel
from models.delivery import DeliveryZone
from typing import Optional, List

class CreatePinnacleZoneRequest(BaseModel):
    sector_code_start: str
    sector_code_end: Optional[str] = None
    has_service: bool
    zone: DeliveryZone

class GetPinnacleZoneResponse(BaseModel):
    sector_code: str
    zone: DeliveryZone

class ZoneResponse(BaseModel):
    zone: DeliveryZone
    sector_code_range: list[str]
    no_service_code_list: list[str]
    migrant_area_code_list: list[str]

class GetPinnacleZonesResponse(BaseModel):
    # pinnacle_zones: list[GetPinnacleZoneResponse]
    missing_sector_codes: list[str]
    # existing_sector_code_ranges: List[str]
    sector_code_ranges_by_zone: List[ZoneResponse]

class EditPinnacleZoneRequest(BaseModel):
    sector_code_list: list[str]
    sector_code_without_service: list[str]
    migrant_area_code_list: list[str]
    zone: DeliveryZone

class UpdatePinnacleZoneRequest(BaseModel):
    sector_code: list[str]
    zone: DeliveryZone

class ConfigurePinnacleZoneRequest(BaseModel):
    sector_code: list[str]
    zone: DeliveryZone

class DeletePinnacleZoneRequest(BaseModel):
    sector_code_range: str

class DeletePinnacleZoneByListRequest(BaseModel):
    sector_code_list: list[str]