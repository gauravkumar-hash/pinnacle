import logging
from sqlalchemy.orm import Session
from models import YuuTransactionLog
from utils.integrations.yuu_client import yuu_client
from dateutil.relativedelta import relativedelta
from utils import sg_datetime
from services.yuu import generate_yuu_refunds_csv_data, upload_s3

def retry_failed_transactions(db: Session):
    records = db.query(YuuTransactionLog).filter(
        YuuTransactionLog.transaction_id != "invalid",
        YuuTransactionLog.success == False,
    ).all()
    
    for row in records:
        try:
            yuu_client.send_transaction_log(row.yuu_payload)
            row.success = True
            db.commit()
        except Exception as e:
            logging.error(f"Scheduler: Error retrying transaction to Yuu: {e}")

def send_yuu_transacion_refunds(db: Session):
    print(f"Scheduler: Running to send yuu transaction refunds for {sg_datetime.now()}")
    # Generate CSV for previous month
    end_date = (sg_datetime.now() + relativedelta(days=-1, hours=12)).date()
    year = end_date.year
    month = end_date.month

    filename, csv_data = generate_yuu_refunds_csv_data(db, year, month)    
    upload_s3(filename, csv_data.getvalue())
