from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from config import SGIMED_DEFAULT_BRANCH_ID
from models.model_enums import PhoneCountryCode, SGiMedGender, SGiMedLanguage, SGiMedNationality
from models.patient import Account
from routers.patient.auth import LoginInput, RegisterInput
from utils.integrations.sgimed import update_patient_data
from tests.utils_auth import generate_valid_nric, login_process, user_cleanup

SGIMED_PYTEST_PATIENT_ID = "17295920313148376"
PYTEST_PATIENT_NRIC_SGIMED = generate_valid_nric('S0101010A')
PYTEST_PATIENT_NRIC_NEW = generate_valid_nric('S0202020A')
PYTEST_PATIENT_MOBILE = '89990101'


def test_login_existing_user(db: Session):
    # Setup: Create a new user with existing SGiMed records

    # Setup for new user
    user = db.query(Account).filter(Account.mobile_number.like("89991%")).order_by(Account.mobile_number.desc()).first()
    assert user

    # Login as new user
    data = {
        'id_type': 'BLUE IC',
        'id_number': user.nric,
        'mobile_code': "+65",
        'mobile_number': user.mobile_number
    }
    login_input = LoginInput(**data) # type: ignore
    login_process(login_input)

def test_new_user_not_existing_in_sgimed(db: Session):
    '''
    Given: New user with no existing record on SGiMed
    When: Signs into the app
    Then: sgimed_patient_id, sgimed_auth_code, sgimed_diff should be None
    '''
    ic_type = "BLUE IC"
    nric = PYTEST_PATIENT_NRIC_NEW
    mobile_number = PYTEST_PATIENT_MOBILE
    date_of_birth = datetime.now() - timedelta(days=365*13)
    
    # Login params
    data = {
        'id_type': ic_type,
        'id_number': nric,
        'mobile_code': "+65",
        'mobile_number': mobile_number
    }
    print(data)
    login_input = LoginInput(**data) # type: ignore

    # Creating a new patient on SGiMed
    user_data = {
        "name": "Pytest User",
        "date_of_birth": date_of_birth.strftime("%Y-%m-%d"),
        "nationality": SGiMedNationality.MALAYSIAN,
        "language": SGiMedLanguage.FILIPINO.value,
        "gender": SGiMedGender.MALE.value
    }    
    user_data["session_id"] = 'xxx'
    register_input = RegisterInput(**user_data)
    token = login_process(login_input, register_input=register_input)

    # Creating a new user through registration
    user = db.query(Account).filter(Account.nric == nric).first()
    assert user
    print(user.as_dict())
    user_cleanup(db, user)
    assert user.sgimed_patient_id is None
    assert user.sgimed_auth_code is None
    assert user.sgimed_diff is None

def test_new_user_existing_in_sgimed_details_matched(db: Session):
    '''
    Given: New user with existing record on SGiMed having same records
    When: Signs into the app
    Then: sgimed_patient_id, sgimed_auth_code should be populated
    '''
    
    ic_type = "BLUE IC"
    sgimed_patient_id = SGIMED_PYTEST_PATIENT_ID
    nric = PYTEST_PATIENT_NRIC_SGIMED
    mobile_number = PYTEST_PATIENT_MOBILE
    date_of_birth = datetime.now() - timedelta(days=365*13)
    
    # Login params
    data = {
        'id_type': ic_type,
        'id_number': nric,
        'mobile_code': "+65",
        'mobile_number': mobile_number
    }
    print(data)
    login_input = LoginInput(**data) # type: ignore

    # Creating a new patient on SGiMed
    user_data = {
        "ic_type": login_input.id_type.value,
        "nric": nric,
        "name": "Pytest User",
        "date_of_birth": date_of_birth.strftime("%Y-%m-%d"),
        "nationality": SGiMedNationality.MALAYSIAN,
        "language": SGiMedLanguage.FILIPINO.value,
        "gender": SGiMedGender.MALE.value,
        "mobile": PhoneCountryCode.SINGAPORE.value + mobile_number,
        "branches": [SGIMED_DEFAULT_BRANCH_ID],
    }
    update_patient_data(sgimed_patient_id, user_data)
    
    user_data["session_id"] = 'xxx'
    register_input = RegisterInput(**{
        **user_data,
        "nationality": user_data["nationality"].title(),
    })
    token = login_process(login_input, register_input=register_input)

    # Creating a new user through registration
    user = db.query(Account).filter(Account.nric == nric).first()
    assert user
    print(user.as_dict())
    user_cleanup(db, user)
    assert user.sgimed_patient_id == sgimed_patient_id
    assert user.sgimed_auth_code
    assert user.sgimed_diff is None

def test_new_user_existing_in_sgimed_details_not_matched(db: Session):
    '''
    Given: New user with existing record on SGiMed with different date of birth
    When: Signs into the app
    Then: sgimed_patient_id, sgimed_auth_code, diff_dict should be populated
    '''

    ic_type = "BLUE IC"
    sgimed_patient_id = SGIMED_PYTEST_PATIENT_ID
    nric = PYTEST_PATIENT_NRIC_SGIMED
    mobile_number = PYTEST_PATIENT_MOBILE
    today = datetime.now()
    date_of_birth =date(2011, today.month, today.day)
    
    # Login params
    data = {
        'id_type': ic_type,
        'id_number': nric,
        'mobile_code': "+65",
        'mobile_number': mobile_number,
    }
    print(data)
    login_input = LoginInput(**data) # type: ignore
    
    # Creating a new patient on SGiMed
    user_data = {
        "ic_type": "PINK IC", # Update from BLUE IC to PINK IC to trigger sgimed_diff
        "nric": nric,
        "name": "Pytest User",
        "date_of_birth": date_of_birth.strftime("%Y-%m-%d"),
        "nationality": SGiMedNationality.MALAYSIAN,
        "language": SGiMedLanguage.FILIPINO.value,
        "gender": SGiMedGender.MALE.value,
        "mobile": PhoneCountryCode.SINGAPORE.value + mobile_number,
        "branches": [SGIMED_DEFAULT_BRANCH_ID],
    }
    update_patient_data(sgimed_patient_id, user_data)

    user_data["session_id"] = 'xxx'
    register_input = RegisterInput(**{
        **user_data,
        "nationality": user_data["nationality"].title(),
    })
    register_input.name += " Edit"
    register_input.date_of_birth -= timedelta(days=3)
    register_input.nationality = SGiMedNationality.SINGAPORE_CITIZEN
    register_input.language = SGiMedLanguage.ENGLISH
    register_input.gender = SGiMedGender.FEMALE
    token = login_process(login_input, register_input=register_input)

    # Creating a new user through registration
    user = db.query(Account).filter(Account.nric == nric).first()
    assert user
    print(user.as_dict())
    user_cleanup(db, user)
    assert user.sgimed_patient_id == sgimed_patient_id
    assert user.sgimed_auth_code
    assert user.sgimed_diff and not (set(['ic_type', 'name', 'date_of_birth', 'nationality', 'language', 'gender']) - set(user.sgimed_diff.keys()))
