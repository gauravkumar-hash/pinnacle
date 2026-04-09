import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, date
import uuid
from sqlalchemy.orm import Session
from config import BACKEND_ENVIRONMENT
from models import SessionLocal, Appointment, Account
from models.model_enums import AppointmentStatus, SGiMedICType, SGiMedGender, SGiMedNationality, SGiMedLanguage, PhoneCountryCode
from scheduler_actions.appointment_updates import send_appointment_notifications
from utils.integrations.sgimed_appointment import update_appointment_status
from utils import sg_datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
import testing.postgresql

@pytest.fixture(scope='module')
def db():
    with testing.postgresql.Postgresql(settings={
            'initdb': '/opt/homebrew/opt/postgresql@14/bin/initdb',
            'postgres': '/opt/homebrew/opt/postgresql@14/bin/postgres'
        }) as postgresql:
        engine = create_engine(postgresql.url())
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        Base.metadata.drop_all(engine)

@patch('utils.integrations.sgimed_appointment.put')
@patch('utils.integrations.sgimed_appointment.get')
def test_sgimed_update_appointment_status(mock_get, mock_put):
    '''
    Test that update_appointment_status only changes the specified parameters
    and preserves all other values from the GET response for patient appointments.
    '''
    # Mock GET response for patient appointment
    get_response = {
        'branch_id': '123',
        'appointment_type': {'id': '456'},
        'calendars': [{'id': '789'}, {'id': '101'}],
        'start_date': '2024-01-15',
        'start_time': '09:00:00',
        'end_date': '2024-01-15',
        'end_time': '10:00:00',
        'subject': 'Health Checkup',
        'description': 'Annual health screening',
        'patient': {'id': '111'},
        'is_confirmed': False,
        'is_informed': False,
        'is_cancelled': False
    }
    mock_get.return_value = get_response
    mock_put.return_value = {'status': 'success'}
    
    # Test updating only is_informed to True
    update_appointment_status('test-appt-id', is_informed=True)
    
    # Verify GET was called correctly
    mock_get.assert_called_once_with('/appointment/test-appt-id')
    
    # Verify PUT was called with correct parameters
    mock_put.assert_called_once()
    # Extract the data dictionary from the PUT call
    put_call_data = mock_put.call_args[0][1]  # Second argument is the data dict
    
    # Assert that only is_informed changed
    assert put_call_data['is_confirmed'] == False, "is_confirmed should remain unchanged"
    assert put_call_data['is_informed'] == True, "is_informed should be updated to True"
    assert put_call_data['is_cancelled'] == False, "is_cancelled should remain unchanged"
    
    # Assert all other parameters are preserved
    assert put_call_data['branch_id'] == '123'
    assert put_call_data['appointment_type_id'] == '456'
    assert put_call_data['calendar_ids'] == ['789', '101']
    assert put_call_data['start_date'] == '2024-01-15'
    assert put_call_data['start_time'] == '09:00:00'
    assert put_call_data['end_date'] == '2024-01-15'
    assert put_call_data['end_time'] == '10:00:00'
    assert put_call_data['subject'] == 'Health Checkup'
    assert put_call_data['description'] == 'Annual health screening'
    assert put_call_data['patient_id'] == '111'

@patch('utils.integrations.sgimed_appointment.put')
@patch('utils.integrations.sgimed_appointment.get')
def test_sgimed_update_appointment_status_guest(mock_get, mock_put):
    '''
    Test that update_appointment_status only changes the specified parameters
    and preserves all other values from the GET response for guest appointments.
    '''
    # Mock GET response for guest appointment
    get_response = {
        'branch_id': '123',
        'appointment_type': {'id': '456'},
        'calendars': [{'id': '789'}],
        'start_date': '2024-01-15',
        'start_time': '14:00:00',
        'end_date': '2024-01-15',
        'end_time': '15:00:00',
        'subject': 'Consultation',
        'description': 'General consultation',
        'patient': None,
        'guest': {'name': 'John Doe', 'phone': '+6512345678'},
        'is_confirmed': True,
        'is_informed': False,
        'is_cancelled': False
    }
    mock_get.return_value = get_response
    mock_put.return_value = {'status': 'success'}
    
    # Test updating only is_cancelled to True
    update_appointment_status('guest-appt-id', is_cancelled=True)
    
    # Verify GET was called correctly
    mock_get.assert_called_once_with('/appointment/guest-appt-id')
    
    # Verify PUT was called with correct parameters
    mock_put.assert_called_once()
    # Extract the data dictionary from the PUT call
    put_call_data = mock_put.call_args[0][1]  # Second argument is the data dict
    
    # Assert that only is_cancelled changed
    assert put_call_data['is_confirmed'] == True, "is_confirmed should remain unchanged"
    assert put_call_data['is_informed'] == False, "is_informed should remain unchanged"
    assert put_call_data['is_cancelled'] == True, "is_cancelled should be updated to True"
    
    # Assert all other parameters are preserved
    assert put_call_data['guest_name'] == 'John Doe'
    assert put_call_data['mobile'] == '+6512345678'
    assert put_call_data['branch_id'] == '123'
    assert put_call_data['subject'] == 'Consultation'

@patch('utils.integrations.sgimed_appointment.put')
@patch('utils.integrations.sgimed_appointment.get')
def test_sgimed_update_appointment_status_multiple_params(mock_get, mock_put):
    '''
    Test that update_appointment_status can change multiple parameters
    while preserving others.
    '''
    # Mock GET response
    get_response = {
        'branch_id': '123',
        'appointment_type': {'id': '456'},
        'calendars': [{'id': '789'}],
        'start_date': '2024-01-15',
        'start_time': '11:00:00',
        'end_date': '2024-01-15',
        'end_time': '12:00:00',
        'subject': 'Follow-up',
        'description': 'Post-treatment follow-up',
        'patient': {'id': '222'},
        'is_confirmed': False,
        'is_informed': False,
        'is_cancelled': False
    }
    mock_get.return_value = get_response
    mock_put.return_value = {'status': 'success'}
    
    # Test updating multiple parameters
    update_appointment_status('multi-appt-id', is_confirmed=True, is_informed=True)
    
    # Verify only specified parameters changed
    put_call_data = mock_put.call_args[0][1]  # Second argument is the data dict
    
    assert put_call_data['is_confirmed'] == True, "is_confirmed should be updated to True"
    assert put_call_data['is_informed'] == True, "is_informed should be updated to True"
    assert put_call_data['is_cancelled'] == False, "is_cancelled should remain unchanged"

@patch('scheduler_actions.appointment_updates.update_appointment_status')
@patch('scheduler_actions.appointment_updates.send_patient_notification')
def test_send_appointment_notifications(mock_send_notification, mock_update_status, db: Session):
    '''
    Test send_appointment_notifications with various appointment records to ensure it only 
    processes appointments that meet ALL the specific criteria:
    - CONFIRMED status
    - Start datetime within next 24 hours  
    - Index is 0 or None (primary user)
    - appt_1_day_reminder not in notifications_sent
    - Has valid SGiMed appointment ID
    
    Edge cases tested:
    1. Wrong status (PREPAYMENT instead of CONFIRMED) - should NOT trigger
    2. Appointment too far in future (beyond 24 hours) - should NOT trigger
    3. Secondary user (index=1) - should NOT trigger  
    4. Already notified (has appt_1_day_reminder) - should NOT trigger
    5. No SGiMed appointment ID - passes SQL filter but gets skipped with error log
    6. Appointment in the past - should NOT trigger (SQL filter now excludes past appointments)
    '''
    # Current time reference
    now = sg_datetime.now()
    tomorrow = now + timedelta(hours=12)  # Within 24 hours
    day_after = now + timedelta(days=2)   # Beyond 24 hours
    
    # Create mock accounts with all required fields
    primary_account = Account(
        id = uuid.uuid4(),
        name = "John Doe",
        nric = "S1234567A",
        mobile_number = "12345678",
        ic_type = SGiMedICType.PINK_IC,
        gender = SGiMedGender.MALE,
        date_of_birth = date(1990, 1, 1),
        nationality = SGiMedNationality.SINGAPORE_CITIZEN,
        language = SGiMedLanguage.ENGLISH,
        mobile_code = PhoneCountryCode.SINGAPORE
    )
    secondary_account = Account(
        id = uuid.uuid4(),
        name = "Jane Doe",
        nric = "S7654321B",
        mobile_number = "87654321",
        ic_type = SGiMedICType.PINK_IC,
        gender = SGiMedGender.FEMALE,
        date_of_birth = date(1995, 5, 15),
        nationality = SGiMedNationality.SINGAPORE_CITIZEN,
        language = SGiMedLanguage.ENGLISH,
        mobile_code = PhoneCountryCode.SINGAPORE
    )
    
    # Add accounts to mock session
    db.add(primary_account)
    db.add(secondary_account)
    
    # Create test appointment scenarios with required fields
    # Scenario 1: VALID - CONFIRMED, within 24h, index=0, no appt_1_day_reminder
    valid_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.CONFIRMED,
        start_datetime=tomorrow,
        duration=30,  # Required field
        index=0,  # Primary user
        notifications_sent=[],  # No appt_1_day_reminder
        sgimed_appointment_id="sgimed-123",
        created_by=primary_account.id,
        account_id=primary_account.id,
        branch={"name": "Main Clinic"},
        services=[{"id": "service-1", "name": "Consultation"}],  # Required field
        payment_breakdown={}  # Required field
    )
    
    # Scenario 2: VALID - CONFIRMED, within 24h, index=None, no appt_1_day_reminder
    none_index_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.CONFIRMED,
        start_datetime=tomorrow,
        duration=45,  # Required field
        index=None,  # Should be treated as primary
        notifications_sent=["other_notification"],  # Has other notifications but not appt_1_day_reminder
        sgimed_appointment_id="sgimed-128",
        created_by=secondary_account.id,
        account_id=secondary_account.id,
        branch={"name": "Branch Clinic"},
        services=[{"id": "service-2", "name": "Health Screening"}],  # Required field
        payment_breakdown={}  # Required field
    )
    
    # EDGE CASES - These should NOT trigger notifications
    
    # Edge Case 1: INVALID - Wrong status (not CONFIRMED)
    pending_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.PREPAYMENT,  # Not CONFIRMED
        start_datetime=tomorrow,
        duration=30,
        index=0,
        notifications_sent=[],
        sgimed_appointment_id="sgimed-401",
        created_by=primary_account.id,
        account_id=primary_account.id,
        branch={"name": "Test Clinic"},
        services=[{"id": "service-3", "name": "Test Service"}],
        payment_breakdown={}
    )
    
    # Edge Case 2: INVALID - Appointment too far in future (beyond 24 hours)
    future_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.CONFIRMED,
        start_datetime=day_after,  # Beyond 24 hours
        duration=30,
        index=0,
        notifications_sent=[],
        sgimed_appointment_id="sgimed-402",
        created_by=primary_account.id,
        account_id=primary_account.id,
        branch={"name": "Future Clinic"},
        services=[{"id": "service-4", "name": "Future Service"}],
        payment_breakdown={}
    )
    
    # Edge Case 3: INVALID - Secondary user (index=1)
    secondary_user_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.CONFIRMED,
        start_datetime=tomorrow,
        duration=30,
        index=1,  # Secondary user, should be skipped
        notifications_sent=[],
        sgimed_appointment_id="sgimed-403",
        created_by=primary_account.id,
        account_id=primary_account.id,
        branch={"name": "Secondary Clinic"},
        services=[{"id": "service-5", "name": "Secondary Service"}],
        payment_breakdown={}
    )
    
    # Edge Case 4: INVALID - Already has appt_1_day_reminder notification
    already_notified_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.CONFIRMED,
        start_datetime=tomorrow,
        duration=30,
        index=0,
        notifications_sent=["appt_1_day_reminder"],  # Already notified
        sgimed_appointment_id="sgimed-404",
        created_by=primary_account.id,
        account_id=primary_account.id,
        branch={"name": "Already Notified Clinic"},
        services=[{"id": "service-6", "name": "Already Notified Service"}],
        payment_breakdown={}
    )
    
    # Edge Case 5: INVALID - No SGiMed appointment ID
    no_sgimed_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.CONFIRMED,
        start_datetime=tomorrow,
        duration=30,
        index=0,
        notifications_sent=[],
        sgimed_appointment_id=None,  # No SGiMed ID
        created_by=primary_account.id,
        account_id=primary_account.id,
        branch={"name": "No SGiMed Clinic"},
        services=[{"id": "service-7", "name": "No SGiMed Service"}],
        payment_breakdown={}
    )
    
    # Edge Case 6: INVALID - Appointment in the past
    # Note: Past appointments are now excluded by SQL filter (start_datetime > now)
    past_datetime = now - timedelta(hours=1)  # 1 hour ago
    past_appointment = Appointment(
        id=uuid.uuid4(),
        status=AppointmentStatus.CONFIRMED,
        start_datetime=past_datetime,
        duration=30,
        index=0,
        notifications_sent=[],
        sgimed_appointment_id="sgimed-405",
        created_by=primary_account.id,
        account_id=primary_account.id,
        branch={"name": "Past Clinic"},
        services=[{"id": "service-8", "name": "Past Service"}],
        payment_breakdown={}
    )
    
    # Add all appointments to session
    db.add(valid_appointment)
    db.add(none_index_appointment)
    db.add(pending_appointment)
    db.add(future_appointment)
    db.add(secondary_user_appointment)
    db.add(already_notified_appointment)
    db.add(no_sgimed_appointment)
    db.add(past_appointment)
    db.commit()

    # Execute the function
    send_appointment_notifications(db)

    # Verify that only eligible appointments triggered notifications
    # Note: 3 appointments pass SQL filters (2 valid + no_sgimed), past is now excluded
    # Only 2 actually send notifications (no_sgimed_appointment gets logged error and skipped)
    assert mock_send_notification.call_count == 2, f"Expected 2 notification calls, got {mock_send_notification.call_count}"
    assert mock_update_status.call_count == 2, f"Expected 2 status updates, got {mock_update_status.call_count}"
    
    # Verify notification parameters for eligible appointments
    notification_calls = mock_send_notification.call_args_list
    
    # First call should be for valid_appointment
    first_call_args = notification_calls[0][0]
    assert first_call_args[0] == primary_account, "First notification should be sent to primary account"
    assert first_call_args[1] == "Appointment Reminder", "Title should be 'Appointment Reminder'"
    assert "appointment scheduled for" in first_call_args[2], "Message should contain appointment details"
    assert "Main Clinic" in first_call_args[2], "Message should contain branch name"
    
    # Second call should be for none_index_appointment  
    second_call_args = notification_calls[1][0]
    assert second_call_args[0] == secondary_account, "Second notification should be sent to secondary account"
    assert second_call_args[1] == "Appointment Reminder", "Title should be 'Appointment Reminder'"
    assert "Branch Clinic" in second_call_args[2], "Message should contain branch name"
    
    # Verify SGiMed status updates
    status_update_calls = mock_update_status.call_args_list
    
    # First update should be for valid_appointment
    first_update_call = status_update_calls[0]
    assert first_update_call[0][0] == "sgimed-123", "First update should be for sgimed-123"
    assert first_update_call[1].get('is_informed') == True, "Should set is_informed=True"
    
    # Second update should be for none_index_appointment
    second_update_call = status_update_calls[1]
    assert second_update_call[0][0] == "sgimed-128", "Second update should be for sgimed-128"
    assert second_update_call[1].get('is_informed') == True, "Should set is_informed=True"
    
    # Verify notifications_sent was updated correctly for VALID appointments
    assert valid_appointment.notifications_sent == ["appt_1_day_reminder"], "Should add appt_1_day_reminder to empty list"
    assert none_index_appointment.notifications_sent == ["other_notification", "appt_1_day_reminder"], "Should append appt_1_day_reminder to existing notifications"
    
    # Verify edge cases were properly EXCLUDED (notifications_sent should remain unchanged)
    assert pending_appointment.notifications_sent == [], "PREPAYMENT status appointment should not be notified"
    assert future_appointment.notifications_sent == [], "Future appointment beyond 24h should not be notified"
    assert secondary_user_appointment.notifications_sent == [], "Secondary user (index=1) should not be notified"
    assert already_notified_appointment.notifications_sent == ["appt_1_day_reminder"], "Already notified appointment should remain unchanged"
    assert no_sgimed_appointment.notifications_sent == [], "Appointment without SGiMed ID should not be notified"
    assert past_appointment.notifications_sent == [], "Past appointment should not be notified"
