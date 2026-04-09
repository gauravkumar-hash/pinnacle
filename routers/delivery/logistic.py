from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from models import get_db
from utils.fastapi import SuccessResp
from utils.supabase_auth import SupabaseUser, get_logistic_or_superadmin
from sqlalchemy.orm import Session
from routers.delivery.typings.delivery import UpdateTeleconsultDeliveryStatusRequest, \
    UpdateTeleconsultDeliveryRequest, LogisticsFetchingResponse, UpdateBulkTeleconsultDeliveryStatusRequest
from routers.delivery.actions.delivery import logistics_get_teleconsult_delivery_objects, \
    update_teleconsult_delivery_status, update_teleconsult_delivery, \
    logistic_download_delivery_note_action, logistic_download_delivery_note_by_date_action, \
    logistic_export_delivery_sheet_action, logistic_export_end_day_report_action, logistics_get_drivers_action, \
    update_bulk_teleconsult_delivery_status

router = APIRouter(dependencies=[Depends(get_logistic_or_superadmin)])

# Delivery Endponts
@router.get("/", response_model=LogisticsFetchingResponse)
async def logistics_read_teleconsult_delivery_routes(date: Optional[date] = None, db: Session = Depends(get_db)):
    try:
        deliveries = logistics_get_teleconsult_delivery_objects(db=db, date=date)
        drivers = logistics_get_drivers_action(db=db)
        return LogisticsFetchingResponse(deliveries=deliveries, drivers=drivers)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update_bulk_delivery_status", response_model=SuccessResp)
async def update_bulk_teleconsult_delivery_status_route(
    request: UpdateBulkTeleconsultDeliveryStatusRequest,
    db: Session = Depends(get_db)
):
    try:
        return update_bulk_teleconsult_delivery_status(request, db=db)   
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update_delivery_status", response_model=SuccessResp)
async def update_teleconsult_delivery_status_route(
    request: UpdateTeleconsultDeliveryStatusRequest,
    user: SupabaseUser = Depends(get_logistic_or_superadmin),
    db: Session = Depends(get_db)
):
    try:
        return update_teleconsult_delivery_status(request, user, db=db)   
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/update_delivery", response_model=SuccessResp)
async def update_teleconsult_delivery_route(request: UpdateTeleconsultDeliveryRequest, db: Session = Depends(get_db)):
    try:
        return update_teleconsult_delivery(request, db=db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download_delivery_note")
async def download_delivery_note_route(delivery_note_key: str):
    try:
        return logistic_download_delivery_note_action(delivery_note_key)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/download_delivery_note_zip")
async def download_delivery_note_zip_route(date: date, db: Session = Depends(get_db)):
    try:
        return logistic_download_delivery_note_by_date_action(date, db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/export_delivery_sheet")
async def export_delivery_sheet_route(date: Optional[date] = None, is_migrant: bool = False,  db: Session = Depends(get_db)):
    try:
        return logistic_export_delivery_sheet_action(db=db, date=date, is_migrant=is_migrant)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export_end_day_report")
async def export_end_day_report_route(date: date, db: Session = Depends(get_db)):
    try:
        return logistic_export_end_day_report_action(date, db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
