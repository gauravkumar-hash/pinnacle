import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from models import SessionLocal
from models.pinnacle import PinnacleAccount
from routers.realtime import ws_manager

router = APIRouter()


@router.websocket("/teleconsult/ws")
async def teleconsult_websocket(id: str, websocket: WebSocket):
    print("Activity Websocket Connected. User UID: ", id)
    with SessionLocal() as db:
        user = db.query(PinnacleAccount).filter(PinnacleAccount.supabase_uid == id).first()
        if not user:
            raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "Invalid Request")
        
    await ws_manager.connect_doctor(websocket, id)

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), 1)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect_doctor(websocket)
