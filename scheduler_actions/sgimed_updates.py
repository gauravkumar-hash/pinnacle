from datetime import timedelta
import logging
from sqlalchemy import or_
from models.corporate import CorpAuthorisation, CorporateAuth, CorporateUser
from models.document import Document, DocumentTypeSGiMed
from models.model_enums import CollectionMethod, DocumentType, DocumentStatus, TeleconsultStatus
from models.delivery import DeliveryStatus
from routers.delivery.actions.delivery import get_delivery_date, teleconsult_delivery_object_handler
from models.patient import Account, YuuTransactionLog
from models.payments import Invoice
from models.sgimed import SGiMedInvoiceRefund
from models.teleconsult import Teleconsult
from models.walkin import WalkInQueue
from routers.patient.actions.teleconsult_flow_backend import teleconsult_invoice_billed_webhook
from utils import sg_datetime
from utils.integrations.sgimed import check_mc_exists, compare_patient, fetch_invoice_details, get_document_updates, get_mc_updates, get_patient_data, get_patient_profile_updates, get_queue_updates, update_payments, update_queue_instructions
from sqlalchemy.orm import Session
from datetime import datetime
from utils.integrations.sgimed_documents import SGiMedDocument, SGiMedInvoice, SGiMedInvoiceStatus, SGiMedMC
from utils.notifications import send_patient_notification
from .common import CronLogAPI, load_cron_log

def update_patient_profiles_cron(db: Session):
    cron_log = load_cron_log(db, 'patient_profiles_cron')
    modified_since = cron_log.last_modified
    data = get_patient_profile_updates(modified_since)

    print(f"Patient Cron: {len(data)} records")
    last_edited = None
    for row in data:
        last_edited = row['last_edited']
        sgimed_patient_id = row['id']
        nric = row['nric']
        patient = db.query(Account).filter(Account.nric == nric).first()
        if not patient:
            logging.info(f"Patient Cron: Patient {nric} not found on app, skipping.")
            continue
        
        diff_dict = compare_patient(patient, sgimed_patient_id)
        if diff_dict:
            try:
                orig_data = { k: v for k, v in patient.as_dict().items() if k in diff_dict }
                print(f"Patient Cron Update: {patient.id}: Changes: {diff_dict}, Original: {orig_data}")
                patient.update_vars(diff_dict)
                patient.reset_diff()
                patient.update_auth_code()
                db.commit()
            except Exception as e:
                logging.error(f"Patient Cron: Failed update SGiMed: {sgimed_patient_id} {nric}, Diff: {diff_dict}. Error: {str(e)}")
                db.rollback()

    if last_edited:
        print(f"Patient Cron: Last Edited: {last_edited}")
        cron_log.last_modified = datetime.strptime(last_edited, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=1)
        db.commit()

def update_documents_cron(db: Session):
    cron = CronLogAPI(db, 'documents_cron', '/document')
    if len(cron.data) == 0:
        return []

    data = cron.data
    print(f"Document Cron: {len(data)} records")
    data = [SGiMedDocument(**row) for row in data]
    update_files_into_documents(db, data)
    cron.commit()

def check_for_refunds(db: Session, invoice_dict: dict):
    '''
    Track refunds for invoices
    '''
    invoice_id = invoice_dict['id']
    invoice_payments = [ row for row in invoice_dict['invoice_payments'] if row['total'] < 0]
    if invoice_payments:
        refund_record = db.query(SGiMedInvoiceRefund).filter(SGiMedInvoiceRefund.sgimed_invoice_id == invoice_id).first()
        refund_amount = -1 * sum([row['total'] for row in invoice_payments])
        include_delivery_charges = any(['delivery' in row['remark'].lower() for item in invoice_payments for row in item['invoice_payment_items']])
        data = {
            "sgimed_invoice_id": invoice_id,
            "refund_amount": refund_amount,
            "include_delivery_charges": include_delivery_charges,
        }
        if refund_record:
            refund_record.update_vars(data)
        else:
            refund_record = SGiMedInvoiceRefund(
                invoice_date=invoice_dict['issued_date'],
                sgimed_invoice_payment_items=invoice_payments,
                **data
            )
            db.add(refund_record)
        db.commit()

        # Handle Yuu refund tracking
        yuu_transaction = db.query(YuuTransactionLog).filter(
            YuuTransactionLog.sgimed_invoice_id == invoice_dict['id']
        ).first()
        if yuu_transaction:
            _invoice_dict = yuu_transaction.sgimed_invoice_dict
            # Compute delivery charges from original invoice
            delivery_charges = sum([
                item['amount'] for item in _invoice_dict.get('invoice_items', [])
                if 'delivery' in item.get('item_name', '').lower()
            ])

            # Update Yuu transaction with refund details
            net_refund = refund_amount - delivery_charges if refund_record.include_delivery_charges else refund_amount
            yuu_transaction.refund_details = {
                "sgimed_invoice_id": _invoice_dict['id'],
                "refund_amount": round(net_refund, 2),
                "refunded_at": refund_record.created_at.isoformat()
            }
            db.commit()

def update_invoices_cron(db: Session) -> list[str]:
    cron = CronLogAPI(db, 'invoice_cron', '/invoice')
    if len(cron.data) == 0:
        return []

    # Includes draft and void
    invalid_data = [row['id'] for row in cron.data if not row['patient'] or not row['visit']]
    # TOOD: Review if this happens often. What happens is if a company is added and invoice is automatically voided, visit gets dropped
    if invalid_data:
        logging.error(f"Invoice Cron: Invalid invoice ids {invalid_data}")

    data = [row for row in cron.data if row['patient'] and row['visit']]
    data = [SGiMedInvoice(**row) for row in data]
    update_invoices_into_documents(db, data)
    # Remove draft and void invoices
    filtered_data = [row for row in data if row.status not in [SGiMedInvoiceStatus.DRAFT, SGiMedInvoiceStatus.VOID]]
    if not filtered_data:
        cron.commit()
        return []

    data = filtered_data
    # Fetch visit ids, and relevant Teleconsult and WalkinQueue records
    invoice_dict: dict[str, SGiMedInvoice] = { x.id: x for x in data }
    invoice_ids = list(invoice_dict.keys())
    invoices = db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()
    logging.info(f"Invoice Cron. Invoice IDs: {len(invoice_ids)}, Invoices: {len(invoices)}. Modified Since: {cron.cron_log.last_modified}, Last Page: {cron.cron_log.last_page}")

    # For missing invoices, call the finalise invoice webhook
    missing_invoices = set(invoice_ids) - set([str(invoice.id) for invoice in invoices])
    logging.info(f"Invoice Cron. Missing Invoices Cron: {len(missing_invoices)}. Modified Since: {cron.cron_log.last_modified}, Last Page: {cron.cron_log.last_page}")

    processed_missing_invoices = []
    for invoice_id in missing_invoices:
        # Skip any records that are not linked to Teleconsult
        teleconsult_id = db.query(Teleconsult.id).filter(Teleconsult.sgimed_visit_id == invoice_dict[invoice_id].visit.id).first()
        if not teleconsult_id:
            print("Skipping as not linked to Teleconsult record")
            continue
        print(f"Invoice Cron: Invoice, Fetching {invoice_dict[invoice_id].visit.id}")
        invoice_details = fetch_invoice_details(invoice_id)
        if invoice_details:
            check_for_refunds(db, invoice_details.invoice_dict)
            details = invoice_details.model_dump()
            teleconsult_invoice_billed_webhook(**details)
        processed_missing_invoices.append(invoice_id)

    invoice_ids_processed = []
    for invoice in invoices:
        # Skip any records that are not linked to Teleconsult and Walkin
        teleconsult_id = db.query(Teleconsult.id).filter(Teleconsult.sgimed_visit_id == invoice_dict[invoice.id].visit.id).first()
        if not teleconsult_id:
            walkin_id = db.query(WalkInQueue.id).filter(WalkInQueue.sgimed_visit_id == invoice_dict[invoice.id].visit.id).first()
            if not walkin_id:
                print(f"Invoice Cron: Visit ID: {invoice_dict[invoice.id].visit.id} skipped as not linked to Teleconsult or Walkin record")
                continue
        if invoice.id in processed_missing_invoices:
            print(f"Invoice Cron: {invoice.id} processed from missing invoices")
            continue
        if invoice.sgimed_last_edited == invoice_dict[str(invoice.id)].last_edited:
            logging.info(f"Invoice {invoice.id} has no changes")
            continue

        print(f"Invoice Cron: Invoice, Fetching {invoice_dict[invoice.id].visit.id}")
        invoice_details = fetch_invoice_details(str(invoice.id))
        if not invoice_details:
            logging.error(f"Failed to fetch invoice details for {invoice.id}")
            continue
        check_for_refunds(db, invoice_details.invoice_dict)
        invoice.invoice_html = invoice_details.invoice_html
        invoice.mc_html = invoice_details.mc_html
        invoice.items = invoice_details.items
        invoice.prescriptions = invoice_details.prescriptions
        invoice.amount = invoice_details.invoice_dict['total']
        invoice.sgimed_last_edited = invoice_details.invoice_dict['last_edited']
        
        # Updating Teleconsult Logic
        if invoice.teleconsults:
            teleconsult = invoice.teleconsults[0]
            # Update total and balance if changed on invoice
            teleconsult.total = invoice_details.invoice_dict['total']
            paid_amt = round(sum([p.payment_amount for p in teleconsult.get_successful_payments()]), 2)
            if invoice_details.invoice_dict['patient_outstanding'] > paid_amt:
                teleconsult.balance = invoice_details.invoice_dict['patient_outstanding'] - paid_amt
            else:
                teleconsult.balance = 0.0

            # Updating to checked out if patient_outstanding is $0
            if teleconsult.balance == 0 and teleconsult.status == TeleconsultStatus.OUTSTANDING:
                teleconsult.complete(db)
                teleconsult_delivery_object_handler(teleconsult, db)
                if teleconsult.sgimed_visit_id:
                    # Send payment information to SGiMed when transitioning from OUTSTANDING to CHECKED_OUT
                    update_payments(teleconsult.invoices[0].id, teleconsult)
                    update_queue_instructions(teleconsult.sgimed_visit_id, teleconsult.status.value)
                else:
                    logging.error(f"Teleconsult {teleconsult.id} has no sgimed_visit_id")

        invoice_ids_processed.append(str(invoice.id))
        db.commit()

    cron.commit()
    # Log visit_ids updated. Those visit_ids that overlap with MC updates can be safely ignored
    return [invoice_dict[invoice_id].visit.id for invoice_id in invoice_ids_processed]

def update_mcs_cron(db: Session, visit_ids_processed: list[str]):
    '''
    This endpoint will have order_item_id when MC is added, edited, or voided. When MC is edited, invoice does not trigger a change.
    '''
    cron_log = load_cron_log(db, 'mc_cron')
    modified_since = cron_log.last_modified
    data = get_mc_updates(modified_since, include_void=True)
    # Inclusive of voided MCs
    data = [SGiMedMC(**row) for row in data]
    update_mcs_into_documents(db, data)
    
    # Remove voided MCs
    data = [row for row in data if not row.is_void]
    prev_data_len = len(data)
    data = [x for x in data if x.visit.id not in visit_ids_processed]
    print(f"MC Cron. Data: {prev_data_len}, Filtered data: {len(data)}")
    if not data:
        print("MC Cron: No data to process")
        return
    
    # Fetch visit ids, and relevant Teleconsult and WalkinQueue records
    order_item_ids = { x.visit.id: x.id for x in data }
    visit_ids = list(order_item_ids.keys())
    teleconsults = db.query(Teleconsult).filter(Teleconsult.sgimed_visit_id.in_(visit_ids)).all()
    walkins = db.query(WalkInQueue).filter(WalkInQueue.sgimed_visit_id.in_(visit_ids)).all()
    logging.info(f"MC Cron. Visit IDs: {len(visit_ids)}, Teleconsults: {len(teleconsults)}, Walkins: {len(walkins)}")
    
    # Update Teleconsult Records for MC
    for teleconsult in teleconsults:
        if not teleconsult.invoices:
            logging.warning(f"Teleconsult {teleconsult.id} has no invoices to update MC")
            continue
        if teleconsult.sgimed_visit_id:
            teleconsult.invoices[0].mc_html = order_item_ids[teleconsult.sgimed_visit_id]
    db.commit()
    
    # Update Walkin Records for MC
    for walkin in walkins:
        if not walkin.invoices:
            logging.warning(f"Queue Request {walkin.id} has no invoices to update MC")
            continue
        if walkin.sgimed_visit_id:
            walkin.invoices[0].mc_html = order_item_ids[walkin.sgimed_visit_id]
    db.commit()

    if data and data[-1].last_edited:
        last_edited = data[-1].last_edited
        cron_log.last_modified = last_edited + timedelta(seconds=1)
        print(f"MC Cron: Last Edited: {cron_log.last_modified}")
        db.commit()

def validate_access(db: Session, user: Account):
    # Check if user belongs to any corporate user
    corp_codes = db.query(CorporateUser.code).filter(CorporateUser.ic_type == user.ic_type, CorporateUser.nric == user.nric).all()
    corp_codes = [row[0] for row in corp_codes]    
    if not corp_codes:
        return
    
    # Check if user has permission to access eDocs
    exists = db.query(CorporateAuth.id).filter(
            CorporateAuth.code.in_(corp_codes), 
            CorporateAuth.permission == CorpAuthorisation.BLOCK_EDOCS
        ).first()
    return bool(exists)

def send_document_notification(db: Session, doc: Document):
    if doc.hidden or doc.notification_sent:
        return
    
    user = db.query(Account).filter(Account.sgimed_patient_id == doc.sgimed_patient_id).first()
    if not user:
        return

    # User does not have access to entire eDocs module    
    if not validate_access(db, user):
        return
    
    # Check if record exists for Teleconsult or WalkInQueue and do not send notification as those are handled separately
    if doc.document_type in [DocumentType.INVOICE, DocumentType.MC]:    
        record = db.query(Teleconsult).filter(Teleconsult.sgimed_visit_id == doc.sgimed_visit_id).first()
        if record:
            return
        record = db.query(WalkInQueue).filter(WalkInQueue.sgimed_visit_id == doc.sgimed_visit_id).first()
        if record:
            return

    send_patient_notification(
        user,
        f"{doc.document_type.value} Uploaded",
        "View your document (My Records)",
        # { 
        #     "pathname": f'/record/document',
        #     "params": { "id": str(doc.id) } 
        # }
    )
    doc.notification_sent = True
    db.commit()

# Update Functions into patient_documents table
def update_files_into_documents(db: Session, data: list[SGiMedDocument]):
    doc_types = db.query(DocumentTypeSGiMed).all()
    doc_type_dict = { dtype.sgimed_document_type_id: dtype.id for dtype in doc_types }

    for row in data:
        if row.document_type.id not in doc_type_dict:
            continue

        update_dict = {
            "sgimed_patient_id": row.patient.id,
            "sgimed_document_id": row.id,
            "sgimed_branch_id": row.branch_id,
            "sgimed_visit_id": row.visit.id if row.visit else None,
            "name": row.name,
            "document_date": row.document_date,
            "remarks": row.remark,
            "document_type": doc_type_dict[row.document_type.id],
            "created_at": row.created_at,
            "updated_at": row.last_edited if row.last_edited else row.created_at,
        }
        # Check if doc exists
        doc = db.query(Document).filter_by(sgimed_document_id=row.id).first()
        if doc:
            doc.update_vars(update_dict)
        else:
            doc = Document(**update_dict)
            db.add(doc)

        try:
            db.commit()
        except Exception as e:
            logging.error(f"Document Cron ID {row.id}: {str(e)}", exc_info=True)
            db.rollback()

        send_document_notification(db, doc)

def update_invoices_into_documents(db: Session, data: list[SGiMedInvoice]):
    # Update into patient_documents table
    for row in data:
        # Hide all invoices with discount eg 100%, 80% or co pay basis
        sgimed_invoice_status_mapping = {
            SGiMedInvoiceStatus.VOID: DocumentStatus.VOID,
            SGiMedInvoiceStatus.DRAFT: DocumentStatus.DRAFT,
            SGiMedInvoiceStatus.BILL: DocumentStatus.PENDING,
            SGiMedInvoiceStatus.PARTIAL_PAID: DocumentStatus.PENDING,
            SGiMedInvoiceStatus.PAID: DocumentStatus.COMPLETE,
        }
        status = sgimed_invoice_status_mapping.get(row.status, None)
        # Pending state to commplete based on patient_outstanding
        if status == DocumentStatus.PENDING and row.patient_outstanding <= 0:
            status = DocumentStatus.COMPLETE
        hidden = status in [DocumentStatus.DRAFT, DocumentStatus.VOID] or bool(row.total <= 0 or row.discount > 0)
        remarks = f"${row.total:.2f}"

        # Logic check to unhide any other documents
        # Show MC once payment is paid
        if status == DocumentStatus.COMPLETE:
            mcs = db.query(Document).filter(
                    Document.document_type == DocumentType.MC,
                    Document.sgimed_visit_id == row.visit.id,
                    # None is required to be check for Null
                    or_(Document.status == None, Document.status != DocumentStatus.VOID)
                ).all()
            for mc in mcs:
                # If invoice is in draft and MC is deleted, MC is not triggered by SGiMed thus the check required if MC still exists
                if not check_mc_exists(mc.sgimed_document_id):
                    mc.hidden = True
                    mc.status = DocumentStatus.VOID
                    mc.remarks = "MC not found in SGiMed"
                    db.commit()
                    continue

                mc.hidden = False
                mc.status = None
                db.commit()
                send_document_notification(db, mc)

        update_dict = {
            "sgimed_patient_id": row.patient.id,
            "sgimed_document_id": row.id,
            "sgimed_branch_id": row.branch_id,
            "sgimed_visit_id": row.visit.id,
            "status": status,
            "name": "Invoice",
            "hidden": hidden,
            "document_date": row.issued_date,
            "remarks": remarks,
            "document_type": DocumentType.INVOICE,
            "created_at": row.created_at,
            "updated_at": row.last_edited if row.last_edited else row.created_at,
        }
        doc = db.query(Document).filter_by(sgimed_document_id=row.id).first()
        if doc:
            doc.update_vars(update_dict)
        else:
            doc = Document(**update_dict)
            db.add(doc)
            
        try:
            db.commit()
        except Exception as e:
            logging.error(f"Invoice patient_documents Documents ID {row.id}: {e}", exc_info=True)
            db.rollback()
            
        send_document_notification(db, doc)

def update_mcs_into_documents(db: Session, data: list[SGiMedMC]):
    # Update into patient_documents table
    for row in data:
        # Hide record if it is voided
        if row.is_void:
            record = db.query(Document).filter(Document.sgimed_document_id == row.id).first()
            if record:
                record.hidden = True
                record.status = DocumentStatus.VOID
                db.commit()
            continue
        
        # Check if invoice is paid
        invoice = db.query(Document.id).filter(
                Document.sgimed_visit_id == row.visit.id,
                Document.document_type == DocumentType.INVOICE,
                Document.status == DocumentStatus.COMPLETE,
            ).first()
        hidden = invoice is None
        # Create or Update Document
        update_dict = {
            "sgimed_patient_id": row.patient.id,
            "sgimed_document_id": row.id,
            "sgimed_branch_id": row.branch_id,
            "sgimed_visit_id": row.visit.id,
            "name": "Medical Certificate (MC)",
            "hidden": hidden,
            "document_date": row.created_at.date(),
            "document_type": DocumentType.MC,
            "created_at": row.created_at,
            "updated_at": row.last_edited if row.last_edited else row.created_at
        }
        doc = db.query(Document).filter_by(sgimed_document_id=row.id).first()
        if doc:
            doc.update_vars(update_dict)
        else:
            doc = Document(**update_dict)
            db.add(doc)
    
        try:
            db.commit()
        except Exception as e:
            logging.error(f"MC patient_documents Documents ID {row.id}: {e}", exc_info=True)
            db.rollback()

        send_document_notification(db, doc)

def update_delivery_method_cron(db: Session):
    crons = [
        CronLogAPI(db, f'delivery_day{i}_cron', '/queue', date=(sg_datetime.now() - timedelta(days=i)).date())
        for i in range(0, 3)    
    ]

    for cron in crons:
        queues = cron.data
        if queues:
            delivery_to_pickup_handler(db, queues)
            pickup_to_delivery_handler(db, queues)
        
        # Commit the updated time even if there are no queues to process
        cron.commit()

def delivery_to_pickup_handler(db: Session, queues: list):
    filtered_queues = [
        queue for queue in queues
        if queue['appointment_type']['name'] != 'Telemed'
        and '.' in str(queue['queue_no'])
    ]
    
    visit_ids = [
        (row['id'], row['queue_no'])
        for row in filtered_queues
    ]
    
    for visit_id, queue_no in visit_ids:
        teleconsult = db.query(Teleconsult).filter(Teleconsult.sgimed_visit_id == visit_id).first()
        if teleconsult:
            logging.info(f"Delivery Cron. Visit IDs: {visit_id}, Teleconsult ID: {teleconsult.id} change delivery method to pickup")
            teleconsult.queue_number = queue_no
            teleconsult.collection_method = CollectionMethod.PICKUP
            
            if teleconsult.teleconsult_delivery:
                teleconsult.teleconsult_delivery.status = DeliveryStatus.CANCELLED
            db.commit()
        else:
            logging.info(f"No teleconsult found for visit_id: {visit_id}")

def pickup_to_delivery_handler(db: Session, queues: list):
    filtered_queues = [
        queue for queue in queues
        if queue['appointment_type']['name'] == 'Telemed'
        and '.' in str(queue['queue_no'])
    ]
    
    visit_ids = [
        (row['id'], row['queue_no'])
        for row in filtered_queues
    ]
    
    for visit_id, queue_no in visit_ids:
        teleconsult = db.query(Teleconsult).filter(Teleconsult.sgimed_visit_id == visit_id).first()
        if not teleconsult:
            continue

        logging.info(f"Delivery Cron. Visit IDs: {visit_id}, Teleconsult ID: {teleconsult.id} change pickup method to delivery")
        teleconsult.queue_number = queue_no
        teleconsult.collection_method = CollectionMethod.DELIVERY
        
        if teleconsult.teleconsult_delivery and teleconsult.teleconsult_delivery.status == DeliveryStatus.CANCELLED:
            teleconsult.teleconsult_delivery.status = DeliveryStatus.RETRY
            teleconsult.teleconsult_delivery.delivery_date = get_delivery_date(db)
        db.commit()
        
        if not teleconsult.teleconsult_delivery:
            logging.info(f"Delivery Cron. Visit IDs: {visit_id}, Teleconsult ID: {teleconsult.id} create delivery object")
            teleconsult_delivery_object_handler(teleconsult, db)
