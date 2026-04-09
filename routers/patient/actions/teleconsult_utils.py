# Code logic for all things Teleconsult table
import logging
from typing import Optional
from sqlalchemy import and_, or_
from models.patient import Account
from utils.integrations.sgimed import update_queue_instructions
from utils.notifications import send_patient_notification, send_voip_notification
from models import Teleconsult, TeleconsultStatus, SessionLocal
from sqlalchemy.orm import Session

# # TODO: Phase 2 Add the logic to update the queue instructions when changed from SGiMed
# def sgimed_triggered_queue_status_change():
#     '''
#     1. SGiMed Queues screen Instruction update
#     '''
#     pass

def get_grouped_teleconsults(db: Session, record: Teleconsult, user: Optional[Account] = None):
    teleconsults = [record]
    if record.created_by:
        # Only for use on Doctor's endpoints
        if not user:
            user = db.query(Account).filter(Account.id == record.created_by).first()
            if not user:
                logging.error(f'Failed to find account linked to created_by: {record.created_by}')
                return [record]

        qry = db.query(Teleconsult).filter(
                Teleconsult.group_id == record.group_id, 
                Teleconsult.created_by == record.created_by
            )
        # Get all MCs for the user and family members
        user_queries = [Teleconsult.account_id == user.id]
        user_queries += [
            and_(Teleconsult.account_id == family_member.nok_id, Teleconsult.checkin_time >= family_member.created_at)
            for family_member in user.family_members
        ]
        teleconsults = qry.filter(or_(*user_queries)).order_by(Teleconsult.index).all()

    return teleconsults

def fetch_notification_account(db: Session, teleconsult: Teleconsult):
    # If not the same account, retrieve the account
    if teleconsult.created_by:
        account: Account | None = db.query(Account).filter(Account.id == teleconsult.created_by).first()
        if not account:
            logging.error(f"Failed to send notifications! Account not found for teleconsult: {teleconsult.id}")
            return
    else:
        account = teleconsult.account
    
    return account

def user_triggered_queue_status_change(teleconsult_id: str):
    '''
    1. Patient's App - Cancel Consulation (CANCELLED)
    2. Doctor's App - Start (CONSULT_START), End (CONSULT_END), Cancel Consultation (MISSED)
    '''
    # Update instructions in SGiMed Queues table
    with SessionLocal() as db:
        teleconsult = db.query(Teleconsult).filter(Teleconsult.id == teleconsult_id).first()
        if not teleconsult or not teleconsult.sgimed_visit_id:
            logging.error(f"Teleconsult or sgimed_visit_id was not found: {teleconsult_id}")
            return

        update_queue_instructions(teleconsult.sgimed_visit_id, teleconsult.status.value)
    
        # Ignore notifications if the teleconsult is not the first record
        if teleconsult.group_id and teleconsult.index != 0:
            return
    
        user = fetch_notification_account(db, teleconsult)
        if not user:
            return

        _trigger_queue_notifications(db) # Trigger notifications for patients in the queue if the previous status is not set or the current record is changed from the previous status
        if teleconsult.status == TeleconsultStatus.CONSULT_START:
            send_voip_notification(user, teleconsult)
            send_patient_notification(
                user,
                "Virtual Consultation",
                "Your session has started"
            )

        elif teleconsult.status == TeleconsultStatus.MISSED:
            send_patient_notification(
                user,
                "Virtual Consultation",
                "Look's like you've missed the call. You may wish to join the queue again.",
                { 
                    "pathname": '/teleconsult/consultation',
                    "params": { "id": str(teleconsult.id) } 
                }
            )

def _trigger_queue_notifications(db: Session):
    '''
    This would trigger whenever a doctor makes a change on the doctors app
    
    1. Retrieve the latest top 5 queues
    2. Send notifications when the user in the queue is 3rd and 5th in the queue
    3. Add notifications sent to their record
    '''
    # TODO: Consider separating notifications for MW and Private
    queues = db.query(Teleconsult).filter(
            Teleconsult.status == TeleconsultStatus.CHECKED_IN,
            or_(Teleconsult.index == 0, Teleconsult.index == None)
        ).order_by(Teleconsult.checkin_time.asc()).limit(5).all()

    msg_mapping = [
        "You are next in line",
        "There is 1 patient ahead of you",
    ]

    for i, queue in enumerate(queues):
        # Skip queue 4
        if str(i) in queue.notifications_sent:
            continue

        message = msg_mapping[i] if i < len(msg_mapping) else f"There are {i} patients ahead of you"
        user = fetch_notification_account(db, queue)
        if not user:
            logging.error(f"Failed to send notifications! Account not found for teleconsult: {queue.id}")
            return
    
        send_patient_notification(
            user,
            "Virtual Consultation",
            message,
            priority='high'
        )
        queue.queue_status = message
        queue.notifications_sent = queue.notifications_sent + [str(i)]
        db.commit()
