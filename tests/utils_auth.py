from datetime import date, datetime
import json
from operator import or_
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session
from config import BACKEND_ENVIRONMENT, EXPO_PUBLIC_API_KEY
from main import app  # Assuming your FastAPI app is in main.py
from models.patient import Account
from models.redis_models import RedisAuthState
from routers.patient.auth import LoginInput, LoginResponse, RegisterInput, RegisterResponse, VerifyDOBInput, VerifyDOBResponse, VerifyOTPInput, VerifyOTPResponse
from utils.auth import get_login_state
import os
import httpx
from pydantic import BaseModel
from firebase_admin import auth
from models import SessionLocal

client = TestClient(app)

# Define the fixture for db: Session
# (scope='module')
@pytest.fixture 
def db():
    if BACKEND_ENVIRONMENT != "development":
        raise Exception(f"Invalid Environment: {BACKEND_ENVIRONMENT}")
    
    with SessionLocal() as session:
        yield session


FIREBASE_WEB_API_KEY = os.getenv("FIREBASE_WEB_API_KEY")
if not FIREBASE_WEB_API_KEY:
    raise Exception("FIREBASE_WEB_API_KEY not set")


def firebase_to_jwt_token(token):
    '''
    Source: https://firebase.google.com/docs/reference/rest/auth#section-verify-custom-token
    '''
    class VerifyCustomTokenResponse(BaseModel):
        kind: str
        idToken: str
        refreshToken: str
        expiresIn: str
        isNewUser: bool

    url = f'https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken?key={FIREBASE_WEB_API_KEY}'
    headers = {'Content-Type': 'application/json'}
    data = {
        "token": token,
        "returnSecureToken": True
    }
    response = httpx.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f"Failed to get token: {response.text}")

    response = VerifyCustomTokenResponse(**response.json())
    return response.idToken


def user_cleanup(db: Session, user: Account):
    # Cleanup
    print(f"Deleting user: {user.id}")
    for firebase_auth in user.firebase_auths:
        print(f"Deleting from firebase: {firebase_auth.firebase_uid}")
        auth.delete_user(firebase_auth.firebase_uid)
        print("Delete from firebase_auths")
        db.delete(firebase_auth)
    print("Delete from patient_accounts")
    db.delete(user)
    db.commit()

def find_unused_nric_mobile(db: Session):
    # Find unused credentials
    day = datetime.now().day
    mobile_suffix = 0
    user = db.query(Account).filter(Account.mobile_number.like("89991%")).order_by(Account.mobile_number.desc()).first()
    if user:
        mobile_suffix = int(user.mobile_number[-4:]) + 1

    for i in range(1, 10):
        mobile_suffix += 1
        mobile_number = f"8999{mobile_suffix:04d}"
        nric = generate_valid_nric(f"S1{day:02d}{mobile_suffix:04d}F")
        record = db.query(Account).filter(or_(Account.nric == nric, Account.mobile_number == mobile_number)).first()
        if record:
            continue

        return nric, mobile_number
    
    raise Exception("Cannot find unused nric and mobile number")

def get(url: str, params: dict = {}, token: str = EXPO_PUBLIC_API_KEY):
    resp = client.get(
        url,
        headers={
            "Authorization": f"Bearer {token}"
        },
        params=params,
    )
    assert resp.status_code == 200, f"GET {url} != 200: {resp.text}"
    return resp.json()

def post_raw(url: str, body: str, token: str = EXPO_PUBLIC_API_KEY):
    resp = client.post(
        url,
        headers={
            "Authorization": f"Bearer {token}"
        },
        json=json.loads(body)
    )
    return resp
    
def post(url: str, body: str, token: str = EXPO_PUBLIC_API_KEY):
    resp = post_raw(url, body, token)
    assert resp.status_code == 200, f"POST {url} != 200: {resp.text}"
    return resp.json()

def login_latest_user(db: Session):
    # Setup for new user
    user = db.query(Account).filter(Account.mobile_number.like("89991%")).order_by(Account.mobile_number.desc()).first()
    assert user
    # Login as user
    data = {
        'id_type': user.ic_type,
        'id_number': user.nric,
        'mobile_code': user.mobile_code,
        'mobile_number': user.mobile_number
    }
    login_input = LoginInput(**data)
    return login_process(login_input)

def login_process(login_input: LoginInput, date_of_birth: date | None = None, register_input: RegisterInput | None = None) -> str:
    '''
    Goes through all the different state to get a logged in user
    '''
    if date_of_birth and register_input:
        raise Exception("Cannot have both date_of_birth and register_input")

    # Login Screen
    resp = post("/api/auth/login", login_input.model_dump_json())
    session_id = LoginResponse(**resp).session_id
    
    # Assert State in Redis
    login_state = get_login_state(session_id)
    assert login_state and login_state.state == RedisAuthState.VERIFY_OTP
    
    # OTP Screen
    resp = post("/api/auth/verify_otp", VerifyOTPInput(session_id=session_id, otp=login_state.otp_code).model_dump_json())
    resp = VerifyOTPResponse(**resp)

    # Verify DOB Screen
    if date_of_birth:
        assert resp.state == RedisAuthState.VERIFY_DOB
        resp = post("/api/auth/verify_dob", VerifyDOBInput(session_id=session_id, date_of_birth=date_of_birth).model_dump_json())
        resp = VerifyDOBResponse(**resp)
        # return firebase_to_jwt_token(resp.token)

    # Register Screen
    elif register_input:
        assert resp.state == RedisAuthState.REGISTER
        register_input.session_id = session_id
        resp = post("/api/auth/register", register_input.model_dump_json())
        resp = RegisterResponse(**resp)
        # return firebase_to_jwt_token(resp.token)
    
    return firebase_to_jwt_token(resp.token)

def generate_valid_nric(nric):
    '''
    Source: https://samliew.com/nric-generator
    '''
    if len(nric) != 9:
        raise Exception("Invalid NRIC")

    first = nric[0].upper()
    checksum = nric[-1].upper()
    digits = nric[1:8]

    if first not in 'STFGM':
        raise Exception("Invalid NRIC")

    if not digits.isdigit():
        raise Exception("Invalid NRIC")

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

    # return checksum == expected_checksum
    return f"{nric[:-1]}{expected_checksum}"

