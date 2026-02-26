from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from models import get_db
from utils.fastapi import SuccessResp
from utils.supabase_auth import SupabaseUser, get_dispatch_or_logistic_or_superadmin
from sqlalchemy.orm import Session
from routers.delivery.typings.delivery import TeleconsultDeliveryResponse, DispatchUpdateTeleconsultDeliveryStatusRequest
from routers.delivery.actions.delivery import dispatch_get_teleconsult_delivery_objects, dispatch_update_teleconsult_delivery_status_action

router = APIRouter(dependencies=[Depends(get_dispatch_or_logistic_or_superadmin)])

@router.get("/", response_model=list[TeleconsultDeliveryResponse])
async def dispatch_read_teleconsult_delivery_routes(db: Session = Depends(get_db)):
    try:
        return dispatch_get_teleconsult_delivery_objects(db=db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/update_delivery_status", response_model=SuccessResp)
async def dispatch_update_teleconsult_delivery_status_route(
    request_json: str = Form(...),
    file: UploadFile | None = None,
    user: SupabaseUser = Depends(get_dispatch_or_logistic_or_superadmin),
    db: Session = Depends(get_db)
):
    """
    request_json must be in format :
    {
        "id": "string",
        "success": boolean,
        "recipient_name": "string"
    }
    """
    try:
        request = DispatchUpdateTeleconsultDeliveryStatusRequest.model_validate_json(request_json)
        return await dispatch_update_teleconsult_delivery_status_action(request, user, db, file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    