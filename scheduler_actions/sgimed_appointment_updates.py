from datetime import datetime
import logging
from sqlalchemy.orm import Session
from models import SGiMedAppointment
from .common import CronLogAPI
from utils.integrations.sgimed_appointment_enums import GetSgimedAppointmentResp
from utils.appointment import compute_time_changes, update_time_changes

def update_appointments_cron(db: Session):
    cron = CronLogAPI(db, 'sgimed_appointments_cron', '/appointment')
    if len(cron.data) == 0:
        return

    updated_cnt = 0
    created_cnt = 0
    time_changes = {}
    # Get all existing appointments
    unique_ids = set([row['id'] for row in cron.data])
    existing_records = db.query(SGiMedAppointment.id, SGiMedAppointment.last_edited).filter(SGiMedAppointment.id.in_(unique_ids)).all()
    existing_records_map = {row[0]: row[1] for row in existing_records}
    
    for row_dict in cron.data:
        row = GetSgimedAppointmentResp.model_validate(row_dict)
        
        # Check for existing record
        # record = db.query(SGiMedAppointment).filter(SGiMedAppointment.id == row.id).first()
        update_dict = {
            'id': row.id,
            'subject': row.subject if row.subject else '',
            'patient_id': row.patient.id if row.patient else None,
            'calendar_id': row.calendars[0].id,
            'branch_id': row.branch_id,
            'is_all_day': row.is_all_day,
            'appointment_type_id': row.appointment_type.id,
            'is_informed': row.is_informed,
            'is_queued': row.is_queued,
            'is_cancelled': row.is_cancelled,
            'start_datetime': datetime.fromisoformat(f"{row.start_date[:11]}{row.start_time}{row.start_date[19:]}"),
            'end_datetime': datetime.fromisoformat(f"{row.end_date[:11]}{row.end_time}{row.end_date[19:]}"),
            'confirm_time': datetime.fromisoformat(row.confirm_time) if row.confirm_time else None,
            'confirm_user': row.confirm_user,
            'is_confirmed': row.is_confirmed,
            'last_edited': datetime.fromisoformat(f"{row.last_edited[:10]}T{row.last_edited[11:19]}+08:00"),
            'created_at': datetime.fromisoformat(f"{row.created_at[:10]}T{row.created_at[11:19]}+08:00"),
        }

        if row.id in existing_records_map:
            # logging.warning(f'Appointment {row.id} already exists. Updating')
            updated_cnt += 1
            # Remove previous entry since time might have changed
            record = db.query(SGiMedAppointment).filter(SGiMedAppointment.id == row.id).first()
            if not record:
                logging.error(f'Appointment Cron {row.id} not found in database despite existing earlier')
                continue
            record.update_vars(update_dict)
        else:
            created_cnt += 1
            record = SGiMedAppointment(**update_dict)
            db.add(record)

        # Compute the overall time changes
        if not record.is_all_day:
            time_changes = compute_time_changes(time_changes, record.branch_id, record.calendar_id, record.start_datetime, record.end_datetime, record.is_cancelled)
        
    if time_changes:
        update_time_changes(db, time_changes)
    cron.commit()
    print(f"Appointment Cron: {cron.cron_log.last_modified}, page {cron.cron_log.last_page}. Updated {updated_cnt}, Created {created_cnt}")
