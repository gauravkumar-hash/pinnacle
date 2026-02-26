"""
Unit tests for the update_corporate_code endpoint in routers/admin/appointment.py

Tests cover:
- Successful partial updates (only updating specified fields)
- Code uniqueness validation when changing code
- 404 when corporate code not found
- Preserving fields that are not included in the update request
"""
import pytest
from datetime import datetime, timedelta, timezone
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import testing.postgresql

from models import Base
from models.appointment import AppointmentCorporateCode
from models import get_db

# Import routers but create a test app without the lifespan handler
from fastapi import FastAPI

# Create a FastAPI app without the lifespan to avoid WebSocket broadcaster issues
# Named 'app_for_testing' to avoid pytest collection warning (pytest looks for 'test_*' patterns)
app_for_testing = FastAPI()

# Import and include the appointment router
from routers.admin import appointment as admin_appointment
from utils.fastapi import HTTPJSONException
from fastapi.responses import JSONResponse
from fastapi import Request

# Add the exception handler
@app_for_testing.exception_handler(HTTPJSONException)
async def exception_handler(request: Request, exc: HTTPJSONException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code.value,
            "title": exc.title,
            "message": exc.message,
            "detail": exc.message,
        },
    )

app_for_testing.include_router(admin_appointment.router, prefix="/api/admin/appointments/v1")


# Module-level database instance for performance
_postgresql = None
_engine = None


def get_postgresql():
    """Get or create the PostgreSQL test instance"""
    global _postgresql, _engine
    if _postgresql is None:
        _postgresql = testing.postgresql.Postgresql(settings={
            'initdb': '/opt/homebrew/opt/postgresql@14/bin/initdb',
            'postgres': '/opt/homebrew/opt/postgresql@14/bin/postgres'
        })
        _engine = create_engine(_postgresql.url())
        Base.metadata.create_all(_engine)
    return _postgresql, _engine


@pytest.fixture(scope='function')
def db():
    """Create a fresh session for each test with transaction rollback"""
    postgresql, engine = get_postgresql()
    TestSession = sessionmaker(bind=engine)
    session = TestSession()

    # Begin a transaction that we'll roll back at the end
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSession(bind=connection)

    yield session

    # Rollback the transaction to reset the database state
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db: Session):
    """Create a test client with mocked authentication and DB session"""
    from routers.admin.utils import get_current_user

    # This is the key: use the same session instance for the override
    def override_get_db():
        yield db

    # Mock auth by overriding the dependency
    async def mock_get_current_user():
        return {"user_id": "test-user"}

    app_for_testing.dependency_overrides[get_db] = override_get_db
    app_for_testing.dependency_overrides[get_current_user] = mock_get_current_user

    with TestClient(app_for_testing) as test_client:
        yield test_client

    app_for_testing.dependency_overrides.clear()


def create_corporate_code(db: Session, code: str = "TEST001", **kwargs) -> AppointmentCorporateCode:
    """Helper function to create a corporate code for testing"""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid.uuid4(),
        "code": code,
        "organization": "Test Organization",
        "patient_survey": {"question1": "How are you?"},
        "corporate_survey": {"survey1": "Corporate survey question"},
        "only_primary_user": False,
        "valid_from": now,
        "valid_to": now + timedelta(days=30),
        "is_active": True
    }
    defaults.update(kwargs)

    corp_code = AppointmentCorporateCode(**defaults)
    db.add(corp_code)
    db.flush()  # Use flush instead of commit to keep transaction open
    return corp_code


class TestUpdateCorporateCode:
    """Tests for PUT /api/admin/appointments/v1/corporate-codes/{code_id}"""

    def test_update_corporate_code_not_found(self, client: TestClient):
        """Test that 404 is returned when corporate code doesn't exist"""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{fake_id}",
            json={"code": "NEW_CODE"}
        )
        assert response.status_code == 404
        data = response.json()
        assert data["title"] == "Not Found"
        assert data["message"] == "Corporate code not found"

    def test_update_code_only(self, client: TestClient, db: Session):
        """Test updating only the code field preserves all other fields"""
        sample_corporate_code = create_corporate_code(db)

        original_org = sample_corporate_code.organization
        original_patient_survey = sample_corporate_code.patient_survey
        original_corporate_survey = sample_corporate_code.corporate_survey
        original_only_primary_user = sample_corporate_code.only_primary_user
        original_valid_from = sample_corporate_code.valid_from
        original_valid_to = sample_corporate_code.valid_to
        original_is_active = sample_corporate_code.is_active

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"code": "UPDATED001"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Refresh from database
        db.refresh(sample_corporate_code)

        # Verify code was updated
        assert sample_corporate_code.code == "UPDATED001"

        # Verify all other fields are preserved
        assert sample_corporate_code.organization == original_org
        assert sample_corporate_code.patient_survey == original_patient_survey
        assert sample_corporate_code.corporate_survey == original_corporate_survey
        assert sample_corporate_code.only_primary_user == original_only_primary_user
        assert sample_corporate_code.valid_from == original_valid_from
        assert sample_corporate_code.valid_to == original_valid_to
        assert sample_corporate_code.is_active == original_is_active

    def test_update_organization_only(self, client: TestClient, db: Session):
        """Test updating only the organization field"""
        sample_corporate_code = create_corporate_code(db)
        original_code = sample_corporate_code.code

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"organization": "New Organization Name"}
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.organization == "New Organization Name"
        assert sample_corporate_code.code == original_code

    def test_update_surveys(self, client: TestClient, db: Session):
        """Test updating patient_survey and corporate_survey fields"""
        sample_corporate_code = create_corporate_code(db)
        new_patient_survey = {"new_question": "Updated question?", "rating": 5}
        new_corporate_survey = {"corp_q1": "Corporate question 1", "corp_q2": "Corporate question 2"}

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={
                "patient_survey": new_patient_survey,
                "corporate_survey": new_corporate_survey
            }
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.patient_survey == new_patient_survey
        assert sample_corporate_code.corporate_survey == new_corporate_survey

    def test_update_only_primary_user(self, client: TestClient, db: Session):
        """Test updating only_primary_user flag"""
        sample_corporate_code = create_corporate_code(db)

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"only_primary_user": True}
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.only_primary_user is True

    def test_update_validity_dates(self, client: TestClient, db: Session):
        """Test updating valid_from and valid_to dates"""
        sample_corporate_code = create_corporate_code(db)
        new_valid_from = "2025-01-01T00:00:00Z"
        new_valid_to = "2025-12-31T23:59:59Z"

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={
                "valid_from": new_valid_from,
                "valid_to": new_valid_to
            }
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.valid_from is not None
        assert sample_corporate_code.valid_to is not None

    def test_update_is_active(self, client: TestClient, db: Session):
        """Test deactivating a corporate code"""
        sample_corporate_code = create_corporate_code(db)

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"is_active": False}
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.is_active is False

    def test_update_multiple_fields(self, client: TestClient, db: Session):
        """Test updating multiple fields at once"""
        sample_corporate_code = create_corporate_code(db)

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={
                "code": "MULTI001",
                "organization": "Multi Update Org",
                "is_active": False,
                "only_primary_user": True
            }
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.code == "MULTI001"
        assert sample_corporate_code.organization == "Multi Update Org"
        assert sample_corporate_code.is_active is False
        assert sample_corporate_code.only_primary_user is True

    def test_update_code_duplicate_rejected(self, client: TestClient, db: Session):
        """Test that updating to an existing code is rejected"""
        # Create two corporate codes
        sample_corporate_code = create_corporate_code(db, code="TEST001")
        another_corporate_code = create_corporate_code(db, code="EXISTING001")

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"code": another_corporate_code.code}  # Try to use existing code
        )

        assert response.status_code == 400
        data = response.json()
        assert data["title"] == "Code Already Exists"
        assert data["message"] == "Corporate code already exists"

    def test_update_code_same_value_allowed(self, client: TestClient, db: Session):
        """Test that updating code to the same value is allowed"""
        sample_corporate_code = create_corporate_code(db)
        original_code = sample_corporate_code.code

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"code": original_code}  # Same code
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.code == original_code

    def test_update_empty_request_preserves_all_fields(self, client: TestClient, db: Session):
        """Test that an empty update request preserves all existing fields"""
        sample_corporate_code = create_corporate_code(db)
        original_code = sample_corporate_code.code
        original_org = sample_corporate_code.organization
        original_patient_survey = sample_corporate_code.patient_survey
        original_corporate_survey = sample_corporate_code.corporate_survey

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={}
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.code == original_code
        assert sample_corporate_code.organization == original_org
        assert sample_corporate_code.patient_survey == original_patient_survey
        assert sample_corporate_code.corporate_survey == original_corporate_survey

    def test_update_clear_validity_dates(self, client: TestClient, db: Session):
        """Test clearing validity dates by setting them to null"""
        sample_corporate_code = create_corporate_code(db)

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={
                "valid_from": None,
                "valid_to": None
            }
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.valid_from is None
        assert sample_corporate_code.valid_to is None

    def test_update_survey_to_empty_dict(self, client: TestClient, db: Session):
        """Test clearing surveys by setting them to empty dicts"""
        sample_corporate_code = create_corporate_code(db)

        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={
                "patient_survey": {},
                "corporate_survey": {}
            }
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.patient_survey == {}
        assert sample_corporate_code.corporate_survey == {}


class TestUpdateCorporateCodeModelFieldsSet:
    """
    Tests specifically for the model_fields_set behavior in update_corporate_code.

    The function uses `req.model_fields_set` to determine which fields were
    explicitly set in the request, preventing accidental field wiping.
    """

    def test_fields_not_in_request_are_preserved(self, client: TestClient, db: Session):
        """
        Verify that fields not included in the request JSON are preserved.
        This tests the model_fields_set behavior.
        """
        sample_corporate_code = create_corporate_code(db)
        original_values = {
            "code": sample_corporate_code.code,
            "organization": sample_corporate_code.organization,
            "patient_survey": sample_corporate_code.patient_survey,
            "corporate_survey": sample_corporate_code.corporate_survey,
            "only_primary_user": sample_corporate_code.only_primary_user,
            "is_active": sample_corporate_code.is_active
        }

        # Only update organization
        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"organization": "Changed Organization Only"}
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)

        # Organization should be updated
        assert sample_corporate_code.organization == "Changed Organization Only"

        # All other fields should remain unchanged
        assert sample_corporate_code.code == original_values["code"]
        assert sample_corporate_code.patient_survey == original_values["patient_survey"]
        assert sample_corporate_code.corporate_survey == original_values["corporate_survey"]
        assert sample_corporate_code.only_primary_user == original_values["only_primary_user"]
        assert sample_corporate_code.is_active == original_values["is_active"]

    def test_explicit_none_vs_omitted_field(self, client: TestClient, db: Session):
        """
        Test that explicitly setting a field to None is different from omitting it.
        When valid_from is explicitly set to None, it should clear the value.
        """
        sample_corporate_code = create_corporate_code(db)

        # First ensure valid_from has a value
        assert sample_corporate_code.valid_from is not None

        # Explicitly set valid_from to None
        response = client.put(
            f"/api/admin/appointments/v1/corporate-codes/{sample_corporate_code.id}",
            json={"valid_from": None}
        )

        assert response.status_code == 200

        db.refresh(sample_corporate_code)
        assert sample_corporate_code.valid_from is None


def teardown_module():
    """Cleanup the PostgreSQL instance after all tests"""
    global _postgresql, _engine
    if _postgresql is not None:
        _postgresql.stop()
        _postgresql = None
        _engine = None
