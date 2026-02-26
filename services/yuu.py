import logging
import boto3
from io import StringIO
import csv
from sqlalchemy.orm import Session
from sqlalchemy import extract
from models import Teleconsult, Appointment
from models.appointment import AppointmentServiceGroup
from models.patient import AccountYuuLink, YuuTransactionLog
from utils import sg_datetime
from pydantic import BaseModel
from utils.integrations.yuu_client import yuu_client
from config import (
    YUU_AWS_ACCESS_KEY, YUU_AWS_SECRET_ACCESS_KEY, YUU_IAM_ROLE, YUU_S3_BUCKET, YUU_S3_PATH, YUU_SGIMED_COMPANY_ID
)

class YuuTransactionItem(BaseModel):
    itemId: str
    unitPrice: float
    quantity: int
    subtotal: float

class YuuTransactionPayment(BaseModel):
    type: str = "OTHERS"
    amount: float

class YuuTransactionPayload(BaseModel):
    storeId: str = "teleconsult"
    userId: str
    userIdType: str = "TOMO_ID"
    brandCode: str = "sg-pfc"
    type: str = "PURCHASE"
    transactionId: str
    createTime: str
    updateTime: str
    channel: str = "MOBILE"
    payments: list[YuuTransactionPayment]
    items: list[YuuTransactionItem]

def submit_yuu_appointment_transaction(db: Session, appointment: Appointment):
    # Ensure appointment is YUU, is the primary appointment, and has an invoice
    if appointment.affiliate_code != 'YUU' or (appointment.index is not None and appointment.index != 0):
        return
    if len(appointment.invoice_ids) == 0:
        logging.error(f"Appointments: No invoice found for appointment {appointment.id}")
        return
    
    # Retrieve YUU related service groups, if none related to appointment, return
    yuu_service_group_ids = db.query(AppointmentServiceGroup.id).filter(
        AppointmentServiceGroup.restricted_memberships.any("YUU"), # type: ignore
    ).all()
    yuu_service_group_ids = [str(svc[0]) for svc in yuu_service_group_ids]
    service_groups = { svc['id']: svc for svc in appointment.services if svc['id'] in yuu_service_group_ids }
    if not service_groups:
        return
    
    # Get the Yuu Tomo ID
    yuu_link = db.query(AccountYuuLink).filter(
        AccountYuuLink.account_id == appointment.created_by,
        AccountYuuLink.deleted == False
    ).first()
    if not yuu_link:
        logging.error(f"No Yuu link found for account {appointment.created_by}")
        return

    account_id = yuu_link.account_id
    tomo_id = yuu_link.tomo_id
    invoice_id = appointment.invoice_ids[0]
    total = round(sum([svc['prepayment_price'] for svc_grp in service_groups.values() for svc in svc_grp['items']]), 2)
    # Create a new transaction log
    row = YuuTransactionLog(
        account_id=account_id,
        tomo_id=tomo_id,
        sgimed_invoice_id=invoice_id,
        sgimed_invoice_dict={},
        transaction_id="",
        yuu_payload={}
    )
    db.add(row)
    db.commit()
    
    curr_time = sg_datetime.sg(row.created_at)
    # Fetch the next transaction id, by checking the previous transaction id
    prev_transaction_id = db.query(YuuTransactionLog.transaction_id) \
        .filter(
            YuuTransactionLog.created_at < row.created_at, 
            YuuTransactionLog.created_at >= curr_time.replace(hour=0, minute=0, second=0, microsecond=0),
            YuuTransactionLog.transaction_id.like("sg-pfc-%")
        ) \
        .order_by(YuuTransactionLog.created_at.desc()).first()
    curr_index = 1
    if prev_transaction_id:
        curr_index = int(prev_transaction_id[0].split('-')[-1]) + 1

    # Update the transaction id and payload if send_to_yuu is False
    curr_transaction_id = f"sg-pfc-{curr_time.strftime('%Y%m%d')}-{curr_index:06d}"
    row.transaction_id = curr_transaction_id
    row.yuu_payload = YuuTransactionPayload(
        storeId="package",
        userId=tomo_id,
        transactionId=curr_transaction_id,
        createTime=curr_time.isoformat(),
        updateTime=curr_time.isoformat(),
        payments=[YuuTransactionPayment(type="OTHERS", amount=total)],
        items=[YuuTransactionItem(itemId="package", unitPrice=total, quantity=1, subtotal=total)]
    ).model_dump()
    db.commit()

    # Send the transaction to Yuu
    try:
        yuu_client.send_transaction_log(row.yuu_payload)
        row.success = True
        db.commit()
    except Exception as e:
        logging.error(f"Error sending transaction to Yuu: {e}")

    return row

def submit_yuu_transaction(db: Session, teleconsult: Teleconsult, invoice_dict: dict, existing_log: YuuTransactionLog | None = None):
    # Check if the invoice is valid for Yuu even though corporate_code is set to YUU
    total_above_zero = float(invoice_dict['total']) > 0
    has_discount = float(invoice_dict.get('discount', 0)) > 0
    has_company = invoice_dict.get('company', None) is not None
    if has_company and 'id' in invoice_dict['company'] and invoice_dict['company']['id'] == YUU_SGIMED_COMPANY_ID:
        has_company = False

    # Logic: If total is above zero, and no discount and no company, then send to Yuu
    send_to_yuu = total_above_zero and not has_discount and not has_company

    # Get the Yuu Tomo ID
    yuu_link = db.query(AccountYuuLink).filter(
        AccountYuuLink.account_id == teleconsult.account_id,
        AccountYuuLink.deleted == False
    ).first()
    if not yuu_link:
        logging.error(f"No Yuu link found for account {teleconsult.account_id}")
        return
    tomo_id = yuu_link.tomo_id

    if existing_log:
        row = existing_log
    else:
        # Create a new transaction log
        row = YuuTransactionLog(
            account_id=teleconsult.account_id,
            tomo_id=tomo_id,
            sgimed_invoice_id=invoice_dict['id'],
            sgimed_invoice_dict=invoice_dict,
            transaction_id="",
            yuu_payload={}
        )
        db.add(row)
        db.commit()
    
    curr_time = sg_datetime.sg(row.created_at)
    
    # Fetch the next transaction id, by checking the previous transaction id
    prev_transaction_id = db.query(YuuTransactionLog.transaction_id) \
        .filter(
            YuuTransactionLog.created_at < row.created_at, 
            YuuTransactionLog.created_at >= curr_time.replace(hour=0, minute=0, second=0, microsecond=0),
            YuuTransactionLog.transaction_id.like("sg-pfc-%")
        ) \
        .order_by(YuuTransactionLog.created_at.desc()).first()
    curr_index = 1
    if prev_transaction_id:
        curr_index = int(prev_transaction_id[0].split('-')[-1]) + 1

    # Update the transaction id
    items = [row for row in invoice_dict['invoice_items'] if 'delivery' not in row['item_name'].lower()]
    teleconsult_subtotal = round(sum([row['amount'] for row in items if row['item_type'] != 'Drugs']), 2)
    medication_subtotal = round(sum([row['amount'] for row in items if row['item_type'] == 'Drugs']), 2)

    yuu_items = [YuuTransactionItem(itemId="teleconsult", unitPrice=teleconsult_subtotal, quantity=1, subtotal=teleconsult_subtotal)]
    if medication_subtotal > 0:
        yuu_items.append(YuuTransactionItem(itemId="medication", unitPrice=medication_subtotal, quantity=1, subtotal=medication_subtotal))

    # Update the transaction id and payload if send_to_yuu is False
    if not send_to_yuu:
        logging.error(f"Invoice {invoice_dict['id']} is Yuu Corporate Code but not valid for Yuu")
        row.transaction_id = "invalid"
        db.commit()
    else:
        curr_transaction_id = f"sg-pfc-{curr_time.strftime('%Y%m%d')}-{curr_index:06d}"
        row.transaction_id = curr_transaction_id
        total = round(teleconsult_subtotal + medication_subtotal, 2)
        row.yuu_payload = YuuTransactionPayload(
            userId=tomo_id,
            transactionId=curr_transaction_id,
            createTime=curr_time.isoformat(),
            updateTime=curr_time.isoformat(),
            payments=[YuuTransactionPayment(type="OTHERS", amount=total)],
            items=yuu_items
        ).model_dump()
        db.commit()

        # Send the transaction to Yuu
        try:
            yuu_client.send_transaction_log(row.yuu_payload)
            row.success = True
            db.commit()
        except Exception as e:
            logging.error(f"Error sending transaction to Yuu: {e}")

    return row

def get_yuu_s3_client():
    """
    Create a boto3 client for a service using assumed role credentials.
    Credentials are cached to avoid repeated AssumeRole calls.
    """
    service_name = 's3'
    role_session_name = 'yuu_s3'
    
    # Create STS client
    sts_client = boto3.client(
        'sts',
        aws_access_key_id=YUU_AWS_ACCESS_KEY,
        aws_secret_access_key=YUU_AWS_SECRET_ACCESS_KEY
    )
    
    # Assume role
    assumed_role = sts_client.assume_role(
        RoleArn=YUU_IAM_ROLE,
        RoleSessionName=role_session_name
    )
    
    # Create and return client with temporary credentials
    temp_creds = assumed_role['Credentials']
    return boto3.client(
        service_name,
        aws_access_key_id=temp_creds['AccessKeyId'],
        aws_secret_access_key=temp_creds['SecretAccessKey'],
        aws_session_token=temp_creds['SessionToken']
    )

def list_s3():
    s3_client = get_yuu_s3_client()
    response= s3_client.list_objects(Bucket=YUU_S3_BUCKET, Prefix=YUU_S3_PATH)
    return [bucket['Key'] for bucket in response['Contents']]

def download_s3(s3_key: str, local_key: str):
    s3_client = get_yuu_s3_client()
    response = s3_client.download_file(
        Bucket=YUU_S3_BUCKET, 
        Key=YUU_S3_PATH + s3_key,
        Filename=local_key
    )

def upload_s3(s3_fname: str, body: str):
    try:
        s3_client = get_yuu_s3_client()
        response = s3_client.put_object(
            Body=body,
            Bucket=YUU_S3_BUCKET,
            Key=YUU_S3_PATH + s3_fname,
            ContentType='text/csv',
        )
        print(response)
    except Exception:
        logging.error('Failed to upload to yuu s3', exc_info=True)

def delete_s3(s3_key: str):
    s3_client = get_yuu_s3_client()
    response = s3_client.delete_object(
        Bucket=YUU_S3_BUCKET,
        Key=YUU_S3_PATH + s3_key
    )
    print(response)

def generate_yuu_refunds_csv_data(db: Session, year: int, month: int):
    """
    Generate CSV data for Yuu refunds.
    Returns (filename, csv_data, transaction_records) tuple.
    """
    # Query transactions with refunds for the month
    transactions = db.query(YuuTransactionLog).filter(
        YuuTransactionLog.refund_details.isnot(None),
        YuuTransactionLog.success == True,
        extract('year', YuuTransactionLog.created_at) == year,
        extract('month', YuuTransactionLog.created_at) == month
    ).all()
    
    filename = f"sg-pfc-refund-{year:04d}{month:02d}.csv"
    csv_data = []
    
    for transaction in transactions:
        refund = transaction.refund_details
        if not refund or 'refund_amount' not in refund:
            raise Exception(f"No refund details or refund_amount for transaction {transaction.transaction_id}")
        csv_data.append({
            'brand_transaction_id': transaction.transaction_id,
            'refund_amount': f"{refund['refund_amount']:.2f}",
            'tomo_id': transaction.tomo_id,
            'date': transaction.created_at.strftime('%Y-%m-%d')
        })
    
    csv_stream = _generate_csv_stream(csv_data, ['brand_transaction_id', 'refund_amount', 'tomo_id', 'date'])
    return filename, csv_stream

def _generate_csv_stream(csv_data: list[dict], headers: list[str]):
    """Helper to generate CSV stream for download"""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(csv_data)
    output.seek(0)
    return output
