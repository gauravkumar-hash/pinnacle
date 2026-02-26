import logging
from typing import Optional
from models import SessionLocal
from models.pinnacle import Branch, PinnacleAccount
from models.walkin import WalkInQueue
from routers.admin.walkin import WalkinAdminResp
from utils.notifications import send_doctor_notification
from routers.realtime import WSEvent, WSMessage, ws_manager

def webhook_send_notifications(branch_id: str, index: Optional[int]):
    # Do not send notifications for group teleconsults that are not the first record
    if index and index != 0:
        return
    
    with SessionLocal() as db:
        branch = db.query(Branch).filter(Branch.id == branch_id).first()
        if not branch:
            logging.error(f"Branch not found with ID: {branch_id}")
            return

        accounts = db.query(PinnacleAccount).filter(PinnacleAccount.enable_notifications == True, PinnacleAccount.deleted == False).all()
        for account in accounts:
            send_doctor_notification(account, f"New Queue Request ({branch.name})", "A new patient has requested to join the queue")

async def admin_supabase_walkin_processing(payload: dict):
    record_id = payload["record"]['id']    
    with SessionLocal() as db:
        teleconsult = db.query(WalkInQueue).filter(WalkInQueue.id == record_id).first()
        if not teleconsult:
            logging.error(f"Webhook: Walkin Record not found. ID: {id}")
            return None

        resp = WalkinAdminResp(
            id=str(teleconsult.id),
            created_at=teleconsult.created_at,
            sgimed_visit_id=teleconsult.sgimed_visit_id if teleconsult.sgimed_visit_id else "",
            queue_number=teleconsult.queue_number,
            sgimed_patient_id=teleconsult.account.sgimed_patient_id if teleconsult.account.sgimed_patient_id else "",
            patient_name=teleconsult.account.name,
            patient_nric=teleconsult.account.nric,
            branch_name=teleconsult.branch.name,
            status=teleconsult.status
        )

    await ws_manager.push_to_channel(WSMessage(event=WSEvent.ADMIN_WALKIN_UPDATE_ALL, data=resp.model_dump()))
