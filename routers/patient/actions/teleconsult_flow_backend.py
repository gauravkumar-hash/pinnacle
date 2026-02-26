## Backend Listeners
import logging
from typing import Optional
from models import SessionLocal, Payment, Teleconsult, TeleconsultStatus, Invoice
from models.model_enums import VisitType
from models.payments import CorporateCode
from models.pinnacle import StAndrew
from services.user import user_is_pcp
from routers.patient.actions.teleconsult_utils import fetch_notification_account, get_grouped_teleconsults
from services.yuu import submit_yuu_transaction
from utils.integrations.sgimed import EmployeeInfo, get_queue_status, insert_prepayment_to_invoice, update_payments, update_queue_instructions, upsert_patient_in_sgimed, create_queue
from utils.notifications import send_patient_notification
from sqlalchemy.orm import Session
from config import SGIMED_MEDICATION_ITEM_TYPE
from utils.system_config import get_sgimed_telemed_routing_params
from utils import sg_datetime
from routers.delivery.actions.delivery import teleconsult_delivery_object_handler

# def main():
    # payment_success_webhook("1234", PaymentMethod.PAYNOW_STRIPE)
    # cron_midnight_reset()
    # invoice_billed_webhook("17167249261007139")
    # invoice_billed_webhook("17168692879170043")
    # pass

# https://www.youtube.com/watch?v=m5H54NcvBRU

# # Source: https://medium.com/@priyanshu009ch/schedule-cron-jobs-in-fastapi-de2a342620f9
# @router.on_event("startup")

def prepayment_success_webhook(db: Session, payments: list[Payment]):
    '''
    Status update from the payment provider on the payment status.
    This will update the payment status in the database

    1. Once payment succeeds, upsert user from Supabase to SGiMed
    2. Create queue of the user in SGiMed
    3. Update teleconsult record in database with sgimed_visit_id in supabase
    4. Link payment id with teleconsult in Supabase
    '''
    for payment in payments:
        # 1. Once payment succeeds, upsert information from Supabase to SGiMed
        user = payment.account
        
        # Get the employee information if the user is from StAndrew
        employee = None
        is_pcp = user_is_pcp(db, user.nric)
        if is_pcp:
            record = db.query(StAndrew).filter(StAndrew.nric == user.nric).first()
            if record:
                employee = EmployeeInfo(employee_id=f"{record.employee_no}", employee_company=f"{record.comp_code} - {record.company_name}")
            else:
                logging.error(f"StAndrew record not found for user: {user.id}")

        # 3. Find teleconsult record in Supabase, and update with visit_id in supabase
        teleconsult = db.query(Teleconsult).filter(
                Teleconsult.status == TeleconsultStatus.PREPAYMENT,
                Teleconsult.account_id == user.id
            ).first()
        if not teleconsult:
            # Check if the teleconsult is already in the next state, if so, tell payment provider that webhook is successful
            if payment.teleconsults and payment.teleconsults[0].sgimed_visit_id:
                logging.info(f"Payment Webhook: Teleconsult already has sgimed_visit_id. Payment: {payment.id}, Teleconsult: {payment.teleconsults[0].id}")
                return True
    
            raise Exception(f"Failed to find Teleconsult record for {user.id}")

        upsert_patient_in_sgimed(db, user, employee, teleconsult.branch)
        if not user.sgimed_patient_id:
            raise Exception(f"SGiMed Patient ID not found for user: {user.id}")

        # 2. Create queue of the user in SGiMed
        # Instead of checking SGiMed ID for new user, as long as there is no teleconsult invoice, we consider it as new user
        is_new_user = db.query(Invoice).filter(
            Invoice.visit_type == VisitType.TELECONSULT, 
            Invoice.account_id == user.id
        ).first() is None
        # Checks the routing params to route to the right branch
        sgimed_branch_id, sgimed_appointment_type_id = get_sgimed_telemed_routing_params(db, teleconsult)
        visit_id = create_queue(
            user.sgimed_patient_id, 
            payment, 
            teleconsult, 
            sgimed_appointment_type_id, 
            is_new_user, 
            sgimed_branch_id
        )
        
        # Get queue status and update teleconsult record
        resp = get_queue_status(visit_id)
        queue_number = resp.get('queue_no')
        if not queue_number:
            logging.warning(f"Queue number not returned from SGiMed for visit_id: {visit_id}")
        teleconsult.sgimed_visit_id=visit_id
        teleconsult.queue_number=queue_number
        teleconsult.status=TeleconsultStatus.CHECKED_IN
        teleconsult.checkin_time = sg_datetime.now()
        db.commit()

        # Add invoice item
        try:
            items = [{ 'item_code': row['code'], 'qty': 1 } for row in teleconsult.payment_breakdown if 'code' in row and row['code']]
            insert_prepayment_to_invoice(visit_id, items)
        except Exception as e:
            logging.error(f"Failed to add invoice/item: {str(e)}")
            # Don't re-raise this exception, as we've already updated the teleconsult status

    return True

def postpayment_success_webhook(db: Session, payments: list[Payment]):
    for payment in payments:
        user = payment.account
        teleconsult = db.query(Teleconsult).filter(
                Teleconsult.status == TeleconsultStatus.OUTSTANDING,
                Teleconsult.account_id == user.id
            ).first()
        if not teleconsult:
            if payment.teleconsults and payment.teleconsults[0].status == TeleconsultStatus.CHECKED_OUT:
                logging.error(f"Stripe Postpayment Webhook: Teleconsult already CHECKED OUT. Payment: {payment.id}, Teleconsult: {payment.teleconsults[0].id}")
                return True

            raise Exception(f"Failed to find Teleconsult record for {user.id}")

        teleconsult.balance = 0
        teleconsult.complete(db)
        teleconsult_delivery_object_handler(teleconsult, db)
        
        # Update Payment and Queue Instructions in SGiMed
        if teleconsult.sgimed_visit_id is None:
            logging.error(f"SGiMed Visit ID not found for teleconsult: {teleconsult.id}")
        else:
            update_payments(teleconsult.invoices[0].id, teleconsult)
            has_medication = any([item['item_type'] == SGIMED_MEDICATION_ITEM_TYPE for item in teleconsult.invoices[0].items])
            instruction = TeleconsultStatus.DISPENSE_MEDICATION if has_medication else teleconsult.status
            update_queue_instructions(teleconsult.sgimed_visit_id, instruction.value)

    return True

def teleconsult_invoice_billed_webhook(invoice_id: str, visit_id: str, invoice_html: str, mc_html: Optional[str], items: list, prescriptions: list, invoice_dict: dict):
    '''
    Webhook when invoice is billed in SGiMed.
    
    1. Fetch invoice, diagnosis, items, prescription, and MC from SGiMed
    2. Save the invoice, diagnosis, items, prescription, and MC in Supabase
    3. Send notification to user that the invoice is ready for viewing
    '''
    # Update the information into Supabase
    db = SessionLocal()
    teleconsult = db.query(Teleconsult).where(Teleconsult.sgimed_visit_id == visit_id).first()
    if not teleconsult:
        logging.info(f"SGiMed Invoice Webhook: Teleconsult not found for visit_id: {visit_id}")
        return

    if teleconsult.invoices:
        logging.error(f"SGiMed Teleconsult Invoice Webhook: Invoice already exists for visit_id: {visit_id}, SGiMed invoice_id: {invoice_id}, Supabase invoice_id: {teleconsult.invoices[0].id}")
        return

    # If there is a corporate code, check if the invoice should be hidden
    hide_invoice = False
    if teleconsult.corporate_code:
        record = db.query(CorporateCode).filter(CorporateCode.code == teleconsult.corporate_code.upper()).first()
        if record:
            hide_invoice = record.hide_invoice

    invoice = Invoice(
        id=invoice_id,
        invoice_html=invoice_html,
        mc_html=mc_html,
        items=items,
        prescriptions=prescriptions,
        visit_type=VisitType.TELECONSULT,
        account_id=teleconsult.account_id,
        amount=invoice_dict['total'],
        hide_invoice=hide_invoice,
        sgimed_last_edited=invoice_dict['last_edited']
    )
    teleconsult.invoices.append(invoice)

    # This fields may have changed in SGiMed, so update them
    teleconsult.total = invoice_dict['total']
    teleconsult.payment_breakdown = [
        { "title": row['item_name'], "amount": row['amount'] }
        for row in invoice_dict['invoice_items']
    ] + [{ "title": f"GST ({invoice_dict['tax_rate']}%)", "amount": invoice_dict['tax_amt'] }]

    # Submit Yuu Transaction
    if teleconsult.corporate_code == 'YUU':
        submit_yuu_transaction(db, teleconsult, invoice_dict)

    paid_amt = round(sum([p.payment_amount for p in teleconsult.get_successful_payments()]), 2)
    if invoice_dict['patient_outstanding'] > paid_amt:
        teleconsult.balance = round(invoice_dict['patient_outstanding'] - paid_amt, 2)
        teleconsult.status = TeleconsultStatus.OUTSTANDING
        teleconsult.queue_status = "Please make payment"
        db.commit()

        if all(t.status in [TeleconsultStatus.OUTSTANDING, TeleconsultStatus.CHECKED_OUT] for t in get_grouped_teleconsults(db, teleconsult)):
            user = fetch_notification_account(db, teleconsult)
            if user:
                send_patient_notification(
                    user,
                    "Virtual Consultation",
                    "Prescription updated. Please make payment to receive medications and MC (if any)",
                    { 
                        "pathname": '/teleconsult/consultation',
                        "params": { "id": str(teleconsult.id) } 
                    }
                )
        
        update_queue_instructions(visit_id, teleconsult.status.value)
    else:
        teleconsult.complete(db)
        teleconsult_delivery_object_handler(teleconsult, db)
        # Update SGiMed Status
        update_payments(teleconsult.invoices[0].id, teleconsult)
        has_medication = any([item['item_type'] == SGIMED_MEDICATION_ITEM_TYPE for item in teleconsult.invoices[0].items])
        instruction = TeleconsultStatus.DISPENSE_MEDICATION if has_medication else teleconsult.status
        update_queue_instructions(visit_id, instruction.value)

        # 3. Send notification to user that the invoice is ready for viewing
        if all(t.status == TeleconsultStatus.CHECKED_OUT for t in get_grouped_teleconsults(db, teleconsult)):
            user = fetch_notification_account(db, teleconsult)
            if user:
                send_patient_notification(
                    user,
                    "Virtual Consultation",
                    "Prescription & Documents Updated",
                    { 
                        "pathname": '/teleconsult/consultation',
                        "params": { "id": str(teleconsult.id) } 
                    }
                )

    db.close()
