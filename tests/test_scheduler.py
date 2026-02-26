from datetime import timedelta
import time
from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session
from config import BACKEND_ENVIRONMENT
from main import app  # Assuming your FastAPI app is in main.py
from models import SessionLocal
from models.patient import Account
from scheduler_actions.sgimed_updates import update_patient_profiles_cron
from utils.integrations.sgimed import update_patient_data

client = TestClient(app)

# Define the fixture for db: Session
@pytest.fixture(scope='module')
def db():
    if BACKEND_ENVIRONMENT != "development":
        raise Exception(f"Invalid Environment: {BACKEND_ENVIRONMENT}")
    
    with SessionLocal() as session:
        yield session

def test_dob_update_from_sgimed(db: Session):
    '''
    Given: New user with existing record on SGiMed with different date of birth
    When: Signs into the app
    Then: sgimed_patient_id, sgimed_auth_code, diff_dict should be populated
    '''
    
    user = db.query(Account).filter(Account.sgimed_patient_id != None).order_by(Account.updated_at.desc()).first()
    assert user and user.sgimed_patient_id
    new_dob = user.date_of_birth - timedelta(days=1)
    user_data = {
        "date_of_birth": new_dob.strftime("%Y-%m-%d"),
    }
    update_patient_data(user.sgimed_patient_id, user_data)
    time.sleep(1)
    update_patient_profiles_cron(db)
    db.refresh(user)
    assert user.date_of_birth == new_dob
    assert user.sgimed_auth_code == f"{user.nric[-4:].upper()}{new_dob.strftime('%d%m%y')}"
