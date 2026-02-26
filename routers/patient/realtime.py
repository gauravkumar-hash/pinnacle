import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status
from models import SessionLocal
from models.payments import Payment, PaymentStatus
from routers.patient.utils import validate_user
from routers.realtime import ws_manager

router = APIRouter()

@router.websocket("/teleconsult/payment/ws")
async def prepayment_websocket(payment_id: str, websocket: WebSocket):
    await websocket.accept()

    try:
        prev_sent_status = None
        while True:
            # Open a new session to check the payment status and close after. Required if not websockets hold the database connection and overflows it.
            with SessionLocal() as db:
                payment = db.query(Payment).filter(Payment.payment_id == payment_id).first()
                if not payment:
                    raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "Payment not found")
                
                if payment.status != prev_sent_status:
                    logging.info(f"Payment Status Changed Payment ID: {payment_id}, Status: {payment.status}")
                    success = payment.status == PaymentStatus.PAYMENT_SUCCESS
                    await websocket.send_json({
                        "id": str(payment.teleconsults[0].id) if success else None,
                        "status": payment.status.value
                    })
                    prev_sent_status = payment.status

            # Sleep 2 seconds before checking again
            await asyncio.sleep(2)
    except (WebSocketDisconnect, RuntimeError):
        pass

@router.websocket("/activity/ws")
async def activity_websocket(id: str, websocket: WebSocket):
    with SessionLocal() as db:
        try:
            user = validate_user(db, id)
        except Exception:
            raise WebSocketException(status.WS_1008_POLICY_VIOLATION, "Invalid Request")

    await ws_manager.connect_patient_activity(str(user.id), websocket)

    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), 1)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect_patient_activity(str(user.id))
    except RuntimeError:
        logging.warning(f'RuntimeError: Patient WS State {websocket.application_state}')