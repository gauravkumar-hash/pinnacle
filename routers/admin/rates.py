from datetime import time
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from models import get_db
from models.payments import DynamicPricing
from models.sgimed import SGiMedInventory
from utils.fastapi import SuccessResp
from utils.supabase_auth import get_superadmin

router = APIRouter(dependencies=[Depends(get_superadmin)])

supported_days = ['MON-FRI', 'SAT', 'SUN', 'PH']

class InventoryItemInfo(BaseModel):
    id: str
    code: str
    name: str
    price: float | None = None

class CorporateCodeOverrideInfo(BaseModel):
    """Full details for a corporate code override including inventory item info."""
    corporate_code_id: str
    inventory_item_ids: list[str] = []  # For saving - just the IDs
    inventory_items: list[InventoryItemInfo] = []  # For display - full item info

class DynamicPricingRow(BaseModel):
    id: str | None = None
    date: str
    start_time: time
    end_time: time
    amount: float
    inventory_item_ids: list[str] = [] # Used for updating
    inventory_items: list[InventoryItemInfo] = []
    corporate_code_overrides: dict[str, list[str]] = {} # For saving: { "corporate_code_id": ["sgimed_inventory_id"] }
    corporate_code_override_details: list[CorporateCodeOverrideInfo] = []  # For display: full details

class DynamicRateResp(BaseModel):
    errors: list[str]
    rates: list[DynamicPricingRow]
    supported_days: list[str]
    supported_rates: list[float]

@router.get('/', response_model=DynamicRateResp)
def get_dynamic_rates(db: Session = Depends(get_db)):
    # Convert 0700 to time(7, 0)
    def convert_time(timings, index):
        time_str = timings.split('-')[index]
        hour = int(time_str[:2])
        hour = 0 if hour == 24 else hour
        minute = int(time_str[2:])

        if time_str == '2400':
            return time(23, 59)
        return time(hour, minute)

    rates = db.query(DynamicPricing).all()
    
    rates.sort(key=lambda x: (supported_days.index(x.date), x.timing))
    
    # Build response with full inventory item details
    response_rates = []
    for record in rates:
        inventory_items = []
        if record.sgimed_consultation_inventory_ids:
            # Fetch inventory items from database
            inventory_records = db.query(SGiMedInventory).filter(
                SGiMedInventory.id.in_(record.sgimed_consultation_inventory_ids)
            ).all()
            
            inventory_items = [
                InventoryItemInfo(
                    id=item.id,
                    code=item.code,
                    name=item.name,
                    price=item.price
                )
                for item in inventory_records
            ]
        
        # Build corporate code override details with full inventory item info
        corporate_code_override_details = []
        if record.corporate_codes:
            # Collect all inventory IDs from all overrides
            all_override_inventory_ids = set()
            for inventory_ids in record.corporate_codes.values():
                all_override_inventory_ids.update(inventory_ids)

            # Fetch all inventory items in one query
            override_inventory_records = {}
            if all_override_inventory_ids:
                override_items = db.query(SGiMedInventory).filter(
                    SGiMedInventory.id.in_(all_override_inventory_ids)
                ).all()
                override_inventory_records = {item.id: item for item in override_items}

            # Build the override details with full item info
            for corp_code_id, inv_ids in record.corporate_codes.items():
                override_items = [
                    InventoryItemInfo(
                        id=override_inventory_records[inv_id].id,
                        code=override_inventory_records[inv_id].code,
                        name=override_inventory_records[inv_id].name,
                        price=override_inventory_records[inv_id].price
                    )
                    for inv_id in inv_ids
                    if inv_id in override_inventory_records
                ]
                corporate_code_override_details.append(CorporateCodeOverrideInfo(
                    corporate_code_id=corp_code_id,
                    inventory_item_ids=inv_ids,
                    inventory_items=override_items
                ))

        response_rates.append(DynamicPricingRow(
            id=str(record.id),
            date=record.date,
            start_time=convert_time(record.timing, 0),
            end_time=convert_time(record.timing, 1),
            amount=0.0, # TODO: Combine with inventory items
            inventory_item_ids=record.sgimed_consultation_inventory_ids or [],
            inventory_items=inventory_items,
            corporate_code_overrides=record.corporate_codes or {},
            corporate_code_override_details=corporate_code_override_details
        ))
    
    rates = response_rates
    
    # Checking errors to ensure all the timings are defined correctly
    errors = []
    # Missing Days Errors
    missing_days = set(supported_days) - set([rate.date for rate in rates])
    for day in missing_days:
        errors.append(f"{day} is not defined")
    
    
    # Validate time continuity within each day
    if rates:  # Only process if there are rates
        curr_day = supported_days[0]
        curr_time = time(0, 0)
        
        for rate in rates:
            # Move to the correct day if we're not there yet
            while rate.date != curr_day:
                if curr_time != time(0, 0):
                    errors.append(f"{curr_day} last record end time is not 23:59")

                # Move to next day in supported_days
                try:
                    curr_day_index = supported_days.index(curr_day)
                    if curr_day_index + 1 < len(supported_days):
                        curr_day = supported_days[curr_day_index + 1]
                        curr_time = time(0, 0)
                    else:
                        # We've processed all supported days, break
                        break
                except ValueError:
                    # curr_day is not in supported_days, this shouldn't happen
                    break
            
            # Skip processing if we've moved beyond our supported days
            if rate.date not in supported_days:
                continue
                
            # Check if start time matches expected time
            if rate.start_time != curr_time:
                errors.append(f"{curr_day} {rate.start_time.strftime('%H:%M')} start time is not {curr_time.strftime('%H:%M')}")

            # Update current time and possibly day
            if rate.end_time == time(23, 59):
                # End of day - move to next day
                try:
                    curr_day_index = supported_days.index(curr_day)
                    if curr_day_index + 1 < len(supported_days):
                        curr_day = supported_days[curr_day_index + 1]
                        curr_time = time(0, 0)
                    else:
                        # Last day processed
                        curr_time = time(0, 0)
                except ValueError:
                    curr_time = time(0, 0)
            else:
                curr_time = rate.end_time

        # Check if the last day ends properly (only if we have a current day that's in supported days)
        if curr_day in supported_days and curr_time != time(0, 0):
            errors.append(f"{curr_day} last record end time is not 23:59")

    return DynamicRateResp(
        errors=errors,
        rates=rates,
        supported_days=supported_days,
        supported_rates=[] # TODO: Add supported rates
    )

@router.post('/', response_model=SuccessResp)
def upsert_dynamic_rates(req: DynamicPricingRow, db: Session = Depends(get_db)):
    if req.date not in supported_days:
        raise HTTPException(status_code=400, detail="Invalid date")
    if req.end_time <= req.start_time:
        raise HTTPException(status_code=400, detail="End time cannot be before start time")

    start_time = req.start_time.strftime('%H%M')
    end_time = req.end_time.strftime('%H%M')
    if end_time == '2359':
        end_time = '2400'
        
    timing = f"{start_time}-{end_time}"
    
    record = {
        'date': req.date,
        'timing': timing,
        'sgimed_consultation_inventory_ids': req.inventory_item_ids,
        'corporate_codes': req.corporate_code_overrides
    }

    if req.id:
        pricing = db.query(DynamicPricing).filter(DynamicPricing.id == int(req.id)).first()
        if not pricing:
            raise HTTPException(status_code=404, detail="Dynamic pricing record not found")
        
        pricing.update_vars(record)
    else:
        pricing = DynamicPricing(**record)
        db.add(pricing)

    db.commit()
    return SuccessResp(success=True)

@router.delete('/{id}', response_model=SuccessResp)
def delete_dynamic_rates(id: int, db: Session = Depends(get_db)):
    rows = db.query(DynamicPricing).filter(DynamicPricing.id == id).delete()
    db.commit()
    if not rows:
        raise HTTPException(status_code=404, detail="Dynamic pricing record not found")
    return SuccessResp(success=True)
