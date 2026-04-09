from datetime import date, datetime
import logging
import re
import time
from typing import Optional
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import or_
from models.patient import Account
from models.redis_models import RedisAuthState, RedisLoginState
from models.teleconsult import Teleconsult
from routers.patient.auth import LoginResponse
from routers.patient.utils import validate_firebase_token, validate_user
from models.model_enums import PhoneCountryCode, SGiMedGender, SGiMedICType, SGiMedLanguage, SGiMedNationality, TeleconsultStatus
from models import get_db, AccountFirebase, get_user
from services.appointment import get_appointment_constants
from utils.auth import OTP_EXPIRE_TIME, OTP_RESEND_WAIT_TIME, delete_login_state, generate_send_otp, get_account_by_phone, get_login_state, update_redis_loginstate
from utils.fastapi import ExceptionCode, HTTPJSONException
from utils.integrations.sgimed import upsert_patient_in_sgimed
from utils.stripe import fetch_customer_sheet
from utils import sg_datetime
from firebase_admin import auth
from sqlalchemy.orm import Session
from routers.realtime import ws_manager, WSMessage, WSEvent
from utils.system_config import is_test_user

router = APIRouter(dependencies=[Depends(validate_firebase_token)])

class FeatureFlagResp(BaseModel):
    flags: list[str] = []

@router.get('feature_flags', response_model=FeatureFlagResp)
def get_feature_flags(user = Depends(validate_user), db: Session = Depends(get_db)):
    feature_flags = ['appointment']
    # if is_test_user(db, user):
    #     feature_flags.append('xxx')

    return FeatureFlagResp(
        flags=feature_flags
    )

class UpdateTokenParams(BaseModel):
    token: str
    device: Optional[str] = None

class SuccessResponse(BaseModel):
    success: bool

# NOTE: This does not affect test user implementation since it uses firebase uid prior to loading user
def update_device_token(db: Session, firebase_uid: str, expo_token: Optional[str] = None, fcm_token: Optional[str] = None, apn_token: Optional[str] = None, device: Optional[str] = None):
    record = db.query(AccountFirebase).filter(AccountFirebase.firebase_uid == firebase_uid).first()
    if not record:
        logging.error(f"Firebase UID not found in AccountFirebase: {firebase_uid}")
        raise HTTPException(status_code=403, detail="Invalid user")
    
    if not record:
        logging.error(f"Firebase UID not found in AccountFirebase: {firebase_uid}")
        raise HTTPException(status_code=403, detail="Invalid user")
    
    if expo_token:
        if expo_token.startswith('ExponentPushToken'):
            record.push_token = expo_token
        else:
            logging.error(f"Invalid Expo Push Token: {expo_token}")
    if fcm_token:
        record.fcm_token = fcm_token
        record.apn_token = None
    if apn_token:
        record.apn_token = apn_token
        record.fcm_token = None
    if device:
        record.device = device

    db.commit()        
    return SuccessResponse(success=True)

@router.post('/update_expo_push_token', response_model=SuccessResponse)
def update_expo_push_token(params: UpdateTokenParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    return update_device_token(db, firebase_uid, expo_token = params.token, device = params.device)

@router.post('/update_fcm_token', response_model=SuccessResponse)
def update_fcm_token(params: UpdateTokenParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    return update_device_token(db, firebase_uid, fcm_token = params.token, device = params.device)

@router.post('/update_apn_token', response_model=SuccessResponse)
def update_apn_token(params: UpdateTokenParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    return update_device_token(db, firebase_uid, apn_token = params.token, device = params.device)

class ProfileParams(BaseModel):
    ic_type: SGiMedICType
    nric: str
    name: str
    date_of_birth: date
    nationality: SGiMedNationality
    language: SGiMedLanguage
    gender: SGiMedGender

@router.get('/profile', response_model=ProfileParams)
def fetch_profile(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    return ProfileParams(
        ic_type=user.ic_type,
        nric=user.nric,
        name=user.name,
        date_of_birth=user.date_of_birth,
        nationality=user.nationality,
        language=user.language,
        gender=user.gender
    )

class UpdateProfileParams(BaseModel):
    language: SGiMedLanguage
    # ic_type: SGiMedICType
    # nric: str
    # name: str = Field(min_length=3, description="The name must be at least 3 characters")
    # date_of_birth: date
    # nationality: SGiMedNationality
    # gender: SGiMedGender

    # @field_validator("date_of_birth")
    # def validate_dob(cls, value: date) -> date:
    #     if value > sg_datetime.now().date():
    #         raise ValueError("Date of birth must be today or before")
    #     return value

@router.post('/profile')
def update_profile(params: UpdateProfileParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    user.language = params.language
    db.commit()
    # Update information into SGiMed if patient data exists
    if user.sgimed_patient_id:
        upsert_patient_in_sgimed(db, user)

    return SuccessResponse(success=True)

    # # Validate ID Number
    # id_type = params.ic_type
    # id_number= params.nric
    # if id_type in [SGiMedICType.PINK_IC, SGiMedICType.BLUE_IC] and not re.match(r'^[STFMG]\d{7}[A-Z]$', id_number): # Test: T1234567G
    #     raise HTTPException(400, "Invalid NRIC Number. Please try again")
    # if id_type in [SGiMedICType.FIN_NUMBER] and not re.match(r'^[FMG]\d{7}[A-Z]$', id_number): # Test: T1234567G
    #     raise HTTPException(400, "Invalid FIN Number. Please try again")
    # if id_type in [SGiMedICType.PASSPORT] and not re.match(r'^[A-Z0-9]{6,9}$', id_number): # Test: T1234567G
    #     raise HTTPException(400, "Invalid Passport Number. Please try again")

    # account = db.query(Account).filter(Account.nric == params.nric, Account.id != user.id).first()
    # if account:
    #     raise HTTPException(400, "NRIC/FIN/Passport Number is already in use. Please try again")

    # user.ic_type = params.ic_type
    # user.nric = params.nric
    # user.name = params.name    
    # user.date_of_birth = params.date_of_birth
    # user.nationality = params.nationality
    # user.gender = params.gender   

class UpdateMobileParams(BaseModel):
    mobile_code: PhoneCountryCode
    mobile_number: str
    secondary_mobile_code: Optional[PhoneCountryCode] = None
    secondary_mobile_number: Optional[str] = None
    email: Optional[EmailStr] = None

@router.get('/mobile', response_model=UpdateMobileParams)
def get_mobile(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    
    return UpdateMobileParams(
        mobile_code=user.mobile_code,
        mobile_number=user.mobile_number,
        secondary_mobile_code=user.secondary_mobile_code,
        secondary_mobile_number=user.secondary_mobile_number,
        email=user.email
    )

@router.post('/mobile', response_model=LoginResponse)
def update_mobile(params: UpdateMobileParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    mobile_code = params.mobile_code
    mobile_number = params.mobile_number
    
    if mobile_code != PhoneCountryCode.SINGAPORE or not re.match(r'^[89]\d{7}$', mobile_number):
        raise HTTPJSONException(
            status_code=400, 
            code=ExceptionCode.USER_NOT_SUPPORTED,
            title="Invalid Phone",
            message="Phone Number is invalid"
        )
    
    user = validate_user(db, firebase_uid)
    user.secondary_mobile_code = params.secondary_mobile_code
    user.secondary_mobile_number = params.secondary_mobile_number
    user.email = params.email
    db.commit()
    # Update mobile change only if patient information is in SGiMed
    if user.sgimed_patient_id:
        upsert_patient_in_sgimed(db, user)
    
    if user.mobile_number == mobile_number and user.mobile_code == mobile_code:
        print("No update for OTP as phone number is the same")
        return LoginResponse(
            session_id="",
            otp_expires_at=sg_datetime.now()
        )
    
    other_acc = get_account_by_phone(db, mobile_code, mobile_number)
    if other_acc:
        raise HTTPJSONException(
            status_code=400, 
            code=ExceptionCode.INVALID_LOGIN,
            title="Mobile Number Not Associated",
            message="Mobile number you've provided is associated with another account. Please try again"
        )

    session_id = str(uuid.uuid4())
    otp_code = generate_send_otp(mobile_code, mobile_number)

    otp_sent_at = time.time()
    otp_expires_at = otp_sent_at + OTP_EXPIRE_TIME
    login_state = RedisLoginState(
        id_type=user.ic_type,
        id_number=str(object=user.id),
        mobile_code=mobile_code,
        mobile_number=mobile_number,
        otp_code=otp_code,
        otp_sent_at=otp_sent_at,
        otp_expires_at=otp_expires_at,
        state=RedisAuthState.CHANGE_MOBILE
    )
    update_redis_loginstate(session_id, login_state)
    logging.info(f'Phone: {mobile_number}, OTP Sent: {otp_code}. Session: {session_id}, {login_state}')
    return LoginResponse(
        session_id=session_id,
        otp_expires_at=sg_datetime.fromtimestamp(otp_expires_at)
    )

class ResendOTPInput(BaseModel):
    session_id: str
class ResendOTPResponse(BaseModel):
    success: bool
    otp_expires_at: datetime

@router.post("/mobile/resend_otp", response_model=ResendOTPResponse)
def resend_otp(params: ResendOTPInput, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    session_id = params.session_id
    login_state = get_login_state(params.session_id)
    if not login_state:
        raise HTTPException(400, "Invalid session")

    # OTP can only be resent every 30 seconds
    if time.time() - login_state.otp_sent_at < OTP_RESEND_WAIT_TIME:
        raise HTTPJSONException(
            status_code=429, 
            code=ExceptionCode.OTP_RESEND_LIMIT,
            title="Resend OTP",
            message=f"Please wait for {OTP_RESEND_WAIT_TIME} secs before resending OTP"
        )

    try:
        otp_code = generate_send_otp(login_state.mobile_code, login_state.mobile_number)
        login_state.otp_code = otp_code
        login_state.otp_sent_at = time.time()
        login_state.otp_expires_at = login_state.otp_sent_at + OTP_EXPIRE_TIME
        update_redis_loginstate(session_id, login_state)
        logging.info(f'OTP Resent: {otp_code}. Session: {session_id}, {login_state}')
        return ResendOTPResponse(
            success=True,
            otp_expires_at=sg_datetime.fromtimestamp(login_state.otp_expires_at)
        )
    # SMSDomeException, return { 'code': 'otp_sent_failed', 'message': 'Failed to send OTP. Please try again later' }
    except Exception:
        raise HTTPJSONException(
            status_code=500, 
            code=ExceptionCode.OTP_SENT_FAILED,
            title="Failed to send OTP",
            message="Failed to send OTP. Please try again later."
        )

class VerifyOtpParams(BaseModel):
    session_id: str
    otp: str

@router.post('/mobile/verify_otp', response_model=SuccessResponse)
def verify_mobile_otp(params: VerifyOtpParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    session_id = params.session_id
    login_state = get_login_state(session_id)
    if not login_state:
        raise HTTPException(400, "Invalid session")

    # 1. If login state not found or state is not OTP sent, 
    if login_state.state != RedisAuthState.CHANGE_MOBILE:
        raise HTTPException(400, "Invalid state")
        return

    # 2. Check if OTP has expired
    if time.time() > login_state.otp_expires_at:
        raise HTTPJSONException(
            status_code=400, 
            code=ExceptionCode.EXPIRED_OTP,
            title="OTP expired",
            message="Your OTP has expired. Please request a new code"
        )
    
    # 3. Check if OTP is valid
    session_id, otp = params.session_id, params.otp
    if login_state.otp_code != otp:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.INVALID_OTP,
            title='Invalid OTP',
            message='The OTP you entered is incorrect. Please try again.'
        )

    # Successful, update phone number and delete state
    user = validate_user(db, firebase_uid)
    user.mobile_code = login_state.mobile_code
    user.mobile_number = login_state.mobile_number
    auth.update_user(
        uid=firebase_uid,
        phone_number=login_state.mobile_code.value + login_state.mobile_number,
    )
    db.commit()
    # Update mobile change only if patient information is in SGiMed
    if user.sgimed_patient_id:
        upsert_patient_in_sgimed(db,user)

    delete_login_state(session_id)
    return SuccessResponse(success=True)

class AddressParams(BaseModel):
    postal: Optional[str] = None
    address: Optional[str] = None
    unit: Optional[str] = None
    building: Optional[str] = None
    residential_postal: Optional[str] = None
    residential_address: Optional[str] = None
    residential_unit: Optional[str] = None
    residential_building: Optional[str] = None

@router.get('/address', response_model=AddressParams)
def fetch_address(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    return AddressParams(
        postal=user.postal, 
        address=user.address, 
        unit=user.unit, 
        building=user.building,
        residential_postal=user.residential_postal, 
        residential_address=user.residential_address, 
        residential_unit=user.residential_unit, 
        residential_building=user.residential_building,    
    )

@router.post('/address')
async def update_address(params: AddressParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = validate_user(db, firebase_uid)
    account_ids = [str(user.id)] + user.get_linked_account_ids()
    accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
    for account in accounts:
        account.postal = params.postal
        account.address = params.address
        account.unit = params.unit
        account.building = params.building
        account.residential_postal = params.residential_postal
        account.residential_address = params.residential_address
        account.residential_unit = params.residential_unit
        account.residential_building = params.residential_building
    db.commit()

    # Ensure sync with SGiMed when address is updated
    for account in accounts:
        if account.sgimed_patient_id:
            upsert_patient_in_sgimed(db, account)

    # Check if there is an ongoing teleconsult and update the address
    teleconsults = db.query(Teleconsult).filter(
            or_(Teleconsult.account_id == user.id, Teleconsult.created_by == user.id),
            Teleconsult.status != TeleconsultStatus.CHECKED_OUT
        ).all()
    for teleconsult in teleconsults:
        teleconsult.address = accounts[0].get_address()

    db.commit()
    await ws_manager.push_to_channel(WSMessage(event=WSEvent.PATIENT_ACTIVITY_UPDATE, id=str(user.id)))
    return SuccessResponse(success=True)

# class PaymentMethodParams(BaseModel):
#     payment_method: PaymentMethod
#     payment_id: Optional[str] = None # Placeholder when cards can be managed internally to store the ID and last four digits
# class PaymentMethodResponse(BaseModel):
#     success: bool
# @router.post('/payment_methods/default', response_model=PaymentMethodResponse)
# def set_default_payment_method(params: PaymentMethodParams, firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
#     user = get_user(db, firebase_uid)
#     if not user:
#         logging.error(f"Firebase UID not found in AccountFirebase: {firebase_uid}")
#         raise HTTPException(status_code=403, detail="Invalid user")

#     user.default_payment_method = params.payment_method
#     user.default_payment_id = params.payment_id
#     db.commit()
#     return PaymentMethodResponse(success=True)

class ManageStripeCardsResp(BaseModel):
    ephemeral_key: str
    setup_intent: str
    customer_id: str

@router.get('/payment_methods/stripe', response_model=ManageStripeCardsResp)
def manage_stripe_cards(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    user = get_user(db, firebase_uid)
    if not user:
        logging.error(f"Firebase UID not found in AccountFirebase: {firebase_uid}")
        raise HTTPException(status_code=403, detail="Invalid user")

    return ManageStripeCardsResp.model_validate(fetch_customer_sheet(db, user))

@router.get(path="/logout")
def logout(firebase_uid = Depends(validate_firebase_token), db: Session = Depends(get_db)):
    '''
    1. Remove push token from user tables
    '''
    account_firebase = db.query(AccountFirebase).where(AccountFirebase.firebase_uid == firebase_uid).first()
    if not account_firebase:
        raise HTTPException(400, "Account not found")

    account_firebase.push_token = None
    account_firebase.fcm_token = None
    db.commit()
