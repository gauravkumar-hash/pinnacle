from datetime import datetime, timedelta
from models.model_enums import PhoneCountryCode, SGiMedGender, SGiMedLanguage, SGiMedNationality
from models.patient import Account
from routers.patient.auth import LoginInput, RegisterInput
from tests.utils_auth import find_unused_nric_mobile, login_process
from utils.integrations.sgimed import upsert_patient_in_sgimed
from sqlalchemy.orm import Session

def test_upsert_new_user(db: Session):
    '''
    Given: New user starts teleconsult
    When: teleconsult started
    Then: patient record with details updated in SGiMed
    '''
    nric, mobile_number = find_unused_nric_mobile(db)
    data = {
        'id_type': 'PINK IC',
        'id_number': nric,
        'mobile_code': PhoneCountryCode.SINGAPORE,
        'mobile_number': mobile_number,
    }
    login_input = LoginInput(**data)
    # Creating a new patient on SGiMed
    date_of_birth = datetime.now() - timedelta(days=365*13)
    user_data = {
        "name": "Pytest User",
        "date_of_birth": date_of_birth.strftime("%Y-%m-%d"),
        "nationality": SGiMedNationality.SINGAPORE_CITIZEN,
        "language": SGiMedLanguage.FILIPINO.value,
        "gender": SGiMedGender.MALE.value
    }    
    user_data["session_id"] = 'xxx'
    register_input = RegisterInput(**user_data)
    login_process(login_input, register_input=register_input)
    
    user = db.query(Account).filter(Account.nric == nric).first()
    assert user
    assert user.sgimed_patient_id is None
    upsert_patient_in_sgimed(db, user)
    assert user.sgimed_patient_id

def test_upsert_merged_user(db: Session):
    '''
    Given the user is merged and sgimed_patient_id is invalid
    When a user with sgimed_patient_id becomes invalid
    Then find the sgimed_patient_id based on user NRIC
    '''
    user = db.query(Account).filter(Account.sgimed_patient_id != None).first()
    assert user
    actual_sgimed_patient_id = user.sgimed_patient_id
    user.sgimed_patient_id = 'invalid'
    upsert_patient_in_sgimed(db, user)
    assert user.sgimed_patient_id == actual_sgimed_patient_id
