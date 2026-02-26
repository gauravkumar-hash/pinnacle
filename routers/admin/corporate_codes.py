from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from models import get_db, SGiMedInventory
from models.payments import CorporateCode
from utils.fastapi import SuccessResp
from utils.supabase_auth import get_superadmin

router = APIRouter(dependencies=[Depends(get_superadmin)])

class CorporateCodeRow(BaseModel):
    id: str
    code: str
    amount: float
    remarks: str | None = None
    skip_prepayment: bool = False
    hide_invoice: bool = False

    # Pydantic Transform code to uppercase
    @field_validator('code')
    def code_to_uppercase(cls, v):
        return v.upper()

class CorporateCodeResp(BaseModel):
    codes: list[CorporateCodeRow]
    supported_rates: list[float]

@router.get('/', response_model=CorporateCodeResp)
def get_corporate_codes(db: Session = Depends(get_db)):
    codes = db.query(CorporateCode).filter(CorporateCode.deleted == False).order_by(CorporateCode.updated_at.desc()).all()

    return CorporateCodeResp(
        codes=[
            CorporateCodeRow(
                id=str(record.id),
                code=record.code,
                amount=0,
                remarks=record.remarks,
                skip_prepayment=record.skip_prepayment,
                hide_invoice=record.hide_invoice
            )
            for record in codes
        ],
        supported_rates=[] # TODO: Add supported rates
    )

@router.post('/', response_model=SuccessResp)
def upsert_corporate_codes(req: CorporateCodeRow, db: Session = Depends(get_db)):
    if not req.code:
        raise HTTPException(status_code=400, detail="Code is required")
    # Check if code is unique
    qry = db.query(CorporateCode.id).filter(CorporateCode.code == req.code)
    if req.id:
        print("req.id", req.id)
        qry = qry.filter(CorporateCode.id != int(req.id))
    record = qry.first()
    if record:
        raise HTTPException(status_code=400, detail="Code already exists")

    record = {
        'code': req.code,
        'remarks': req.remarks,
        'skip_prepayment': req.skip_prepayment,
        'hide_invoice': req.hide_invoice,
        'allow_user_input': True,
        # 'sgimed_consultation_inventory_ids': req.inventory_item_ids
    }
    if req.id:
        code = db.query(CorporateCode).filter(CorporateCode.id == int(req.id)).first()
        if not code:
            raise HTTPException(status_code=404, detail="Corporate code record not found")
        
        code.update_vars(record)
    else:
        code = CorporateCode(**record)
        db.add(code)

    db.commit()
    return SuccessResp(success=True)

@router.delete('/{id}', response_model=SuccessResp)
def delete_corporate_codes(id: int, db: Session = Depends(get_db)):
    record = db.query(CorporateCode).filter(CorporateCode.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Corporate code record not found")

    record.deleted = True
    db.commit()
    return SuccessResp(success=True)


# V2 Schemas for new model structure (without Rate dependency)
class InventoryItemInfo(BaseModel):
    id: str
    code: str
    name: str
    price: Optional[float] = None

class CorporateCodeV2Row(BaseModel):
    id: Optional[str] = None
    code: str
    remarks: Optional[str] = None
    skip_prepayment: bool = False
    hide_invoice: bool = False
    allow_user_input: bool = True
    inventory_items: List[InventoryItemInfo] = []
    priority_index: int = 100

    # Pydantic Transform code to uppercase
    @field_validator('code')
    def code_to_uppercase(cls, v):
        return v.upper()


# V2 Endpoints using new model structure
@router.get('/v2', response_model=List[CorporateCodeV2Row])
def get_corporate_codes_v2(db: Session = Depends(get_db)):
    codes = db.query(CorporateCode).filter(CorporateCode.deleted == False).order_by(CorporateCode.priority_index.asc(), CorporateCode.updated_at.desc()).all()
    
    # Get all unique inventory IDs from corporate codes
    all_inventory_ids = set()
    for code in codes:
        all_inventory_ids.update(code.sgimed_consultation_inventory_ids)
    
    # Fetch inventory items with their prices
    inventory_items = {}
    if all_inventory_ids:
        inventory_records = db.query(SGiMedInventory).filter(
            SGiMedInventory.id.in_(all_inventory_ids)
        ).all()
        
        inventory_items: dict[str, InventoryItemInfo] = {
            item.id: InventoryItemInfo(
                id=item.id,
                code=item.code,
                name=item.name,
                price=item.price
            )
            for item in inventory_records
        }

    return [
            CorporateCodeV2Row(
                id=str(record.id),
                code=record.code,
                remarks=record.remarks,
                skip_prepayment=record.skip_prepayment,
                hide_invoice=record.hide_invoice,
                allow_user_input=record.allow_user_input,
                inventory_items=[
                    inventory_items[ids]
                    for ids in record.sgimed_consultation_inventory_ids
                    if ids in inventory_items
                ],
                priority_index=record.priority_index
            )
            for record in codes
        ]

@router.get('/v2/inventory/search', response_model=List[InventoryItemInfo])
def search_inventory(
    search: str = Query(..., description="Search term for inventory code or name"),
    db: Session = Depends(get_db)
):
    """Search for SGiMed inventory items by code or name"""
    if len(search) < 2:
        raise HTTPException(status_code=400, detail="Search term must be at least 2 characters")
    
    # Search for inventory items
    inventory_items = db.query(SGiMedInventory).filter(
        or_(
            SGiMedInventory.code.ilike(f"%{search}%"),
            SGiMedInventory.name.ilike(f"%{search}%")
        ),
        SGiMedInventory.type == "Service"  # Only show service items for corporate codes
    ).limit(20).all()
    
    return [
        InventoryItemInfo(
            id=item.id,
            code=item.code,
            name=item.name,
            price=item.price
        )
        for item in inventory_items
    ]

@router.post('/v2', response_model=SuccessResp)
def upsert_corporate_codes_v2(req: CorporateCodeV2Row, db: Session = Depends(get_db)):
    if not req.code:
        raise HTTPException(status_code=400, detail="Code is required")
    
    # Check if code is unique
    qry = db.query(CorporateCode.id).filter(CorporateCode.code == req.code)
    if req.id:
        qry = qry.filter(CorporateCode.id != int(req.id))
    record = qry.first()
    if record:
        raise HTTPException(status_code=400, detail="Code already exists")
    
    inventory_ids = [item.id for item in req.inventory_items]
    # Validate SGiMed inventory codes if provided
    for inventory_id in inventory_ids:
        inventory_item = db.query(SGiMedInventory).filter(
            SGiMedInventory.id == inventory_id
        ).first()
        if not inventory_item:
            raise HTTPException(status_code=404, detail=f"Inventory item '{inventory_id}' not found")
    
    record_data = {
        'code': req.code,
        'remarks': req.remarks,
        'skip_prepayment': req.skip_prepayment,
        'hide_invoice': req.hide_invoice,
        'allow_user_input': req.allow_user_input,
        'sgimed_consultation_inventory_ids': inventory_ids,
        'priority_index': req.priority_index
    }
    
    if req.id:
        code = db.query(CorporateCode).filter(CorporateCode.id == int(req.id)).first()
        if not code:
            raise HTTPException(status_code=404, detail="Corporate code record not found")
        
        code.update_vars(record_data)
    else:
        code = CorporateCode(**record_data)
        db.add(code)

    db.commit()
    return SuccessResp(success=True)

@router.delete('/v2/{id}', response_model=SuccessResp)
def delete_corporate_codes_v2(id: int, db: Session = Depends(get_db)):
    record = db.query(CorporateCode).filter(CorporateCode.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Corporate code record not found")

    record.deleted = True
    db.commit()
    return SuccessResp(success=True)
