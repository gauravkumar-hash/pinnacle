# Guide: https://rajansahu713.medium.com/implementing-background-job-scheduling-in-fastapi-with-apscheduler-6f5fdabf3186
from datetime import datetime, timedelta
import time
from apscheduler.schedulers.blocking import BlockingScheduler
import sentry_sdk
# from apscheduler.jobstores.memory import MemoryJobStore

from config import SENTRY_DSN
from models import SessionLocal
from models.model_enums import TeleconsultStatus, WalkinQueueStatus
from models.pinnacle import Branch
from models.teleconsult import Teleconsult
from models.walkin import WalkInQueue
from routers.patient.actions.walkin import pending_walkin_queue_update
from scheduler_actions.appointment_updates import send_appointment_notifications
from scheduler_actions.sgimed_updates import load_cron_log, update_delivery_method_cron, update_documents_cron, update_invoices_cron, update_mcs_cron, update_patient_profiles_cron
from scheduler_actions.sgimed_health_report_updates import generate_health_reports, update_hl7_logs_cron, update_incoming_reports_cron, update_measurements_cron
from scheduler_actions.sgimed_appointment_updates import update_appointments_cron
from scheduler_actions.sgimed_sync import update_inventory_details_cron, update_inventory_sync_cron, update_appointment_types_sync_cron
from scheduler_actions.yuu_updates import retry_failed_transactions, send_yuu_transacion_refunds
from services.reconciliation import process_reconciliation
from utils import sg_datetime
from scheduler_actions.delivery_updates import hide_expired_delivery_note_action

sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    send_default_pii=True,
    enable_tracing=True
)

# Initialize a SQLAlchemyJobStore with SQLite database
# jobstores = {
#     'default': MemoryJobStore()
# }
# Initialize an AsyncIOScheduler with the jobstore
# scheduler = AsyncIOScheduler(jobstores=jobstores, timezone='Asia/Singapore') 
# scheduler = BackgroundScheduler(timezone='Asia/Singapore') 
scheduler = BlockingScheduler(timezone='Asia/Singapore')

@scheduler.scheduled_job('interval', minutes=30)
def scheduled_payment_reconciliation():
    with SessionLocal() as db:
        cron_log = load_cron_log(db, 'reconciliation_cron')
        # Process Reconciliation
        start_time = cron_log.last_modified
        end_time = datetime.now()
        process_reconciliation(db, start_time, end_time)
        # Update Timing
        cron_log.last_modified = end_time
        print(f"Reconciliation Cron: Last Edited: {cron_log.last_modified}")
        db.commit()

# This is a scheduled job that will run every 5 minutes.
@scheduler.scheduled_job('interval', minutes=5)
def scheduled_clear_pending_queues():
    print("Scheduler: Scheduled to run every 1 minute to clear any pending queues past 30 minutes")
    with SessionLocal() as db:
        records = db.query(WalkInQueue).filter(
                WalkInQueue.status == WalkinQueueStatus.PENDING,
                WalkInQueue.created_at < sg_datetime.now() - timedelta(minutes=30)
            ).all()

        for record in records:
            pending_walkin_queue_update(record.sgimed_pending_queue_id, False, cancel_sgimed=True)
            print(f"Rejected {record.sgimed_pending_queue_id}. Created Time: {record.created_at}, Curr Time: {sg_datetime.now()}")

# This is a scheduled job that will run every 1 minutes.
@scheduler.scheduled_job('interval', minutes=1)
def scheduled_sgimed_updates():
    print("Scheduler: Scheduled to run every 1 minute to clear any pending queues past 30 minutes")
    start_time = time.time()
    with SessionLocal() as db:
        update_patient_profiles_cron(db)
        update_documents_cron(db)
        visit_ids_processed = update_invoices_cron(db)
        update_mcs_cron(db, visit_ids_processed)

    print(f"Time Taken: {time.time() - start_time:.2f} seconds")

@scheduler.scheduled_job('interval', minutes=1)
def scheduled_sgimed_appointment_updates():
    print("Scheduler: Scheduled to run every 1 minute to update sgimed appointments")
    start_time = time.time()
    with SessionLocal() as db:
        update_appointments_cron(db)
        
    print(f"Time Taken: {time.time() - start_time:.2f} seconds")

# TODO: Profile and Invoice Polling (Half Daily)
@scheduler.scheduled_job('cron', day_of_week='mon-sun', hour=0, minute=0, second=0)  # Decorator for scheduling the job
def scheduled_clear_midnight_teleconsults():  # Function to be executed at the scheduled time
    print(f"Scheduler: Running at midnight to convert any missed/cancelled teleconsults to checked out {sg_datetime.now()}") 

    curr_time = sg_datetime.midnight(sg_datetime.now() + timedelta(seconds=10))
    print(f"Retrieving teleconsults before {curr_time}")

    with SessionLocal() as db:
        records = db.query(Teleconsult).filter(
                Teleconsult.status.in_((TeleconsultStatus.CANCELLED, TeleconsultStatus.MISSED)),
                Teleconsult.created_at < curr_time
            ).all()
        
        for record in records:
            print(f"{record.id}: {record.status}, {record.created_at}")
            record.queue_status = "Completed"
            record.additional_status = record.status
            record.status = TeleconsultStatus.CHECKED_OUT
            record.doctor_id = None
            record.teleconsult_start_time = None
            record.teleconsult_join_time = None
            record.teleconsult_end_time = None
            record.checkout_time = curr_time

        queue_numbers = [record.queue_number for record in records if record.queue_number]
        ids = [str(record.id) for record in records]
        print(f"{curr_time}: Checked out {len(records)} ([{','.join(queue_numbers)}]) teleconsults (CANCELLED/MISSED) successfully. [IDs: {','.join(ids)}]")
        
        # Update Branch Walk In Queue Number
        branches = db.query(Branch).all()
        for branch in branches:
            branch.walk_in_curr_queue_number = None
        print(f"{curr_time}: Reset Clinic Queue number to None")

        db.commit()

# This is the scheduler to manage delivery note expiry
@scheduler.scheduled_job('interval', days=1)
def scheduled_delivery_note_expiry():
    print(f"Scheduler: Running to hide expired delivery notes {sg_datetime.now()} every one day")
    with SessionLocal() as db:
        hide_expired_delivery_note_action(db)
        print(f"Scheduler: Hidden expired delivery notes {sg_datetime.now()} successfully")

# This is the scheduler to manage change of delivery method
@scheduler.scheduled_job('interval', minutes=1)
def scheduled_delivery_method_change():
    print(f"Scheduler: Running to change delivery method {sg_datetime.now()} every minute")
    with SessionLocal() as db:
        update_delivery_method_cron(db)        
        print(f"Scheduler: Changed delivery method {sg_datetime.now()} successfully")

@scheduler.scheduled_job('interval', minutes=45)
def scheduled_update_health_report_logs():
    print(f"Scheduler: Running to update Health Report (HL7, Incoming Reports) logs {sg_datetime.now()}")
    with SessionLocal() as db:
        update_hl7_logs_cron(db)
        update_incoming_reports_cron(db)
        update_measurements_cron(db)

@scheduler.scheduled_job('cron', day_of_week='mon-sun', hour=1, minute=0, second=0)
def scheduled_process_health_reports():
    print(f"Scheduler: Running to process health reports {sg_datetime.now()}")
    with SessionLocal() as db:
        generate_health_reports(db)

@scheduler.scheduled_job('interval', minutes=5)
def scheduled_inventory_sync():
    print(f"Scheduler: Running inventory sync from SGiMed {sg_datetime.now()}")
    start_time = time.time()
    with SessionLocal() as db:
        update_appointment_types_sync_cron(db)
        update_inventory_sync_cron(db)
        update_inventory_details_cron(db)

    print(f"Inventory and appointment types sync completed. Time taken: {time.time() - start_time:.2f} seconds")

@scheduler.scheduled_job('cron', day=1, hour=0, minute=0, second=0)  # Decorator for scheduling the job
def scheduled_send_yuu_transacion_refunds():
    print(f"Scheduler: Running to send Yuu transaction refunds {sg_datetime.now()}")
    with SessionLocal() as db:
        send_yuu_transacion_refunds(db)

@scheduler.scheduled_job('interval', hours=1)
def scheduled_retry_failed_transactions():
    print(f"Scheduler: Running to retry failed transactions {sg_datetime.now()}")
    with SessionLocal() as db:
        retry_failed_transactions(db)

@scheduler.scheduled_job('interval', hours=1)
def scheduled_send_notifications():
    print(f"Scheduler: Running to send 1 day before appointment notifications {sg_datetime.now()}")
    with SessionLocal() as db:
        send_appointment_notifications(db)

# import tracemalloc
# tracemalloc.start()

# @scheduler.scheduled_job('cron', second='*/5')  # Decorator for scheduling the job
# def take_memory_snapshot():  # Function to be executed at the scheduled time
#     current, peak = tracemalloc.get_traced_memory()
#     print('Current and peak memory usage: {} {}'.format(current / 1048576, peak / 1048576))
#     snapshot = tracemalloc.take_snapshot()
#     top_stats = snapshot.statistics('lineno')
#     logging.info(f"[ Top 10 ]:")
#     for stat in top_stats[:10]:
#         logging.info(stat)

print("Start Scheduler")
scheduler.start()