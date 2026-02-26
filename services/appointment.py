from datetime import timedelta
import logging
from typing import Optional
from models import Session, Appointment, Payment, Account
from models.model_enums import AppointmentStatus
from models.pinnacle import Branch
from repository.appointment import get_appointment_by_payment, get_grouped_appointments
from services.yuu import submit_yuu_appointment_transaction
from utils.integrations.sgimed_appointment import post_appointment_by_guest, post_appointment_by_patient
from utils.integrations.sgimed import create_invoice, InvoiceRecord, InvoiceItemRecord, InvoicePaymentRecord, upsert_patient_in_sgimed
from models.appointment import AppointmentService, GuestCol
from utils.system_config import get_config_value
from utils.email import send_appointment_notification_email
from utils.executors import email_executor
from utils.sg_datetime import sgtz
from pydantic import BaseModel

class AppointmentConstants(BaseModel):
    DEFAULT_ONSITE_BRANCH_ID: str
    DEFAULT_DOCTOR_ID: str

def get_appointment_constants(db: Session):
    return AppointmentConstants.model_validate(get_config_value(db, 'APPOINTMENT_CONSTANTS'))

# routers/patient/appointment.py: confirm_appointment
# routers/patient/webhook.py
# routers/payments/pgw2c2p/router.py
def appointment_success_webhook(db: Session, payments: list[Payment] = [], appt: Optional[Appointment] = None):
    # If there are no payments, get the appointment from the database
    if not appt:
        payment = payments[0]    
        appt = get_appointment_by_payment(db, payment)
        if not appt:
            logging.error(f"Appointment Payment Webhook: Appointment not found for payment {payment.id}")
            return

    appts = get_grouped_appointments(db, appt)
    # Trigger calls to SGiMed
    branch = db.query(Branch).filter(Branch.id == appt.branch['id']).first()
    if not branch:
        logging.error(f"Appointment Payment Webhook: Branch not found for appointment {appt.id}")
        return

    # Confirm Appointments
    start_dt = appt.start_datetime.astimezone(sgtz)
    total_price = appt.get_payment_breakdown().total
    services = appt.get_services()
    service_groups = [svc.name for svc in services]
    service_items = [item.name for svc in services for item in svc.items]
    created_by = db.query(Account).filter(Account.id == appt.created_by).first()
    if not created_by:
        logging.error(f"Appointment Payment Webhook: Account not found for appointment {appt.id}")
        return

    # If the created_by is not a patient in SGiMed, upsert the patient in SGiMed
    if not created_by.sgimed_patient_id:
        upsert_patient_in_sgimed(db, created_by, branch=branch)

    # Handle the main appointment
    if appt.guests or appt.account_id:
        duration_per_pax = appt.duration // ((len(appt.guests) if appt.guests else 0) + int(bool(appt.account_id)))
        if appt.account_id:
            account = db.query(Account).filter(Account.id == appt.account_id).first()
            if not account:
                logging.error(f"Appointment Payment Webhook: Account not found for appointment {appt.id}")
                return
            upsert_patient_in_sgimed(db, account, branch=branch)
            sgimed_appointment_id = post_appointment_by_patient(
                user=account,
                branch=branch,
                start_dt=start_dt,
                duration=duration_per_pax,
                price=total_price,
                service_groups=service_groups,
                service_items=service_items,
                created_by=created_by
            )
            appt.sgimed_appointment_id = sgimed_appointment_id
            start_dt += timedelta(minutes=duration_per_pax)

        appt_guests = appt.get_guests()
        if appt_guests:
            guests_with_appt_id: list[GuestCol] = []
            for guest in appt_guests:
                sgimed_appointment_id = post_appointment_by_guest(
                    guest_name=guest.name,
                    guest_mobile=guest.mobile,
                    branch=branch,
                    start_dt=start_dt,
                    duration=duration_per_pax,
                    price=total_price,
                    service_groups=service_groups,
                    service_items=service_items,
                    created_by=created_by,
                )
                guest.sgimed_appointment_id = sgimed_appointment_id
                guests_with_appt_id.append(guest)
                start_dt += timedelta(minutes=duration_per_pax)

            appt.guests = [guest.model_dump() for guest in guests_with_appt_id]

    # Handle the additional family appointments
    for _appt in appts[1:]:
        account = db.query(Account).filter(Account.id == _appt.account_id).first()
        if not account:
            logging.error(f"Appointment Payment Webhook: Account not found for appointment {_appt.id}")
            continue
        upsert_patient_in_sgimed(db, account, branch=branch)
        sgimed_appointment_id = post_appointment_by_patient(
            user=account,
            branch=branch,
            start_dt=start_dt,
            duration=_appt.duration,
            price=total_price,
            service_groups=service_groups,
            service_items=service_items,
            created_by=created_by,
        )
        _appt.sgimed_appointment_id = sgimed_appointment_id
        start_dt += timedelta(minutes=_appt.duration)

    # Create invoices for the appointments
    try:
        if total_price > 0:
            # Main appointment + Family appointments + Guests
            qty = len(appts) \
                + (0 if appt.account_id else -1) \
                + (len(appt.guests) if appt.guests else 0)
            invoice_id = create_appointment_invoice(db, appt, qty, payments[0])
            appt.invoice_ids = appt.invoice_ids + [invoice_id]
    except Exception as e:
        logging.error(f"Failed to create invoice for appointments: {str(e)}")
        # Don't fail the entire process if invoice creation fails

    for _appt in appts:
        _appt.status = AppointmentStatus.CONFIRMED
    db.commit()
    # Submit YUU Transaction
    submit_yuu_appointment_transaction(db, appt)

    # Send email notification to clinic (non-blocking)
    try:
        # Capture appointment ID before background task
        appointment_id = str(appt.id)

        # Send email in background thread to avoid blocking
        def send_email_task() -> None:
            try:
                send_appointment_notification_email(appointment_id)
                logging.info(f"Appointment notification email sent for appointment {appointment_id}")
            except Exception as email_error:
                logging.error(
                    f"Failed to send appointment notification email for appointment {appointment_id}: {str(email_error)}",
                    exc_info=True
                )

        email_executor.submit(send_email_task)
    except Exception as e:
        logging.error(f"Failed to schedule appointment notification email for appointment {appt.id}: {str(e)}", exc_info=True)
        # Don't fail the entire process if email scheduling fails

def create_appointment_invoice(db: Session, appt: Appointment, qty: int, payment: Payment):
    """Create an invoice for an appointment in SGiMed system"""
    # Build invoice items from appointment services
    invoice_items = []
    for service_group in appt.get_services():
        for service_item in service_group.items:
            # Map service to SGiMed inventory item
            service_id = service_item.id
            service_price = service_item.prepayment_price
            if service_price <= 0:
                continue

            service = db.query(AppointmentService).filter(AppointmentService.id == service_id).first()
            if not service or not service.sgimed_inventory:
                logging.error(f"Appointment Payment Webhook: Service {service_id} does not have an inventory item")
                continue

            invoice_items.append(InvoiceItemRecord(
                item_code=service.sgimed_inventory.code,
                qty=qty,
                selling_price=round(service_price, 2)
            ))

    # Build payment records
    invoice_payments = []
    invoice_payments.append(InvoicePaymentRecord(
        payment_mode_id=payment.payment_mode.sgimed_payment_mode_id,
        amount=round(payment.payment_amount, 2),
        remark=f'{payment.payment_type.value}, {payment.payment_method.value}: {payment.payment_id}'
    ))

    branch = appt.get_branch()
    appointment_constants = get_appointment_constants(db)
    account = db.query(Account).filter(Account.id == appt.created_by).first()
    if not account:
        raise Exception(f'Failed to create invoice for appointment {appt.id} because account is null')

    # Create invoice record
    invoice_record = InvoiceRecord(
        patient_id=str(account.sgimed_patient_id),
        branch_id=branch.sgimed_branch_id,
        date=appt.start_datetime.date(),
        appointment_type_id=branch.sgimed_appointment_type_id,
        doctor_id=appointment_constants.DEFAULT_DOCTOR_ID,
        items=invoice_items,
        payments=invoice_payments
    )
    
    # Create invoice in SGiMed
    invoice_id = create_invoice(invoice_record)
    return invoice_id
