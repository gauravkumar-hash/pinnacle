import logging
from typing import Optional
from sqlalchemy import and_, or_
from models import SessionLocal
from models.model_enums import VisitType, WalkinQueueStatus, WalkinNotifications
from models.patient import Account
from models.payments import Invoice
from models.pinnacle import Branch
from models.walkin import WalkInQueue
from utils import sg_datetime
from utils.integrations.sgimed import cancel_pending_queue, get_queue_status, get_visit_id, get_walkin_queues, update_queue_instructions
from utils.notifications import send_patient_notification
from routers.realtime import WSEvent, WSMessage, ws_manager
from sqlalchemy.orm import Session

def get_grouped_walkins(db: Session, record: WalkInQueue, user: Optional[Account] = None):
    walkins = [record]
    if record.created_by:
        # Only for use on Doctor's endpoints
        if not user:
            user = db.query(Account).filter(Account.id == record.created_by).first()
            if not user:
                logging.error(f'Failed to find account linked to created_by: {record.created_by}')
                return [record]

        qry = db.query(WalkInQueue).filter(
                WalkInQueue.group_id == record.group_id, 
                WalkInQueue.created_by == record.created_by
            )
        # Get all MCs for the user and family members
        user_queries = [WalkInQueue.account_id == user.id]
        user_queries += [
            and_(WalkInQueue.account_id == family_member.nok_id, WalkInQueue.created_at >= family_member.created_at)
            for family_member in user.family_members
        ]
        walkins = qry.filter(or_(*user_queries)).order_by(WalkInQueue.index).all()

    return walkins

def get_walkin_queues_status(queues: list[WalkInQueue]):
    status = [q.status for q in queues]
    if WalkinQueueStatus.CHECKED_OUT in status:
        queue = queues[status.index(WalkinQueueStatus.CHECKED_OUT)]
        return queue.status, queue.queue_status    
    if WalkinQueueStatus.CHECKED_IN in status:
        queue = queues[status.index(WalkinQueueStatus.CHECKED_IN)]
        return queue.status, queue.queue_status
    return queues[0].status, queues[0].queue_status

def get_walkin_queues_numbers(queues: list[WalkInQueue], status: WalkinQueueStatus):
    queue_number = None
    checkedin_status = [WalkinQueueStatus.CHECKED_IN, WalkinQueueStatus.CONSULT_START]
    if status in checkedin_status:
        queue_number = ",".join([q.queue_number for q in queues if q.queue_number if q.status in checkedin_status])

    return queue_number

async def walkin_queue_update(visit_id: str):
    # # Ignore for now. Queue that is called, 
    # update_queue_instructions(visit_id, WalkinQueueStatus.CONSULT_START.value)
    branch_id, curr_queue_number, first_five_visit_ids = get_walkin_queues(visit_id)
    db = SessionLocal()
    # Update the current queue number for the branch
    branch = db.query(Branch).filter(Branch.sgimed_branch_id == branch_id).first()
    if branch:
        branch.walk_in_curr_queue_number = curr_queue_number
    else:
        logging.error(f"Branch not found for walkin queue update. Branch ID: {branch_id}")

    notification_msg = "Please make your way down to the clinic, your queue number is about to be called"

    records = db.query(WalkInQueue).filter(WalkInQueue.sgimed_visit_id.in_(first_five_visit_ids)).all()
    group_ids_sent = []
    for record in records:
        if record:
            if WalkinNotifications.FIVE_PATIENTS_BEFORE.value not in record.notifications_sent:
                # Skip if group_id exists, as notification has already been sent
                if record.group_id and record.group_id in group_ids_sent:
                    continue
                if record.group_id:
                    group_ids_sent.append(record.group_id)
                
                account_id = str(record.account_id if not record.created_by else record.created_by)
                await ws_manager.push_to_channel(WSMessage(
                        id=account_id, 
                        event=WSEvent.PATIENT_ACTIVITY_UPDATE
                    ))
                
                user = db.query(Account).filter(Account.id == account_id).first()
                if user:
                    send_patient_notification(
                        user,
                        f"Queue Request ({record.branch.name})",
                        notification_msg,
                    )
                record.queue_status = f"{notification_msg}. Your queue number is "

                # Update the group of walkins that notification has been sent
                for queue in get_grouped_walkins(db, record):
                    queue.notifications_sent = queue.notifications_sent + [WalkinNotifications.FIVE_PATIENTS_BEFORE.value]
                db.commit()    
        else:
            logging.info(f"Walkin queue not found for visit_id: {visit_id}. Most likely is in patient visit")

    db.commit()
    db.close()
    # TODO: Instead of updating all, should only update those that are in a walk in queue
    await ws_manager.push_to_channel(WSMessage(event=WSEvent.PATIENT_ACTIVITY_UPDATE_ALL))

async def walkin_queue_number_update(visit_id: str):
    resp = get_queue_status(visit_id)
    curr_queue_number = resp['queue_no']
    with SessionLocal() as db:
        # If record is not found, it is a physical walkin queue
        record = db.query(WalkInQueue).filter(WalkInQueue.sgimed_visit_id == visit_id).first()    
        if not record:
            return
        record.queue_number = curr_queue_number
        db.commit()
        account_id = str(record.account_id if not record.created_by else record.created_by)
        await ws_manager.push_to_channel(WSMessage(
                id=account_id, 
                event=WSEvent.PATIENT_ACTIVITY_UPDATE
            ))
        
        user = db.query(Account).filter(Account.id == account_id).first()
        if user:
            send_patient_notification(
                user,
                f"Queue Request ({record.branch.name})",
                f'Your queue number has been updated to {record.queue_number}',
                { "params": { "id": str(record.id) } }
            )

def pending_walkin_queue_update(pending_queue_id: str, accepted: bool, cancel_sgimed: bool = False):
    db = SessionLocal()
    record = db.query(WalkInQueue).filter(WalkInQueue.sgimed_pending_queue_id == pending_queue_id).first()
    if not record:
        logging.error(f"Walkin queue request not found for pending queue id: {pending_queue_id}")
        return
    
    message = ''
    if accepted:
        # Check the visit_id as sometimes the visit_id is not available in the pending queue
        visit_id = get_visit_id(pending_queue_id)
        if not visit_id:
            return

        record.sgimed_visit_id = visit_id
        record.status = WalkinQueueStatus.CHECKED_IN
        record.queue_status = 'Your queue number is '
        record.checkin_time = sg_datetime.now()
        message = f'Your queue number is {record.queue_number}'
    else:
        message = 'Clinic has rejected queue request'
        # Cancel all walkin requests in the group
        for queue in get_grouped_walkins(db, record):
            queue.status = WalkinQueueStatus.REJECTED
            queue.queue_status = 'Clinic has rejected your request as the it is currently busy'
            # When clinic rejects a queue, ensure that all visits and pending queues are also cancelled.
            if queue.sgimed_pending_queue_id != pending_queue_id:
                if queue.sgimed_visit_id:
                    update_queue_instructions(queue.sgimed_visit_id, queue.status.value)
                else:
                    cancel_pending_queue(queue.sgimed_pending_queue_id)
    db.commit()
    
    # Send notification and update user.
    title = f'Queue Request ({record.branch.name})'
    
    user = record.created_by_account if record.created_by else record.account
    if user:
        send_patient_notification(user, title, message, { 
            "pathname": '/walkin/consultation',
            "params": { "id": str(record.id) } 
        })

    db.close()

    if cancel_sgimed:
        cancel_pending_queue(pending_queue_id)

def walkin_invoice_billed_webhook(invoice_id: str, visit_id: str, invoice_html: str, mc_html: Optional[str], items: list, prescriptions: list, invoice_dict: dict):
    db = SessionLocal()
    queue = db.query(WalkInQueue).where(WalkInQueue.sgimed_visit_id == visit_id).first()
    if not queue:
        logging.info(f"SGiMed Walkin Invoice Webhook: Record not found for visit_id: {visit_id}")
        return

    if queue.invoices:
        logging.error(f"SGiMed Walkin Invoice Webhook: Invoice already exists for visit_id: {visit_id}, SGiMed invoice_id: {invoice_id}, Supabase invoice_id: {queue.invoices[0].id}")
        return

    invoice = Invoice(
        id=invoice_id,
        invoice_html=invoice_html,
        mc_html=mc_html,
        items=items,
        prescriptions=prescriptions,
        visit_type=VisitType.WALKIN,
        account_id=queue.account_id,
        amount=invoice_dict['total'],
        show_details=True,
        sgimed_last_edited=invoice_dict['last_edited']
    )
    queue.invoices.append(invoice)

    queue.status = WalkinQueueStatus.CHECKED_OUT
    queue.checkout_time = sg_datetime.now()
    queue.queue_status = "Completed"
    
    # 3. Send notification to user that the invoice is ready for viewing
    user = queue.created_by_account if queue.created_by else queue.account
    if user:
        send_patient_notification(
            user,
            f"Queue Request ({queue.branch.name})",
            "Prescription & Documents Updated",
            { 
                "pathname": '/walkin/consultation',
                "params": { "id": str(queue.id) } 
            }
        )

    db.commit()
    if not queue.sgimed_visit_id:
        logging.error(f"SGiMed Visit ID not found in walkin queue: {queue.id}")
    else:
        update_queue_instructions(queue.sgimed_visit_id, queue.status.value)

    db.close()
