from sqlalchemy import func
from sqlalchemy.orm import Session
from models.model_enums import SGiMedICType
from models.patient import Account
from routers.patient.auth import LoginInput
from tests.utils_auth import generate_valid_nric, post_raw
from utils.auth import id_number_validation

def test_invalid_nric_login():
    '''
    Given: User logs in
    When: ID Number is invalid based on id type
    Then: display invalid error
    '''
    # Invalid match to id_number structure
    for id_type in ['PINK IC', 'BLUE IC', 'FIN NUMBER', 'PASSPORT']:
        data = {
            'id_type': id_type,
            'id_number': 's1234561234a',
            'mobile_code': '+65',
            'mobile_number': '89991234'
        }
        login_input = LoginInput(**data) # type: ignore
        resp = post_raw("/api/auth/login", login_input.model_dump_json())
        assert resp.status_code == 400
        resp = resp.json()
        assert resp['code'] == 'invalid_login'

    # Under 12 years old error
    for id_type in ["PINK IC", "BLUE IC"]:
        data = {
            'id_type': id_type,
            'id_number': generate_valid_nric('T1600000A'),
            'mobile_code': '+65',
            'mobile_number': '89991234'
        }
        login_input = LoginInput(**data) # type: ignore
        resp = post_raw("/api/auth/login", login_input.model_dump_json())
        assert resp.status_code == 400
        resp = resp.json()
        print(resp)
        assert resp['message'] == 'Age must be at least 12 years old'

def test_invalid_nric():
    '''
    Validate NRIC/FIN Number used when signing in and adding family
    '''
    # Invalid match to id_number structure
    for id_type in [SGiMedICType.PINK_IC, SGiMedICType.BLUE_IC, SGiMedICType.FIN_NUMBER, SGiMedICType.PASSPORT]:
        error = id_number_validation(id_type, 's1234561234a')
        assert error is not None

    # Validate failure and success cases
    nric_id_types = [
            (SGiMedICType.PINK_IC, 'S0010010A'),
            (SGiMedICType.BLUE_IC, 'T0010010A'),
            (SGiMedICType.FIN_NUMBER, 'F0010011A'),
            (SGiMedICType.FIN_NUMBER, 'G0010011A'),
            (SGiMedICType.FIN_NUMBER, 'M0010011A')
        ]
    for id_type, id_number in nric_id_types:
        error = id_number_validation(id_type, id_number)
        assert error and 'Invalid NRIC/FIN number.' in error
    for id_type, id_number in nric_id_types:
        error = id_number_validation(id_type, generate_valid_nric(id_number))
        assert error is None


def test_login_invalid_phone_number(db: Session):
    data = {
        'id_type': 'PINK IC',
        'id_number': generate_valid_nric('S0010010A'),
        'mobile_code': '+65',
        'mobile_number': '69991234'
    }
    login_input = LoginInput(**data) # type: ignore
    resp = post_raw("/api/auth/login", login_input.model_dump_json())
    assert resp.status_code == 400
    resp = resp.json()
    assert resp['message'] == 'Invalid phone number'
    
    # Fetch two users for testing
    users = db.query(Account).filter(func.length(Account.mobile_number) == 8).limit(2).all()
    if len(users) != 2:
        raise Exception("Failed to find 2 users for testing")

    # 1. Test with existing user, using another existing user phone number
    data = {
        'id_type': users[0].ic_type,
        'id_number': users[0].nric,
        'mobile_code': users[1].mobile_code,
        'mobile_number': users[1].mobile_number
    }
    login_input = LoginInput(**data) # type: ignore
    resp = post_raw("/api/auth/login", login_input.model_dump_json())
    assert resp.status_code == 400
    resp = resp.json()
    print(f"Input: {data}\nResp: {resp}")
    assert resp['title'] == 'Mobile Number Not Associated'
    
    
    # 2. Test with new user, using another existing user phone number
    data = {
        'id_type': 'FIN NUMBER',
        'id_number': generate_valid_nric('G0010010A'),
        'mobile_code': users[0].mobile_code,
        'mobile_number': users[0].mobile_number
    }
    login_input = LoginInput(**data) # type: ignore
    resp = post_raw("/api/auth/login", login_input.model_dump_json())
    assert resp.status_code == 400
    resp = resp.json()
    print(f"Input: {data}\nResp: {resp}")
    assert resp['title'] == 'Mobile Number Not Associated'
