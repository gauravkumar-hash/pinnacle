from fastapi import APIRouter, Depends, HTTPException
from models import get_db
from sqlalchemy.orm import Session
from routers.delivery.typings.zone import GetPinnacleZonesResponse, EditPinnacleZoneRequest  
from routers.delivery.actions.zone import get_pinnacle_zones, edit_pinnacle_zone    
from utils.supabase_auth import get_admin_or_superadmin
from utils.fastapi import SuccessResp

router = APIRouter(dependencies=[Depends(get_admin_or_superadmin)])

@router.get("/", response_model=GetPinnacleZonesResponse)
async def get_pinnacle_zones_route(db: Session = Depends(get_db)):
    try:
        return get_pinnacle_zones(db=db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.put("/edit", response_model=SuccessResp)
async def edit_pinnacle_zone_route(request: EditPinnacleZoneRequest, db: Session = Depends(get_db)):
    try:
        return edit_pinnacle_zone(request, db=db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
