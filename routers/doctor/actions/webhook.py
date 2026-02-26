from datetime import datetime
import json
import logging
from typing import Optional
from pydantic import BaseModel
from models import SessionLocal
from models.model_enums import PatientType, SGiMedICType, TeleconsultStatus
from models.pinnacle import PinnacleAccount
from models.teleconsult import Teleconsult
from routers.patient.actions.teleconsult_utils import get_grouped_teleconsults
from utils.notifications import send_doctor_notification
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_random
from utils.system_config import is_test_user

class UserResponse(BaseModel):
    name: str
    ic_type: SGiMedICType
    nric: str

class TeleconsultResponse(BaseModel):
    id: str
    patient_type: PatientType
    status: TeleconsultStatus
    doctor_id: Optional[str] = None
    additional_status: Optional[TeleconsultStatus] = None 
    queue_number: Optional[str] = None
    checkin_time: datetime 
    teleconsult_start_time: Optional[datetime] = None
    branch_name: str
    user: UserResponse

def send_new_teleconsult_notification(db: Session, teleconsult: Teleconsult):
    # If the teleconsult is a group and index is not the first record, no need to send as it will send repeated notifications
    if teleconsult.group_id and teleconsult.index != 0:
        return

    if is_test_user(db, teleconsult.account):
        logging.info(f"Teleconsult (Test User) skip notification. ID: {teleconsult.account.id}, Name: {teleconsult.account.name}")
        return

    accounts = db.query(PinnacleAccount).filter(PinnacleAccount.enable_notifications == True, PinnacleAccount.deleted == False).all()
    for account in accounts:
        send_doctor_notification(account, f"New Teleconsult ({teleconsult.branch.name})", "A new teleconsult patient has joined the queue")

@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_random(min=1, max=2))
def ensure_queue_numbers(db: Session, teleconsults: list[Teleconsult]):
    for t in teleconsults:
        if not t.queue_number:
            db.refresh(t)
            if not t.queue_number:
                raise Exception(f"Queue number not found for teleconsult {t.id}")

# This is called from the routers/webhook
def doctor_supabase_webhook_processing(payload: dict):
    # Handle the payload received from Supabase realtime changes
    # print(payload)
    type = payload["type"]
    record = payload["record"]
    if record["status"] == 'PREPAYMENT':
        print("Webhook: Ignoring PREPAYMENT status update")
        return None

    old_record = payload["old_record"]
    id = None
    output = None
    # if type == "DELETE":
    #     id = old_record["id"]
    #     output = id

    if type in ["INSERT", "UPDATE"]:
        id = record["id"]
        with SessionLocal() as db:
            record = db.query(Teleconsult).filter(Teleconsult.id == id).first()
            if not record:
                logging.error(f"Teleconsult record not found. ID: {id}")
                return None
            if record.group_id and record.index != 0:
                logging.info(f"Teleconsult is a group and index is not 0. ID: {id}")
                return None

            teleconsults = get_grouped_teleconsults(db, record)
            # This is to ensure all queue numbers are populated before sending out to doctor websockets
            try:
                ensure_queue_numbers(db, teleconsults)
            except Exception as e:
                logging.error(e)
            teleconsult = teleconsults[0]

            # This method json.loads(...model_dump_json()) converts enums into its string representation
            output = json.loads(TeleconsultResponse(
                id=str(teleconsult.id),
                patient_type=teleconsult.patient_type,
                status=teleconsult.status,
                additional_status=teleconsult.additional_status,
                doctor_id=str(teleconsult.doctor_id),
                queue_number=','.join([str(t.queue_number) for t in teleconsults]),
                checkin_time=teleconsult.checkin_time,
                branch_name=teleconsult.branch.name,
                user=UserResponse(
                    name=teleconsult.account.name,
                    ic_type=teleconsult.account.ic_type,
                    nric=teleconsult.account.nric
                )
            ).model_dump_json())

            if type == "INSERT":
                # Else just send out out the record for insertion
                # NOTE: This state may never be called again since Teleconsult is added as a PREPAYMENT state
                if teleconsult.status == TeleconsultStatus.CHECKED_IN:
                    output = teleconsult
                    send_new_teleconsult_notification(db, teleconsult)
                # If new record is not checked in, dont have to send anything to client
                else:
                    type = "IGNORE_INSERT"
                    output = None
            elif type == "UPDATE":
                # If the record is not checked_in (e.g. CANCELLED, MISSED state), treat as INSERT
                if teleconsult.status == TeleconsultStatus.CHECKED_IN and old_record["status"] != TeleconsultStatus.CHECKED_IN.name:
                    type = "INSERT"
                    output = output
                    send_new_teleconsult_notification(db, teleconsult)

                # If the record is in frontend, just update the existing record
                elif teleconsult.status == TeleconsultStatus.CHECKED_IN:
                    output = output
                # If updated record is not checked in, send id to delete from queue list
                # No matter old record is checked in or not checked in, send id to client for filter purpose
                else:
                    type = "FILTER"
                    output = id

    return {"type": type, "output": output}