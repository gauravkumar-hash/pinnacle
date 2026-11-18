import asyncio
import logging
import time
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
import jwt
from stripe._error import SignatureVerificationError

from config import STRIPE_WEBHOOK_SECRET, SGIMED_WEBHOOK_PUBLIC_KEY, SUPABASE_WEBHOOK_API_KEY, stripe
from models import Payment, PaymentMethod, get_db, PaymentStatus
from models.payments import PaymentType
from routers.admin.actions.teleconsult import admin_supabase_webhook_processing
from routers.admin.actions.walkins import admin_supabase_walkin_processing, webhook_send_notifications
from routers.doctor.actions.webhook import doctor_supabase_webhook_processing
from routers.patient.actions.walkin import pending_walkin_queue_update, walkin_invoice_billed_webhook, walkin_queue_number_update, walkin_queue_update
from routers.patient.actions.appointment import sgimed_appointment_deleted_webhook, sgimed_appointment_updated_webhook, sgimed_appointment_cancelled_webhook
from utils.integrations.sgimed import ClientException, fetch_invoice_details
from .actions.teleconsult_flow_backend import postpayment_success_webhook, prepayment_success_webhook, teleconsult_invoice_billed_webhook
from sqlalchemy.orm import Session
from routers.realtime import ws_manager, WSMessage, WSEvent
from services.appointment import appointment_success_webhook

router = APIRouter()

# NOTE: 2C2P Webhook is in /routers/payments/pgw2c2p/router.py @router.post("/webhook")

def stripe_charge_succeeded(db: Session, event: dict):
    checkout_session = event["data"]["object"]
    payment_intent_id = checkout_session["payment_intent"]

    if checkout_session["payment_method_details"]["type"] == "card":
        brand = checkout_session["payment_method_details"]["card"]["brand"]
        last4 = checkout_session["payment_method_details"]["card"]["last4"]

        payments = db.query(Payment).where(
                Payment.payment_id == payment_intent_id, 
                Payment.payment_method == PaymentMethod.CARD_STRIPE
            ).all()
        if not payments:
            logging.error(f"Stripe Webhook Record not found (Card). Payment ID: {payment_intent_id}")
            return { "success": False }
        
        for payment in payments:
            payment.status = PaymentStatus.PAYMENT_SUCCESS
            payment.remarks = { "brand": brand, "last4": last4 }
        db.commit()
        
        if payments[0].payment_type == PaymentType.PREPAYMENT:
            prepayment_success_webhook(db, payments)
        elif payments[0].payment_type == PaymentType.POSTPAYMENT:
            postpayment_success_webhook(db, payments)
        elif payments[0].payment_type == PaymentType.APPOINTMENT:
            appointment_success_webhook(db, payments)
    # Ignore PayNow as there should be checkout.session.completed event
    elif checkout_session["payment_method_details"]["type"] != 'paynow':
        logging.info("Unhandled Payment Type on charge.succeeded: {}".format(checkout_session['payment_method_details']['type']))

def stripe_checkout_session_completed(db: Session, event: dict):
    checkout_session = event["data"]["object"]        
    session_id = checkout_session["id"],
    payment_intent_id = checkout_session["payment_intent"]

    is_paid = checkout_session["payment_status"] == "paid"
    if is_paid:
        # Check if payment succeeded
        payments = db.query(Payment).where(
                Payment.payment_id.in_((session_id, payment_intent_id)),
                Payment.payment_method == PaymentMethod.PAYNOW_STRIPE
            ).all()
        if not payments:
            logging.error(f"Stripe Webhook Record not found (PayNow). Session ID: {session_id}, Payment ID: {payment_intent_id}")
            return { "success": False }
        
        for payment in payments:
            payment.payment_id = payment_intent_id
            payment.status = PaymentStatus.PAYMENT_SUCCESS
        db.commit()
        
        if payments[0].payment_type == PaymentType.PREPAYMENT:
            prepayment_success_webhook(db, payments)
        elif payments[0].payment_type == PaymentType.POSTPAYMENT:
            postpayment_success_webhook(db, payments)
        elif payments[0].payment_type == PaymentType.APPOINTMENT:
            appointment_success_webhook(db, payments)

@router.post('/stripe')
async def webhook(request: Request, db: Session = Depends(get_db)):
    event = None
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError as e:
        # Invalid payload
        raise e
    except SignatureVerificationError as e:
        # Invalid signature
        raise e

    # Card
    if event['type'] == 'charge.succeeded':    
        stripe_charge_succeeded(db, event)
    # PayNow
    elif event['type'] == 'checkout.session.completed':
        stripe_checkout_session_completed(db, event)
    else:
        # Handle the event
        print('Unhandled event type {}'.format(event['type']))
        print(event)

    return {
        "success": True
    }

# Authorize Supabase Webhook using "Authorization: Bearer <API_KEY>" header
auth_scheme = HTTPBearer()
def validate_supabase_webhook_token(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if token.credentials != SUPABASE_WEBHOOK_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")

@router.post("/supabase/teleconsults")
async def supabase_teleconsults_webhook(payload: dict, webhook = Depends(validate_supabase_webhook_token)):
    # print(f"Payload Teleconsults Received: {payload}. Ignoring")
    # return {"success": True}
    print(f"Payload Received: {payload}")
    type = payload["type"]
    record = payload["record"]
    # Patient Websocket Updates
    await ws_manager.push_to_channel(WSMessage(
            id=record['created_by'] if record.get('created_by', None) else record["account_id"], 
            event=WSEvent.PATIENT_ACTIVITY_UPDATE
        ))
    # Doctor Websocket Updates
    message = doctor_supabase_webhook_processing(payload)
    if message:
        await ws_manager.push_to_channel(WSMessage(event=WSEvent.DOCTOR_TELECONSULT_UPDATE_ALL, data=message))
    # Admin 
    await admin_supabase_webhook_processing(payload)
    return {"message": "Received"}

@router.post("/supabase/walkins")
async def supabase_walkins_webhook(payload: dict, webhook = Depends(validate_supabase_webhook_token)):
    # print(f"Payload Walkin Received: {payload}. Ignoring")
    # return {"success": True}
    '''
    Handles the changes 
    '''
    print(f"Payload Received: {payload}")
    type = payload["type"]
    record = payload["record"]

    # Update patient app on any changes to the record
    await ws_manager.push_to_channel(WSMessage(
            id=record['created_by'] if record.get('created_by', None) else record["account_id"],
            event=WSEvent.PATIENT_ACTIVITY_UPDATE
        ))
    # Send notifications to all doctors with notifications on that a new patient has joined the queue
    if type == 'INSERT':
        webhook_send_notifications(record["branch_id"], record['index'])
    # Admin 
    await admin_supabase_walkin_processing(payload)
    return {"message": "Received"}


class SGiMedWebhookRequest(BaseModel):
    token: str

async def validate_sgimed_token(params: SGiMedWebhookRequest):
    payload = jwt.decode(params.token, SGIMED_WEBHOOK_PUBLIC_KEY, algorithms=["ES256"])
    return payload
    # except jwt.ExpiredSignatureError:
    #     raise HTTPException(status_code=403, detail="Token has expired")
    # except Exception:
    #     raise HTTPException(status_code=403, detail="Could not validate token")

async def _handle_sgimed_event(event: str, ref: str):
    '''
    Runs one SGiMed event. Each branch reads from SGiMed before it writes anything (or is idempotent),
    so a failed SGiMed call leaves nothing half-done and the event can be run again.
    Returns the invoice details for invoice.finalized, None otherwise.
    '''
    if event == 'invoice.finalized':
        return fetch_invoice_details(ref)
    elif event == 'visit.queue_called':
        await walkin_queue_update(ref)
    elif event == 'visit.queue_number_changed':
        await walkin_queue_number_update(ref)
    elif event == 'pending_queue.updated':
        pending_walkin_queue_update(ref, accepted=True)
    elif event == 'pending_queue.deleted':
        pending_walkin_queue_update(ref, accepted=False)
    elif event == 'appointment.updated':
        sgimed_appointment_updated_webhook(ref)
    elif event == 'appointment.cancelled':
        sgimed_appointment_cancelled_webhook(ref)
    elif event == 'appointment.deleted':
        sgimed_appointment_deleted_webhook(ref)
    else:
        logging.info(f"Unhandled SGiMed event: {event} {ref}")

async def process_sgimed_event(event: str, ref: str):
    '''
    Runs after the webhook has already answered 200. Before, an SGiMed 429 inside the request made us answer 500,
    SGiMed re-sent the webhook every few seconds, and every re-send used more of the shared 140/min limit.
    That limit is a fixed window that resets at :00, so on a 429/5xx we wait for the next window and try again.
    '''
    # ponytail: in-memory retry, a pending retry is lost if the server restarts during the wait
    for attempt in range(1, 4):
        try:
            invoice_details = await _handle_sgimed_event(event, ref)
            break
        except ClientException as e:
            if attempt == 3:
                logging.error(f"SGiMed Webhook FAILED after {attempt} attempts: {event} {ref}. Error: {e}")
                return
            wait = 61 - time.time() % 60
            logging.warning(f"SGiMed Webhook attempt {attempt} failed, retrying in {wait:.0f}s: {event} {ref}. Error: {e}")
            await asyncio.sleep(wait)
        except Exception as e:
            logging.exception(f"SGiMed Webhook FAILED (not retried): {event} {ref}. Error: {e}")
            return
    if attempt > 1:
        logging.info(f"SGiMed Webhook recovered on attempt {attempt}: {event} {ref}")

    if invoice_details:
        # Outside the retry on purpose: these post payments to SGiMed, so a second run would post them twice
        details = invoice_details.model_dump()
        await run_in_threadpool(teleconsult_invoice_billed_webhook, **details)
        await run_in_threadpool(walkin_invoice_billed_webhook, **details)

@router.post("/sgimed")
async def sgimed_webhook(background_tasks: BackgroundTasks, payload: dict = Depends(validate_sgimed_token)):
    '''
    Webhook call from SGiMed when there are changes to the queue. Answers 200 straight away and does the work
    in the background, so a failed SGiMed call can't make SGiMed re-send the webhook in a loop.
    '''
    print(f"SGiMed Webhook: {payload}")
    # {'event': 'invoice.finalized', 'object_reference': '17171306466674117'}}
    background_tasks.add_task(process_sgimed_event, payload['data']['event'], payload['data']['object_reference'])
    return {"success": True}
