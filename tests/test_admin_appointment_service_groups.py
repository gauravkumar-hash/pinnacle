"""
Admin appointment endpoints for the revised appointment workflow:
- Duplicate service groups (with services) under another corporate code
- Partial updates (drag-and-drop reorder sends only {index}) must not wipe corporate code / inventory
- New slot allocation fields round trip (corporate code max_bookings_per_slot, clinic/corporate caps on hours)
"""
import pytest
import uuid
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import testing.postgresql

from models import Base, Branch, get_db
from models.appointment import AppointmentCorporateCode, AppointmentServiceGroup, AppointmentService, AppointmentBranchOperatingHours
from models.model_enums import AppointmentServiceGroupType, BranchType, DayOfWeek
from models.sgimed import SGiMedInventory
from routers.admin import appointment as admin_appointment
from routers.admin.utils import get_current_user
from utils.fastapi import HTTPJSONException

app_for_testing = FastAPI()

@app_for_testing.exception_handler(HTTPJSONException)
async def exception_handler(request: Request, exc: HTTPJSONException):
    return JSONResponse(status_code=exc.status_code, content={"title": exc.title, "message": exc.message})

app_for_testing.include_router(admin_appointment.router, prefix="/api/admin/appointments/v1")
URL = "/api/admin/appointments/v1"


@pytest.fixture(scope='module')
def engine():
    with testing.postgresql.Postgresql() as postgresql:
        engine = create_engine(postgresql.url())
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    async def mock_get_current_user():
        return {"user_id": "test-user"}

    app_for_testing.dependency_overrides[get_db] = override_get_db
    app_for_testing.dependency_overrides[get_current_user] = mock_get_current_user
    with TestClient(app_for_testing) as test_client:
        yield test_client
    app_for_testing.dependency_overrides.clear()


def make_code(db, code):
    record = AppointmentCorporateCode(code=code, organization=code, patient_survey={}, corporate_survey={})
    db.add(record)
    db.flush()
    return record


@pytest.fixture
def group(db):
    source = make_code(db, 'SOURCE')
    inventory = SGiMedInventory(
        id='INV1', code='INV1', name='Medical', type='Service', remark=None,
        last_edited=datetime.now(), created_at=datetime.now(), category_id='CAT',
    )
    db.add(inventory)
    group = AppointmentServiceGroup(
        name='Work Permit', title='Work Permit Medical', description='desc', index=3, icon='', duration=30,
        type=AppointmentServiceGroupType.MULTIPLE,
        restricted_branches=['b1'], corporate_code_id=source.id,
    )
    db.add(group)
    db.flush()
    for i, name in enumerate(['New Application (Male)', 'New Application (Female)']):
        db.add(AppointmentService(
            name=name, index=i, group_id=group.id, prepayment_price=10.0, display_price=20.0, sgimed_inventory_id='INV1',
            tests=[{'name': 'Clinical Examination', 'exclusion': ''}, {'name': 'Blood Test', 'exclusion': 'VDRL'}],
        ))
    db.flush()
    return group


def test_duplicate_service_group_to_another_code(client, db, group):
    target = make_code(db, 'TARGET')
    resp = client.post(f"{URL}/service-groups/duplicate", json={'group_ids': [str(group.id)], 'corporate_code_id': str(target.id)})
    assert resp.status_code == 200, resp.text
    [new_id] = resp.json()['ids']
    assert new_id != str(group.id)

    copy = db.query(AppointmentServiceGroup).filter(AppointmentServiceGroup.id == new_id).one()
    assert copy.corporate_code_id == target.id
    for field in ('name', 'title', 'description', 'index', 'duration', 'type', 'restricted_branches', 'category'):
        assert getattr(copy, field) == getattr(group, field), field

    services = sorted(copy.services, key=lambda s: s.index)
    originals = sorted(group.services, key=lambda s: s.index)
    assert [s.name for s in services] == [s.name for s in originals]
    assert [s.tests for s in services] == [s.tests for s in originals]
    assert all(s.sgimed_inventory_id == 'INV1' and s.prepayment_price == 10.0 for s in services)
    assert not {s.id for s in services} & {s.id for s in originals}
    # Original untouched
    db.refresh(group)
    assert group.corporate_code.code == 'SOURCE' and len(group.services) == 2


def test_duplicate_as_general_and_errors(client, db, group):
    resp = client.post(f"{URL}/service-groups/duplicate", json={'group_ids': [str(group.id)], 'corporate_code_id': None})
    assert resp.status_code == 200, resp.text
    copy = db.query(AppointmentServiceGroup).filter(AppointmentServiceGroup.id == resp.json()['ids'][0]).one()
    assert copy.corporate_code_id is None

    assert client.post(f"{URL}/service-groups/duplicate", json={'group_ids': [str(group.id)], 'corporate_code_id': str(uuid.uuid4())}).status_code == 404
    assert client.post(f"{URL}/service-groups/duplicate", json={'group_ids': [str(uuid.uuid4())]}).status_code == 404
    assert client.post(f"{URL}/service-groups/duplicate", json={'group_ids': []}).status_code == 400


def test_reorder_group_keeps_corporate_code(client, db, group):
    resp = client.put(f"{URL}/service-groups/{group.id}", json={'index': 7})
    assert resp.status_code == 200, resp.text
    db.refresh(group)
    assert group.index == 7 and group.corporate_code.code == 'SOURCE'

    # Explicit null still removes the code (edit form clearing the field)
    assert client.put(f"{URL}/service-groups/{group.id}", json={'corporate_code_id': None}).status_code == 200
    db.refresh(group)
    assert group.corporate_code_id is None


def test_reorder_service_keeps_inventory(client, db, group):
    service = group.services[0]
    resp = client.put(f"{URL}/services/{service.id}", json={'index': 5})  # Prepaid service: used to fail with 400
    assert resp.status_code == 200, resp.text
    db.refresh(service)
    assert service.index == 5 and service.sgimed_inventory_id == 'INV1'


def test_corporate_code_max_bookings_per_slot(client, db):
    resp = client.post(f"{URL}/corporate-codes", json={'code': 'SLOTS', 'organization': 'Org', 'max_bookings_per_slot': 2})
    assert resp.status_code == 200, resp.text
    code_id = resp.json()['id']
    assert client.get(f"{URL}/corporate-codes/{code_id}").json()['max_bookings_per_slot'] == 2

    assert client.put(f"{URL}/corporate-codes/{code_id}", json={'organization': 'Org 2'}).status_code == 200
    assert client.get(f"{URL}/corporate-codes/{code_id}").json()['max_bookings_per_slot'] == 2  # Not wiped
    assert client.put(f"{URL}/corporate-codes/{code_id}", json={'max_bookings_per_slot': None}).status_code == 200
    assert client.get(f"{URL}/corporate-codes/{code_id}").json()['max_bookings_per_slot'] is None


def test_corporate_code_validity_can_be_cleared(client, db):
    resp = client.post(f"{URL}/corporate-codes", json={
        'code': 'DATES', 'organization': 'Org', 'valid_from': '2026-01-01T00:00:00+08:00', 'valid_to': '2026-02-01T23:59:59+08:00',
    })
    code_id = resp.json()['id']
    assert client.put(f"{URL}/corporate-codes/{code_id}", json={'valid_from': None, 'valid_to': None}).status_code == 200
    body = client.get(f"{URL}/corporate-codes/{code_id}").json()
    assert body['valid_from'] is None and body['valid_to'] is None


def test_operating_hours_split_round_trip(client, db):
    branch = Branch(id=uuid.uuid4(), name='B', category='Test', branch_type=BranchType.MAIN, deleted=False, hidden=False)
    db.add(branch)
    db.flush()
    payload = {'Saturday': [{
        'start_time': '09:00', 'end_time': '12:00', 'cutoff_time': 0, 'max_bookings': 2,
        'max_appointments_per_session': None, 'max_clinic_bookings': 0, 'max_corporate_bookings': 2,
    }]}
    assert client.put(f"{URL}/operating-hours/{branch.id}", json=payload).status_code == 200
    [hour] = client.get(f"{URL}/operating-hours/{branch.id}").json()['operating_hours']['Saturday']
    assert hour['max_bookings'] == 2 and hour['max_clinic_bookings'] == 0 and hour['max_corporate_bookings'] == 2

    row = db.query(AppointmentBranchOperatingHours).filter(AppointmentBranchOperatingHours.branch_id == branch.id).one()
    assert row.day == DayOfWeek.SATURDAY and row.max_clinic_bookings == 0
