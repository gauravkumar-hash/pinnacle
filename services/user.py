from models.patient import Account
from models.pinnacle import StAndrew
from sqlalchemy.orm import Session
from datetime import timedelta
from datetime import datetime as sg_datetime
import logging

def is_test_user(user: Account):
    return user.mobile_number in ['81611147', '89998107', '89992001']

def user_is_pcp(db: Session, nric: str):
    '''
    1. If user does not exist in sa_database
    1. Check status terminated and terminated date has passed, return False
    2. Check if start_pcp and end_pcp is within the current date
        - start_pcp, end_pcp same date, return True
        - start_pcp + 1 day, end_pcp + 1 day, return False
    '''
    # 1. If user does not exist in sa_database
    # results = supabase.table(SA_TABLE).select('*').eq('nric', nric).limit(1).execute()
    record = db.query(StAndrew).filter(StAndrew.nric == nric).first()
    print(f"Finding Record: {nric} {record}")
    if not record:
        return False

    # Date Format String
    date_format = '%d/%m/%Y'
    # date_format = "%Y-%m-%d %H:%M:%S" # Weird formatting in staging env

    # 2. Check status terminated, and current date is past date terminated, return False
    if record.status == 'TERMINATED':
        # Convert dd/mm/yyyy string to datetime + 1 day and compare if past current time
        try:
            if not record.termination_date:
                logging.error(f"Termination date not found for record: {nric}")    
                return False
            termination_date = sg_datetime.strptime(record.termination_date, date_format) + timedelta(days=1)
        except Exception as e:
            logging.error(f"Error in parsing termination date: {e}")
            return False

        # If current time is past termination date, return False
        if termination_date < sg_datetime.now():
            return False
    
    # 3. Check if start_pcp and end_pcp is within the current date
    try:
        if not record.pcp_start or not record.pcp_end:
            logging.error(f"PCP dates not found for record: {nric}")
            return False

        start_pcp = sg_datetime.strptime(record.pcp_start, date_format)
        end_pcp = sg_datetime.strptime(record.pcp_end, date_format) + timedelta(days=1)
    except Exception as e:
        logging.error(f"Error in parsing PCP dates: {e}")
        return False

    if start_pcp < sg_datetime.now() < end_pcp:
        return True

    return False
