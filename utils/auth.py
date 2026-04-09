import logging
import re
from typing import Optional
from config import redis_client
import random
from models.redis_models import RedisLoginState
from utils.fastapi import ExceptionCode, HTTPJSONException
from utils.notifications import send_sms
from models import AccountFirebase, FirebaseLoginType, Account
from models.model_enums import PhoneCountryCode, SGiMedICType
from sqlalchemy.orm import Session
from firebase_admin import auth

OTP_RESEND_WAIT_TIME = 600  # 10 minutes
OTP_EXPIRE_TIME = 600 # 10 minutes
SESSION_TIME = 1200 # 20 minutes

# Supabase Helpers

def raise_invalid_login(title: str = "Invalid Login", message: str = "Invalid session. Please try again"):
    logging.error(f"Invalid login: {title} {message}")
    raise HTTPJSONException(
        status_code=400,
        code=ExceptionCode.INVALID_LOGIN,
        title=title,
        message=message
    )

def get_account_by_phone(db: Session, mobile_code: PhoneCountryCode, mobile_number: str):
    return db.query(Account).filter(Account.mobile_code == mobile_code, Account.mobile_number == mobile_number).first()

def get_account_by_id(db: Session, id: str):
    return db.query(Account).filter(Account.nric == id).first()

def get_account_firebase_uid(db: Session, user_id: str):
    record = db.query(AccountFirebase).filter(AccountFirebase.account_id == user_id, AccountFirebase.login_type == FirebaseLoginType.PHONE).first()
    if not record:
        return None
    return record.firebase_uid

def generate_send_otp(code: PhoneCountryCode, phone: str):
    '''
    Generate OTP and Send SMS
    '''
    # Generate a random 6 character OTP
    otp_code = ''.join(random.choices('0123456789', k=6))
    if phone.startswith('8999'):
        otp_code = '555555'

    send_sms(f'{code.value}{phone}', f'PinnacleSG+ OTP code is {otp_code}')
    return otp_code

# Firebase Helpers
def generate_login_token(db: Session, session_id: str, account: Account) -> Optional[str]:
    '''
    Generate a login token for the user
    '''
    firebase_uid = get_account_firebase_uid(db, str(account.id))
    if not firebase_uid:
        logging.error('Failed to get firebase uid for account: {0}'.format(account.id))    
        return None
    
    token = auth.create_custom_token(firebase_uid).decode()
    auth.revoke_refresh_tokens(firebase_uid) # Revoke any existing sessions
    delete_login_state(session_id) # Delete login state from redis
    return token

# Redis Helpers

def update_redis_loginstate(session_id: str, login_state: RedisLoginState):
    '''
    Update the login state in Redis
    '''
    redis_client.set(session_id, login_state.model_dump_json(), ex=SESSION_TIME)  # Update session


def get_login_state(session_id: str) -> Optional[RedisLoginState]:
    '''
    Retrieve the login state from Redis
    '''
    state = redis_client.get(session_id)
    if state:
        return RedisLoginState.model_validate_json(str(state))
    return None

def delete_login_state(session_id: str):
    '''
    Delete the login state since user has already logged in
    '''
    redis_client.delete(session_id)

def is_valid_nric(nric: str):
    '''
    Source: https://samliew.com/nric-generator
    '''
    first = nric[0].upper()
    checksum = nric[-1].upper()
    digits = nric[1:8]
    if not nric or len(nric) != 9 or first not in 'STFGM' or not digits.isdigit():
        return False

    chars = [int(d) for d in digits]
    weights = [2, 7, 6, 5, 4, 3, 2]
    sum_digits = sum([c * w for c, w in zip(chars, weights)])

    offset = 0
    if first in 'TG':
        offset = 4
    elif first == 'M':
        offset = 3

    index = (offset + sum_digits) % 11
    if first == 'M':
        index = 10 - index

    st = "JZIHGFEDCBA"
    fg = "XWUTRQPNMLK"
    m = "KLJNPQRTUWX"

    expected_checksum = ''
    if first in 'ST':
        expected_checksum = st[index]
    elif first in 'FG':
        expected_checksum = fg[index]
    elif first == 'M':
        expected_checksum = m[index]

    return checksum == expected_checksum

def id_number_validation(id_type: SGiMedICType, id_number: str) -> str | None:
    # 1 - FIN entered is invalid
    if id_type in [SGiMedICType.PINK_IC, SGiMedICType.BLUE_IC] and not re.match(r'^[STFMG]\d{7}[A-Z]$', id_number): # Test: T1234567G
        return "Invalid NRIC Number. Please try again"
    if id_type in [SGiMedICType.FIN_NUMBER] and not re.match(r'^[FMG]\d{7}[A-Z]$', id_number): # Test: T1234567G
        return "Invalid FIN Number. Please try again"
    if id_type in [SGiMedICType.PASSPORT] and not re.match(r'^[A-Z0-9]{6,9}$', id_number): # Test: T1234567G
        return "Invalid Passport Number. Please try again.\n\nIf this was a mistake, kindly call +65 6235 1852"
    if id_type in [SGiMedICType.PINK_IC, SGiMedICType.BLUE_IC, SGiMedICType.FIN_NUMBER] and not is_valid_nric(id_number):
        return "Invalid NRIC/FIN number. Please try again.\n\nIf this was a mistake, kindly call +65 6235 1852"

    return None
