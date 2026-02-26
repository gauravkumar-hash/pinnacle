from datetime import date, datetime
import logging
from typing import Optional
import time
import uuid
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth
from models.redis_models import RedisAuthState, RedisLoginState
from models import get_db
from models.model_enums import PhoneCountryCode, SGiMedGender, SGiMedICType, SGiMedLanguage, SGiMedNationality
from models.patient import Account, AccountFirebase, FirebaseLoginType
from repository.family_nok import delete_family_account
from services.family import check_ongoing_consults
from utils.auth import OTP_EXPIRE_TIME, OTP_RESEND_WAIT_TIME, generate_login_token, get_account_by_id, get_account_by_phone, get_account_firebase_uid, get_login_state, generate_send_otp, id_number_validation, raise_invalid_login, update_redis_loginstate
from config import EXPO_PUBLIC_API_KEY
import re
from utils.fastapi import ExceptionCode, HTTPJSONException
from utils import sg_datetime
from sqlalchemy.orm import Session
from utils.integrations.sgimed import retrieve_sgimed_patient_id
from firebase_admin.auth import PhoneNumberAlreadyExistsError
# The following will validate all public facing requests like login
auth_scheme = HTTPBearer()
def validate_token(token: HTTPAuthorizationCredentials = Depends(auth_scheme)):
    if token.credentials != EXPO_PUBLIC_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid token")

router = APIRouter(dependencies=[Depends(validate_token)])

class LoginInput(BaseModel):
    id_type: SGiMedICType
    id_number: str
    mobile_code: PhoneCountryCode
    mobile_number: str
    
    @field_validator("id_type", mode="before")
    def validate_id_type(cls, value: str):
        # This is for earlier versions where the id_type used is defined as BLUE IC
        if value == 'BLUE IC':
            return SGiMedICType.BLUE_IC
        return SGiMedICType(value)

class LoginResponse(BaseModel):
    session_id: str
    otp_expires_at: datetime

@router.post("/login", response_model=LoginResponse)
def register_or_login(params: LoginInput, db = Depends(get_db)):    
    id_type = params.id_type
    id_number = params.id_number.upper().strip()
    mobile_code = params.mobile_code
    mobile_number = params.mobile_number.strip()

    # 1 - FIN entered is invalid
    id_error = id_number_validation(id_type, id_number)
    if id_error:
        raise_invalid_login(message=id_error)

    if id_type in [SGiMedICType.PINK_IC, SGiMedICType.BLUE_IC] and id_number.startswith('T'):
        age = sg_datetime.now().year - int(f'20{id_number[1:3]}')
        if age < 12:
            raise_invalid_login(message="Age must be at least 12 years old")

    # 3 - Invalid Phone Number
    if mobile_code != PhoneCountryCode.SINGAPORE or not re.match(r'^[89]\d{7}$', mobile_number):
        raise_invalid_login(message="Invalid phone number")

    # 4 - Phone in Accounts database but ID number is different. 1st Sentry Call
    account = get_account_by_phone(db, mobile_code, mobile_number)
    if account and account.nric != id_number:
        raise_invalid_login(
            title="Mobile Number Not Associated",
            message="Mobile number you've provided is not associated with ID Number. Please try again.\n\nIf this was a mistake, kindly call +65 6235 1852"
        )

    # 5 - Check if linked to family member and if there is an ongoing teleconsult. 2nd Sentry Call
    account = get_account_by_id(db, id_number)
    if account and account.parent_nok: # 3rd Call
        has_ongoing_consult = check_ongoing_consults(db, str(account.id))
        if has_ongoing_consult:
            raise_invalid_login(
                title="Ongoing Consultation",
                message="Unable to login as there is an ongoing Teleconsultation/Queue Request for this family member. Please wait for the consultation to complete before logging in again."
            )

    # No Account or FIN matches. Phone number could be different from what is recorded
    try:
        session_id = str(uuid.uuid4())
        otp_code = generate_send_otp(mobile_code, mobile_number)

        otp_sent_at = time.time()
        otp_expires_at = otp_sent_at + OTP_EXPIRE_TIME
        login_state = RedisLoginState(
            id_type=id_type,
            id_number=id_number, 
            mobile_code=mobile_code,
            mobile_number=mobile_number,
            otp_code=otp_code,
            otp_sent_at=otp_sent_at,
            otp_expires_at=otp_expires_at,
        )
        update_redis_loginstate(session_id, login_state)
        logging.info(f'Phone: {mobile_number}, OTP Sent: {otp_code}. Session: {session_id}, {login_state}')
        return LoginResponse(
            session_id=session_id,
            otp_expires_at=sg_datetime.fromtimestamp(otp_expires_at)
        )
    except Exception:
        logging.error("Possibly failed to connect to Redis")
        raise HTTPJSONException(
            status_code=500, 
            code=ExceptionCode.OTP_SENT_FAILED,
            title="Failed to send OTP",
            message="Failed to send OTP. Please try again later."
        )

class SessionInput(BaseModel):
    session_id: str
def validate_session(params: SessionInput):
    # 1. If login state not found or state is not 'otp_sent', return { 'code': 'invalid_session', 'redirect_to': 'login', 'message': 'Invalid session. Please try again' }
    login_state = get_login_state(params.session_id)
    if not login_state:
        raise_invalid_login()
        return
    
    return login_state
class ResendOTPInput(BaseModel):
    session_id: str
class ResendOTPResponse(BaseModel):
    success: bool
    otp_expires_at: datetime

@router.post("/resend_otp", response_model=ResendOTPResponse)
def resend_otp(params: ResendOTPInput, login_state: RedisLoginState = Depends(validate_session)):
    if login_state.state != RedisAuthState.VERIFY_OTP:
        raise_invalid_login()
        return
    
    session_id = params.session_id

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

def create_firebase_record(db: Session, account: Account, login_state: RedisLoginState):
    logging.info('verify_dob: Failed to get firebase uid for account: {0}'.format(account.id))
    try:
        user = auth.create_user(
            display_name=account.name,
            phone_number=login_state.mobile_code.value + login_state.mobile_number,
            password=str(uuid.uuid4()) # Random password since it is not being used for now
        )
    except PhoneNumberAlreadyExistsError:
        raise Exception(f"Phone number already exists: {login_state.id_number} {login_state.mobile_number}")

    accFirebase = AccountFirebase(
        account_id=account.id,
        login_type=FirebaseLoginType.PHONE,
        firebase_uid=user.uid,
    )
    db.add(accFirebase)
    db.commit()
    
    return accFirebase

def create_login_token(db: Session, session_id: str, account: Account):
    # Delete the parent relationship if it exists once a new account is created
    if account.parent_nok:
        delete_family_account(db, account.parent_nok)

    token = generate_login_token(db, session_id, account)
    if not token:
        logging.error('Failed to generate login token for account: {0}'.format(account.id))
        raise HTTPJSONException(
            status_code=500,
            code=ExceptionCode.SERVER_ERROR,
            title="Login Failed",
            message="Failed to login. Please try again later."
        )

    return token

class VerifyOTPInput(BaseModel):
    session_id: str
    otp: str
    
class VerifyOTPResponse(BaseModel):
    token: Optional[str] = None
    state: RedisAuthState

@router.post("/verify_otp", response_model=VerifyOTPResponse)
def verify_otp(params: VerifyOTPInput, login_state: RedisLoginState = Depends(validate_session), db = Depends(get_db)):
    # 1. If login state not found or state is not OTP sent, 
    if login_state.state != RedisAuthState.VERIFY_OTP:
        raise_invalid_login()
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

    # OTP is Valid and not expired
    account = get_account_by_id(db, login_state.id_number)

    # 1. New User: If FIN or Mobile Number does not exist in the database
    if not account:
        login_state.state = RedisAuthState.REGISTER
        update_redis_loginstate(session_id, login_state)
        return VerifyOTPResponse(
            token=None,
            state=RedisAuthState.REGISTER
        )

    # 2. Existing User: If FIN and Mobile Number matches in the database
    if account.nric == login_state.id_number and account.mobile_code == login_state.mobile_code and account.mobile_number == login_state.mobile_number:
        # The following code is for imported records into the database. There is no record in Firebase, therefore, it is created separately
        firebase_uid = get_account_firebase_uid(db, str(account.id))
        if not firebase_uid:
            create_firebase_record(db, account, login_state)

        return VerifyOTPResponse(
            token=create_login_token(db, session_id, account),
            state=RedisAuthState.LOGGED_IN
        )


    # 3. Existing User: If FIN matches but Mobile Number is different
    # If FIN does not match, if would trigger the last condition
    if account.nric == login_state.id_number:
        # Check if the number matches other people profiles
        
        login_state.state = RedisAuthState.VERIFY_DOB
        update_redis_loginstate(session_id, login_state)
        return VerifyOTPResponse(
            token=None,
            state=RedisAuthState.VERIFY_DOB
        )

    # 4. Existing User: If FIN does not match but mobile number matches
    # It means that the mobile number is associated with another account
    raise HTTPJSONException(
        status_code=400,
        code=ExceptionCode.INVALID_LOGIN,
        title="Invalid Login",
        message="Mobile number you've provided is not associated with FIN. Please try again."
    )


class VerifyDOBInput(BaseModel):
    session_id: str
    date_of_birth: date
class VerifyDOBResponse(BaseModel):
    token: str

@router.post("/verify_dob", response_model=VerifyDOBResponse)
def verify_dob(params: VerifyDOBInput, login_state: RedisLoginState = Depends(validate_session), db: Session = Depends(get_db)):
    # 1. If login state not found or state is not to verify dob, 
    if login_state.state != RedisAuthState.VERIFY_DOB:
        raise_invalid_login()
    account = get_account_by_id(db, login_state.id_number)
    if not account:
        raise_invalid_login()
        return

    if account.date_of_birth != params.date_of_birth:
        raise HTTPJSONException(
            status_code=400,
            code=ExceptionCode.INVALID_DOB,
            title="Invalid DOB",
            message="Invalid DOB. Please try again."
        )

    # Update phone number in Accounts table, Generate login token
    account.mobile_code = login_state.mobile_code
    account.mobile_number = login_state.mobile_number

    # The following code is for imported records into the database. There is no record in Firebase, therefore, it is created separately
    firebase_uid = get_account_firebase_uid(db, str(account.id))
    if not firebase_uid:
        create_firebase_record(db, account, login_state)
    # Update Firebase Phone Number
    else:
        auth.update_user(
            uid=firebase_uid,
            phone_number=login_state.mobile_code.value + login_state.mobile_number,
        )
    db.commit()

    return VerifyDOBResponse(
        token=create_login_token(db, params.session_id, account)
    )

class RegisterInput(BaseModel):
    session_id: str
    # Validate at least 3 characters
    name: str = Field(min_length=3, description="The name must be at least 3 characters")
    date_of_birth: date
    nationality: SGiMedNationality # Reference SGiMed Nationality List
    language: SGiMedLanguage
    gender: SGiMedGender
    # phone_code: Optional[str] = None # Additional Phone Code + Number
    # phone_number: Optional[str] = None
    # marital_status: Optional[SGiMedMaritalStatus]
    # email: Optional[EmailStr] = None
    # country: Optional[str] = None
    
    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        if not re.match(r'^[a-zA-Z\d\s\-\.\'\,\/\:\;\'\'\(\)\@]*$', value):
            raise_invalid_login(message="Name must contain only latin characters and common symbols")
        return value.strip()
    
    @field_validator("date_of_birth")
    def validate_dob(cls, value: date) -> date:
        today = sg_datetime.now().date()
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 12:
            raise_invalid_login(message="Age must be at least 12 years")

        if value > sg_datetime.now().date():
            raise ValueError("Date of birth must be today or before")
        return value

class RegisterResponse(BaseModel):
    token: str

@router.post("/register", response_model=RegisterResponse)
def mw_register(params: RegisterInput, login_state: RedisLoginState = Depends(validate_session), db: Session = Depends(get_db)):
    # 1. If login state not found or state is not to verify dob, 
    if login_state.state != RedisAuthState.REGISTER:
        raise_invalid_login()
        return

    # This is to catch events where there are two register instances and one of them already created the account
    account = get_account_by_id(db, login_state.id_number)
    if account:
        raise_invalid_login(message="Account already exists")
        return

    # Create user in firebase auth
    user = None
    try:
        user = auth.create_user(
            display_name=params.name,
            phone_number=login_state.mobile_code.value + login_state.mobile_number,
            password=str(uuid.uuid4()) # Random password since it is not being used for now
        )
        logging.info('Sucessfully created new user: {0}'.format(user.uid))
    # except EmailAlreadyExistsError as e:
    # except PhoneNumberAlreadyExistsError as e:
    # except ValueError as e:
    except Exception as e:
        logging.error('Failed to create new Firebase user: {0}'.format(e))

    # Sometimes the user does not exist in the database but exists in Firebase
    if not user:
        try:
                user = auth.get_user_by_phone_number(login_state.mobile_code.value + login_state.mobile_number)
        except Exception:
            logging.error('Failed to get Firebase user by phone number: {0}'.format(login_state.mobile_code.value + login_state.mobile_number))
            user = None

    if not user:
        raise HTTPJSONException(
            status_code=500,
            code=ExceptionCode.SERVER_ERROR,
            title="Server Error",
            message="Failed to create account. Please try again later."
        )
    
    account = Account(
        ic_type=login_state.id_type,
        nric=login_state.id_number,
        mobile_code=login_state.mobile_code,
        mobile_number=login_state.mobile_number,
        name=params.name,
        gender=params.gender,
        date_of_birth=params.date_of_birth,
        nationality=params.nationality,
        language=params.language,
        ## Secondary Contact
        # phone_code: Mapped[Optional[str]]
        # phone_number: Mapped[Optional[str]]    
        # email: Mapped[Optional[str]]
        # marital_status: Mapped[SGiMedMaritalStatus]
        # country: Mapped[str] # Reference SGiMed Country list
        # # TODO: Review if these fields should be optional
        # postal: Mapped[Optional[str]]
        # address: Mapped[Optional[str]]
        # unit: Mapped[Optional[str]]
        # building_name: Mapped[Optional[str]]
        firebase_auths=[
            AccountFirebase(
                login_type=FirebaseLoginType.PHONE,
                firebase_uid=user.uid,
            )
        ]
    )
    db.add(account)
    db.commit()
    # Once account is created, tag SGiMed patient ID if it exists on SGiMed
    retrieve_sgimed_patient_id(db, account)
    
    return RegisterResponse(
        token=create_login_token(db, params.session_id, account)
    )
