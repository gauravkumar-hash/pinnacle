from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.delivery import DeliveryZone
from utils.fastapi import SuccessResp
from routers.delivery.typings.zone import (
    GetPinnacleZonesResponse,
    ZoneResponse,
    EditPinnacleZoneRequest,
)
from models.delivery import PinnacleZone
from collections import defaultdict
from pydantic import BaseModel

def group_sector_codes_into_ranges(codes: set[str]) -> list[str]:
    # Convert to sorted list of integers
    sorted_codes = sorted(int(code) for code in codes)
    ranges = []
    if not sorted_codes:
        return ranges
    start = prev = sorted_codes[0]
    for code in sorted_codes[1:]:
        if code != prev + 1:
            if start == prev:
                ranges.append(f"{start:02d}")
            else:
                ranges.append(f"{start:02d}-{prev:02d}")
            start = code
        prev = code
    # Handle the last range
    if start == prev:
        ranges.append(f"{start:02d}")
    else:
        ranges.append(f"{start:02d}-{prev:02d}")
    return ranges


def get_missing_sector_codes(existing_sector_codes: set[str]) -> list[str]:
    # Generate list of all expected sector codes (01-82)
    all_sector_codes = {f"{i:02d}" for i in range(1, 83)}
    # Find missing sector codes
    missing_codes = all_sector_codes - existing_sector_codes
    return group_sector_codes_into_ranges(missing_codes)


def get_sector_code_ranges_by_zone(pinnacle_zones: list[PinnacleZone]) -> list[ZoneResponse]:
    # Group sector codes by zone
    zone_to_codes = defaultdict(lambda: {"service": set(), "no_service": set(), "migrant_area": set()})
    for zone in pinnacle_zones:
        zone_to_codes[zone.zone]["service"].add(zone.sector_code)
        if not zone.has_service:
            zone_to_codes[zone.zone]["no_service"].add(zone.sector_code)
        if zone.is_migrant_area:
            zone_to_codes[zone.zone]["migrant_area"].add(zone.sector_code)
            
    # For each zone, group codes into ranges and create a single ZoneResponse
    result = []
    for zone, codes in zone_to_codes.items():
        service_ranges = group_sector_codes_into_ranges(codes["service"])
        no_service_ranges = group_sector_codes_into_ranges(codes["no_service"])
        migrant_area_ranges = group_sector_codes_into_ranges(codes["migrant_area"])
        result.append(
            ZoneResponse(
                zone=zone,
                sector_code_range=service_ranges,
                no_service_code_list=no_service_ranges,
                migrant_area_code_list=migrant_area_ranges,
            )
        )
    placeholder_zone = [zone for zone in DeliveryZone if zone != DeliveryZone.UNKNOWN and zone not in [zone.zone for zone in result]]
    for placeholder in placeholder_zone:
        result.append(ZoneResponse(zone=placeholder, sector_code_range=[], no_service_code_list=[], migrant_area_code_list=[]))

    # Sort by the integer value of the first range's start
    def range_key(zr: ZoneResponse):
        # Define zone priority order
        zone_priority = {
            DeliveryZone.CENTRAL: 0,
            DeliveryZone.NORTH: 1,
            DeliveryZone.EAST: 2,
            DeliveryZone.SOUTH: 3,
            DeliveryZone.WEST: 4,
            DeliveryZone.UNKNOWN: 5,
        }
        return zone_priority[zr.zone]

    result.sort(key=range_key)
    return result


def get_pinnacle_zones(db: Session):
    # Get all existing pinnacle zones
    pinnacle_zones = db.query(PinnacleZone).all()
    existing_sector_codes = {zone.sector_code for zone in pinnacle_zones}

    # Get missing sector codes
    missing_sector_codes = get_missing_sector_codes(existing_sector_codes)
    # Map sector code ranges to their respective zones
    sector_code_ranges_by_zone = get_sector_code_ranges_by_zone(pinnacle_zones)

    return GetPinnacleZonesResponse(
        missing_sector_codes=missing_sector_codes,
        sector_code_ranges_by_zone=sector_code_ranges_by_zone,
    )

class RetrievePinnacleZoneResponse(BaseModel):
    zone: DeliveryZone
    has_service: bool
    is_migrant_area: bool

def _generate_retrieve_pinnacle_zone_response(zone: PinnacleZone | None):
    return RetrievePinnacleZoneResponse(
        zone=zone.zone if zone else DeliveryZone.UNKNOWN,
        has_service=zone.has_service if zone else False,
        is_migrant_area=zone.is_migrant_area if zone else False,
    )

def retrieve_pinnacle_zone_by_sector_codes(sector_codes: list[str], db: Session):
    uniq_sector_codes = list(set(sector_codes))
    records = db.query(PinnacleZone) \
        .filter(PinnacleZone.sector_code.in_(uniq_sector_codes)) \
        .all()
    records_dict = {zone.sector_code: zone for zone in records}

    return {
        sector_code: _generate_retrieve_pinnacle_zone_response(records_dict.get(sector_code)) for sector_code in sector_codes
    }

def retrieve_pinnacle_zone_by_sector_code(sector_code: str, db: Session):
    record = db.query(PinnacleZone) \
        .filter(PinnacleZone.sector_code == sector_code) \
        .first()

    return _generate_retrieve_pinnacle_zone_response(record)

def edit_pinnacle_zone(request: EditPinnacleZoneRequest, db: Session):
    for code in request.sector_code_list + request.sector_code_without_service + request.migrant_area_code_list:
        if not code.isdigit() or len(code) != 2:
            raise HTTPException(status_code=400, detail="Sector code must be a 2-digit number")
    
    pinnacle_zones = (
        db.query(PinnacleZone)
        .filter(
            PinnacleZone.sector_code.in_(
                request.sector_code_list + request.sector_code_without_service + request.migrant_area_code_list
            )
        )
        .all()
    )

    # Step 1 : Find non-exist sector codes and add them to the database
    non_exist_sector_codes = [
        code
        for code in request.sector_code_list
        if code not in [zone.sector_code for zone in pinnacle_zones]
    ]
    non_exist_sector_codes.extend(
        [
            code
            for code in request.sector_code_without_service
            if code not in ([zone.sector_code for zone in pinnacle_zones] + [code for code in request.sector_code_list])
        ]
    )
    non_exist_sector_codes.extend(
        [
            code
            for code in request.migrant_area_code_list
            if code not in ([zone.sector_code for zone in pinnacle_zones] + [code for code in request.sector_code_list] + [code for code in request.sector_code_without_service])
        ]
    )

    for code in non_exist_sector_codes:
        new_zone = PinnacleZone(sector_code=code, zone=request.zone, has_service=True)
        db.add(new_zone)
        pinnacle_zones.append(new_zone)

    # Step 2 : Update the zone object with correct zone
    for zone in pinnacle_zones:
        zone.zone = request.zone

    # Step 3 : Update the has_service attribute for the pinnacle zones
    no_service_pinnacle_zones = [
        zone
        for zone in pinnacle_zones
        if zone.sector_code in request.sector_code_without_service
    ]
    has_service_pinnacle_zones = [
        zone
        for zone in pinnacle_zones
        if zone.sector_code not in request.sector_code_without_service
    ]

    for zone in no_service_pinnacle_zones:
        zone.has_service = False

    for zone in has_service_pinnacle_zones:
        zone.has_service = True
        
    for zone in pinnacle_zones:
        zone.is_migrant_area = zone.sector_code in request.migrant_area_code_list

    # Step 4 : Delete the pinnacle zones that are not in the request
    original_zones = (
        db.query(PinnacleZone).filter(PinnacleZone.zone == request.zone).all()
    )
    zones_to_delete = [
        zone
        for zone in original_zones
        if zone.sector_code
        not in request.sector_code_list + request.sector_code_without_service + request.migrant_area_code_list
    ]
    for zone in zones_to_delete:
        db.delete(zone)

    db.commit()

    return SuccessResp(success=True)
