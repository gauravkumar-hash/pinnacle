from sqlalchemy import or_
from sqlalchemy.orm import Session
from models import Appointment, Account
from models.model_enums import AppointmentStatus
from repository.appointment import get_grouped_appointments
from utils import sg_datetime
from datetime import timedelta
from utils.notifications import send_patient_notification
from utils.integrations.sgimed_appointment import update_appointment_status
import logging

def send_appointment_notifications(db: Session):
    now = sg_datetime.now()
    appts = db.query(Appointment) \
        .filter(
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.start_datetime > now,  # Exclude past appointments
            Appointment.start_datetime <= (now + timedelta(days=1)),  # Within next 24 hours
            or_(Appointment.index == 0, Appointment.index == None),
            ~Appointment.notifications_sent.any('appt_1_day_reminder'), # type: ignore
        ).all()

    for appt in appts:
        account = db.get(Account, appt.created_by)
        if not account:
            logging.error(f"Appointment {appt.id} has no account {appt.created_by}")
            continue
        
        # Send Notification to Primary User
        send_patient_notification(
            account, 
            "Appointment Reminder", 
            "This is a reminder that you have an appointment scheduled for " + sg_datetime.sg(appt.start_datetime).strftime("%I:%M %p") + " tomorrow at " + appt.branch['name']
        )
        appt.notifications_sent = appt.notifications_sent + ['appt_1_day_reminder']
        db.commit()

        appts = get_grouped_appointments(db, appt)
        for appt in appts:
            # Update on SGiMed Appointment Informed. It can be None because primary appointment is not created on SGiMed.
            if appt.sgimed_appointment_id:
                update_appointment_status(appt.sgimed_appointment_id, is_informed=True)
