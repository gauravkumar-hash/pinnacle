from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from models.model_enums import PatientType, CollectionMethod
from utils.system_config import get_sgimed_telemed_routing_params

# Mock classes and data
class MockTeleconsult:
    def __init__(self, patient_type=PatientType.PRIVATE_PATIENT, collection_method=CollectionMethod.PICKUP):
        self.patient_type = patient_type
        self.collection_method = collection_method
        self.branch = MockBranch()
        self.account = MockAccount()
    
    def get_appointment_type_id(self, db):
        return "DEFAULT-APPT-TYPE"

class MockBranch:
    def __init__(self, sgimed_branch_id="TEST-BRANCH"):
        self.sgimed_branch_id = sgimed_branch_id

class MockAccount:
    def __init__(self, is_test_user=False):
        self.id = "test-user-id" if is_test_user else "regular-user-id"

class MockDB:
    def __init__(self, config=None):
        self.config = config or {}
    
    def query(self, *args, **kwargs):
        return self
    
    def filter(self, *args, **kwargs):
        return self
    
    def first(self):
        return self.config

# Define test data constants
PT_BRANCH_ID = "PT-BRANCH"
DEFAULT_BRANCH_ID = "TEST-BRANCH"
DELIVERY_APPT_TYPE = "DELIVERY-TYPE"
PICKUP_APPT_TYPE = "PICKUP-TYPE"
DEFAULT_APPT_TYPE = "DEFAULT-APPT-TYPE"

def get_mock_config(enabled=True, state="on"):
    """Helper to generate test configuration"""
    # Format needs to match what get_config_value returns for TELECONSULT_BRANCH_ROUTING
    return {
        "sgimed_branch_id": PT_BRANCH_ID if enabled else None,
        "state": state,
        "delivery_sgimed_appointment_type_id": DELIVERY_APPT_TYPE,
        "pickup_sgimed_appointment_type_id": {
            DEFAULT_BRANCH_ID: PICKUP_APPT_TYPE
        }
    }

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_private_patient(mock_is_test_user, mock_get_config):
    """Test routing for private patient in normal mode"""
    # Setup
    db = MagicMock(spec=Session)
    mock_get_config.return_value = get_mock_config(enabled=True, state="on")
    mock_is_test_user.return_value = False
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.PICKUP
    )
    
    # Execute
    with patch('utils.system_config.logging.info'), \
         patch('utils.system_config.Teleconsult', MockTeleconsult):  # Type compatibility patch
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert
    assert branch_id == PT_BRANCH_ID
    assert appt_type == PICKUP_APPT_TYPE
    # In "on" state, is_test_user is not called because it routes all private patients regardless
    # of whether they're test users or not

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_private_patient_test_user_delivery(mock_is_test_user, mock_get_config):
    """Test routing for private patient test user with delivery collection method"""
    # Setup
    db = MagicMock(spec=Session)
    mock_get_config.return_value = get_mock_config(enabled=True, state="test")
    mock_is_test_user.return_value = True
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.DELIVERY
    )
    teleconsult.account = MockAccount(is_test_user=True)
    
    # Execute
    with patch('utils.system_config.Teleconsult', MockTeleconsult):  # Type compatibility patch
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert
    assert branch_id == PT_BRANCH_ID
    assert appt_type == DELIVERY_APPT_TYPE
    mock_is_test_user.assert_called_once()

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_private_patient_test_user_pickup(mock_is_test_user, mock_get_config):
    """Test routing for private patient test user with pickup collection method"""
    # Setup
    db = MagicMock(spec=Session)
    mock_get_config.return_value = get_mock_config(enabled=True, state="test")
    mock_is_test_user.return_value = True
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.PICKUP
    )
    teleconsult.account = MockAccount(is_test_user=True)
    
    # Execute
    with patch('utils.system_config.Teleconsult', MockTeleconsult):  # Type compatibility patch
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert
    assert branch_id == PT_BRANCH_ID
    assert appt_type == PICKUP_APPT_TYPE
    mock_is_test_user.assert_called_once()

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_private_patient_non_test_user_in_test_mode(mock_is_test_user, mock_get_config):
    """Test routing for private patient who is NOT a test user when routing is in test mode"""
    # Setup
    db = MagicMock(spec=Session)
    mock_get_config.return_value = get_mock_config(enabled=True, state="test")
    mock_is_test_user.return_value = False
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.PICKUP
    )
    teleconsult.account = MockAccount(is_test_user=False)
    
    # Execute
    with patch('utils.system_config.Teleconsult', MockTeleconsult):  # Type compatibility patch
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert - should not route to PT in test mode for non-test users
    assert branch_id == DEFAULT_BRANCH_ID
    assert appt_type == DEFAULT_APPT_TYPE
    mock_is_test_user.assert_called_once()

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_missing_branch_id(mock_is_test_user, mock_get_config):
    """Test error handling when PT branch ID is missing from configuration"""
    # Setup
    db = MagicMock(spec=Session)
    config = get_mock_config(state="on")
    config["sgimed_branch_id"] = None  # Missing branch ID
    mock_get_config.return_value = config
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.PICKUP
    )
    
    # Execute
    with patch('utils.system_config.logging.error') as mock_error, \
         patch('utils.system_config.Teleconsult', MockTeleconsult):
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert
    assert branch_id == DEFAULT_BRANCH_ID  # Should fall back to default branch
    assert appt_type == DEFAULT_APPT_TYPE
    mock_error.assert_called_once_with("PT Telemed Routing is on, but no SGiMed branch id found")

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_missing_delivery_appointment_type(mock_is_test_user, mock_get_config):
    """Test error handling when delivery appointment type is missing for a delivery teleconsult"""
    # Setup
    db = MagicMock(spec=Session)
    config = get_mock_config(state="on")
    config["delivery_sgimed_appointment_type_id"] = None  # Missing delivery appointment type
    mock_get_config.return_value = config
    mock_is_test_user.return_value = False
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.DELIVERY
    )
    
    # Execute
    with patch('utils.system_config.logging.error') as mock_error, \
         patch('utils.system_config.Teleconsult', MockTeleconsult):
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert
    assert branch_id == DEFAULT_BRANCH_ID  # Should fall back to default branch
    assert appt_type == DEFAULT_APPT_TYPE
    mock_error.assert_called_once_with("Delivery PT Routing is on, but no delivery appointment type id found")

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_missing_pickup_appointment_type(mock_is_test_user, mock_get_config):
    """Test error handling when pickup appointment type is missing for a branch"""
    # Setup
    db = MagicMock(spec=Session)
    config = get_mock_config(state="on")
    config["pickup_sgimed_appointment_type_id"] = {}  # No mappings for any branch
    mock_get_config.return_value = config
    mock_is_test_user.return_value = False
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.PICKUP
    )
    
    # Execute
    with patch('utils.system_config.logging.error') as mock_error, \
         patch('utils.system_config.Teleconsult', MockTeleconsult):
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert - should fall back to default routing
    assert branch_id == DEFAULT_BRANCH_ID
    assert appt_type == DEFAULT_APPT_TYPE
    mock_error.assert_called_once_with(
        f"Pickup PT Routing is on, but no pickup appointment type id found for branch: {teleconsult.branch.sgimed_branch_id}"
    )

@patch('utils.system_config.get_config_value')
@patch('utils.system_config.is_test_user')
def test_migrant_worker(mock_is_test_user, mock_get_config):
    """Test routing for migrant worker patient (should use default routing)"""
    # Setup
    db = MagicMock(spec=Session)
    mock_get_config.return_value = get_mock_config(enabled=True, state="on")
    mock_is_test_user.return_value = False
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.MIGRANT_WORKER, 
        collection_method=CollectionMethod.PICKUP
    )
    
    # Execute
    with patch('utils.system_config.Teleconsult', MockTeleconsult):  # Type compatibility patch
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert - should use default routing (not PT routing)
    assert branch_id == DEFAULT_BRANCH_ID
    assert appt_type == DEFAULT_APPT_TYPE
    # is_test_user should not be called for non-private patients
    mock_is_test_user.assert_not_called()

@patch('utils.system_config.get_config_value')
def test_when_routing_disabled(mock_get_config):
    """Test behavior when PT routing is disabled"""
    # Setup
    db = MagicMock(spec=Session)
    mock_get_config.return_value = None  # No routing config
    
    teleconsult = MockTeleconsult(
        patient_type=PatientType.PRIVATE_PATIENT, 
        collection_method=CollectionMethod.PICKUP
    )
    
    # Execute
    with patch('utils.system_config.Teleconsult', MockTeleconsult):  # Type compatibility patch
        branch_id, appt_type = get_sgimed_telemed_routing_params(db, teleconsult)
    
    # Assert - should use default routing
    assert branch_id == DEFAULT_BRANCH_ID
    assert appt_type == DEFAULT_APPT_TYPE 