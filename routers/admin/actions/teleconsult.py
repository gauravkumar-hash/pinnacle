import logging
from models import SessionLocal
from models.teleconsult import Teleconsult
from routers.admin.teleconsult import TeleconsultAdminResp
from routers.realtime import WSMessage, ws_manager, WSEvent

async def admin_supabase_webhook_processing(payload: dict):
    # Handle the payload received from Supabase realtime changes
    # print(payload)
    type = payload["type"]
    record = payload["record"]
    if record["status"] == 'PREPAYMENT':
        print("Webhook: Ignoring PREPAYMENT status update")
        return None

    id = record['id']

    with SessionLocal() as db:
        teleconsult = db.query(Teleconsult).filter(Teleconsult.id == id).first()
        if not teleconsult:
            logging.error(f"Webhook: Teleconsult not found. ID: {id}")
            return None

        resp = TeleconsultAdminResp(
            id=str(teleconsult.id),
            sgimed_visit_id=teleconsult.sgimed_visit_id if teleconsult.sgimed_visit_id else "",
            queue_number=teleconsult.queue_number,
            checkin_time=teleconsult.checkin_time,
            sgimed_patient_id=teleconsult.account.sgimed_patient_id if teleconsult.account.sgimed_patient_id else "",
            patient_type=teleconsult.patient_type,
            patient_name=teleconsult.account.name,
            patient_nric=teleconsult.account.nric,
            branch_name=teleconsult.branch.name,
            corporate_code=teleconsult.corporate_code,
            hide_invoice=teleconsult.invoices[0].hide_invoice if teleconsult.invoices else None,
            status=teleconsult.status,
            doctor_name=teleconsult.doctor.name if teleconsult.doctor else ""
        )

    await ws_manager.push_to_channel(WSMessage(event=WSEvent.ADMIN_TELECONSULT_UPDATE_ALL, data=resp.model_dump()))
