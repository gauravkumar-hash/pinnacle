import asyncio
from datetime import date
from enum import Enum
import json
import logging
from typing import Callable, Optional
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from config import REDIS_HOST, REDIS_PORT ,REDIS_PASSWORD
from models.model_enums import VisitType
from routers.admin.teleconsult import TeleconsultAdminResp
from broadcaster import Broadcast

from routers.admin.walkin import WalkinAdminResp
from utils.sg_datetime import sg
BROADCASTER_URL = f'rediss://default:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}'
BROADCASTER_CHANNEL = 'realtime'

class WSEvent(Enum):
    PATIENT_ACTIVITY_UPDATE = "patient_activity_update" # Require id
    PATIENT_ACTIVITY_UPDATE_ALL = "patient_activity_update_all" # Update all patients for walkin queue number update
    DOCTOR_TELECONSULT_UPDATE_ALL = "doctor_teleconsult_update_all" # Update all doctors for teleconsult queue number update
    ADMIN_TELECONSULT_UPDATE_ALL = "admin_teleconsult_update_all" # Update all admins for teleconsult queue number update
    ADMIN_WALKIN_UPDATE_ALL = "admin_walkin_update_all" # Update all admins for walkin queue number update

class WSMessage(BaseModel):
    id: Optional[str] = None
    event: WSEvent
    data: dict = {}

class ConnectionManager:
    broadcaster = Broadcast(BROADCASTER_URL)
    
    def __init__(self):
        self.activity_connections: dict[str, WebSocket] = {}
        self.doctor_connections: dict[WebSocket, dict] = {}
        self.admin_connections: dict[WebSocket, dict] = {}
        
    async def listen(self):
        subscribe_n_listen_task = asyncio.create_task(self.listen_to_channel(room_id=BROADCASTER_CHANNEL))
        wait_for_subscribe_task = asyncio.create_task(asyncio.sleep(1))  # 1 Second delay
        await asyncio.wait([subscribe_n_listen_task, wait_for_subscribe_task], return_when=asyncio.FIRST_COMPLETED)

    async def send_patient_update(self, id: str):
        if id not in self.activity_connections:
            return

        try:
            await self.activity_connections[id].send_text("update")
        except (WebSocketDisconnect, RuntimeError):
            self.disconnect_patient_activity(id)

    async def send_doctor_update(self, ws: WebSocket, data: dict):
        try:
            await ws.send_json(data)
        except (WebSocketDisconnect, RuntimeError):
            self.disconnect_doctor(ws)

    async def send_update(self, ws: WebSocket, data: dict, disconnect_func: Callable):
        try:
            await ws.send_json(data)
        except (WebSocketDisconnect, RuntimeError):
            disconnect_func(ws)

    async def push_to_channel(self, message: WSMessage):
        logging.info(f"Publish WS event: {message}")
        await self.broadcaster.publish(channel=BROADCASTER_CHANNEL, message=message.model_dump_json())

    async def listen_to_channel(self, room_id: str):
        async with self.broadcaster.subscribe(channel=room_id) as subscriber:
            async for event in subscriber: # type: ignore
                logging.info(f"Received WS event: {event.message}")
                msg = WSMessage.model_validate_json(event.message)
                # continue
                # Handle Patient Activity Update
                if msg.id and msg.event == WSEvent.PATIENT_ACTIVITY_UPDATE:
                    await self.send_patient_update(msg.id)
                elif msg.event == WSEvent.PATIENT_ACTIVITY_UPDATE_ALL:
                    for id in list(self.activity_connections.keys()):
                        await self.send_patient_update(id)
                elif msg.event == WSEvent.DOCTOR_TELECONSULT_UPDATE_ALL:
                    for ws in list(self.doctor_connections.keys()):
                        await self.send_doctor_update(ws, msg.data)
                elif msg.event == WSEvent.ADMIN_TELECONSULT_UPDATE_ALL:
                    resp = TeleconsultAdminResp.model_validate(msg.data)
                    for ws, metadata in list(self.admin_connections.items()):
                        if metadata["type"] != VisitType.TELECONSULT:
                            continue
                        data = {} if sg(resp.checkin_time).date() != metadata["date"] else json.loads(resp.model_dump_json())
                        await self.send_update(ws, data, self.disconnect_admin)
                elif msg.event == WSEvent.ADMIN_WALKIN_UPDATE_ALL:
                    resp = WalkinAdminResp.model_validate(msg.data)
                    for ws, metadata in list(self.admin_connections.items()):
                        if metadata["type"] != VisitType.WALKIN:
                            continue
                        data = {} if sg(resp.created_at).date() != metadata["date"] else json.loads(resp.model_dump_json())
                        await self.send_update(ws, data, self.disconnect_admin)
                else:
                    logging.error(f"Unknown event: {event.message}")

    async def connect_patient_activity(self, id: str, ws: WebSocket):
        await ws.accept()
        self.activity_connections[id] = ws
    
    def disconnect_patient_activity(self, id: str):
        try:
            del self.activity_connections[id]
        except KeyError:
            logging.warning(f"WS Patient Connection not found. User ID: {id}")
    
    async def connect_doctor(self, ws: WebSocket, id: str):
        await ws.accept()
        self.doctor_connections[ws] = { "id": id }
    
    def disconnect_doctor(self, ws: WebSocket):
        try:
            del self.doctor_connections[ws]
        except Exception:
            logging.warning("WS Doctor Connection not found.")    
    
    async def connect_admin(self, ws: WebSocket, id: str, date: date, type: VisitType):
        await ws.accept()
        self.admin_connections[ws] = {
            "id": id,
            "date": date,
            "type": type
        }

    def disconnect_admin(self, ws: WebSocket):
        try:
            del self.admin_connections[ws]
        except Exception:
            logging.warning("WS Admin Connection not found.")

ws_manager = ConnectionManager()
