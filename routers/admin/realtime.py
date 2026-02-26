import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status

from models import SessionLocal
from models.model_enums import VisitType
from models.pinnacle import PinnacleAccount
from datetime import date
from routers.realtime import ws_manager

router = APIRouter()



@router.websocket("/teleconsult/ws")
async def teleconsult_websocket(id: str, date: date, websocket: WebSocket):
    with SessionLocal() as db:
        user = db.query(PinnacleAccount).filter(PinnacleAccount.supabase_uid == id).first()
        if not user:
            raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "Invalid Request")
        
    await ws_manager.connect_admin(websocket, id, date, VisitType.TELECONSULT)

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), 1)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect_admin(websocket)

@router.websocket("/walkin/ws")
async def walkin_websocket(id: str, date: date, websocket: WebSocket):
    with SessionLocal() as db:
        user = db.query(PinnacleAccount).filter(PinnacleAccount.supabase_uid == id).first()
        if not user:
            raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "Invalid Request")
        
    await ws_manager.connect_admin(websocket, id, date, VisitType.WALKIN)

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), 1)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect_admin(websocket)
