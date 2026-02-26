from datetime import datetime, timedelta
from models import SGiMedAppointment, SessionLocal
from models.model_enums import AppointmentStatus
from models.appointment import Appointment, AppointmentAuditLog
from utils.appointment import compute_time_changes, update_time_changes
from utils.integrations.sgimed_appointment import get_appointment
from sqlalchemy.orm import Session
from utils.notifications import send_patient_notification
from utils.sg_datetime import sgtz
from typing import Literal

# NOTE: This logic is for SGiMed Appointment updates to sync Patient Appointments and available Appointment slots
# - [ ] Guests are not handled for 2 way sync
# - [ ] Webhooks are the basis for updates. Not integrated into polling

def get_patient_appointment(db: Session, appointment_id: str):
    appt = db.query(Appointment).filter(Appointment.sgimed_appointment_id == appointment_id).first()
    return appt

def send_notification(appt: Appointment, sgimed_resp: dict, state: Literal['cancelled', 'rescheduled']):
    # Send Notification
    patient_name = ''
    if 'patient' in sgimed_resp:
        patient_name = sgimed_resp['patient']['name'] 
    elif appt.account:
        patient_name = appt.account.name
    start_time = appt.start_datetime.astimezone(sgtz).strftime('%Y-%m-%d %H:%M')
    send_patient_notification(
        appt.created_by_account,
        f"Appointment {state}",
        f"Your appointment {'for ' + patient_name if patient_name else ''}{' on ' + start_time if state == 'cancelled' else ''} has been {state}{(' to ' + start_time if state == 'rescheduled' else '')}.",
        { 
            "pathname": '/appointment/consultation',
            "params": { "id": str(appt.id) } 
        }
    )

def reschedule_appointment(db: Session, appt: Appointment, sgimed_resp: dict, action: str):
    '''
    NOTE: This does not handle guests
    '''
    # Logic is that if the timing is within the index range, then it is not considered to be rescheduled
    duration = appt.duration // ((len(appt.guests) if appt.guests else 0) + int(bool(appt.account_id)))
    new_starttime = datetime.fromisoformat(sgimed_resp['start_date'][:10] + 'T' + sgimed_resp['start_time'] + '+08:00')
    appt_start = appt.start_datetime.astimezone(sgtz)
    appt_end = appt_start + timedelta(minutes=(duration * appt.index if appt.index is not None else duration))
    if appt_start <= new_starttime and new_starttime <= appt_end:
        return

    # Add to Audit Log
    log = AppointmentAuditLog(
        sgimed_appointment_id=appt.sgimed_appointment_id,
        sgimed_payload=sgimed_resp,
        source="sgimed",
        action=action,
    )
    db.add(log)
    
    # Update Appointment Timing
    appt.start_datetime = new_starttime
    db.commit()
    
    # Send Notification
    send_notification(appt, sgimed_resp, "rescheduled")

def cancel_appointment(db: Session, appt: Appointment, sgimed_resp: dict, action: str):
    '''
    NOTE: This does not handle guests
    '''
    if not appt.status == AppointmentStatus.CANCELLED:
        # Add to Audit Log
        log = AppointmentAuditLog(
            sgimed_appointment_id=appt.sgimed_appointment_id,
            sgimed_payload=sgimed_resp,
            source="sgimed",
            action=action,
        )
        db.add(log)

        # Cancel Appointment
        appt.status = AppointmentStatus.CANCELLED
        db.commit()

        # Send Notification
        send_notification(appt, sgimed_resp, "cancelled")

def sgimed_appointment_updated_webhook(appointment_id: str):
    resp = get_appointment(appointment_id)
    with SessionLocal() as db:
        appt = get_patient_appointment(db, appointment_id)
        if not appt:
            return
        reschedule_appointment(db, appt, resp, "webhook.appointment.updated")

def sgimed_appointment_cancelled_webhook(appointment_id: str):
    with SessionLocal() as db:
        appt = get_patient_appointment(db, appointment_id)
        if not appt:
            return
        cancel_appointment(db, appt, { 'id': appointment_id }, "webhook.appointment.cancelled")

def sgimed_appointment_deleted_webhook(appointment_id: str):
    with SessionLocal() as db:
        appointment = db.query(SGiMedAppointment).filter(SGiMedAppointment.id == appointment_id).first()
        if appointment:
            appointment.subject = 'Deleted: ' + appointment.subject 
            appointment.is_cancelled = True
            db.commit()

            # Free up time slots
            if not appointment.is_all_day:
                time_changes = compute_time_changes({}, appointment.branch_id, appointment.calendar_id, appointment.start_datetime, appointment.end_datetime, appointment.is_cancelled)
                update_time_changes(db, time_changes)

        # Cancel Appointment if deleted
        appt = get_patient_appointment(db, appointment_id)
        if not appt:
            return
        cancel_appointment(db, appt, { 'id': appointment_id }, "webhook.appointment.deleted")
