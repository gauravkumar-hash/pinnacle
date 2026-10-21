"""
Clinic / corporate split of appointment slots (Revised appointment workflow):
- max_clinic_bookings / max_corporate_bookings on branch appointment hours split max_bookings per 15 min
- max_bookings_per_slot on a corporate code limits how many of the corporate slots that code can see.
  It is compared against ALL corporate bookings in the slot, so limits of different codes do not stack.
"""
import pytest
import uuid
from datetime import date, datetime, time, timedelta
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import testing.postgresql

from models import Base, Branch, Account, OperatingHour
from models.appointment import (
    Appointment, AppointmentCount, AppointmentCorporateCode, AppointmentServiceGroup, AppointmentService,
    AppointmentBranchOperatingHours,
)
from models.model_enums import (
    AppointmentServiceGroupType, AppointmentStatus, BranchType, DayOfWeek,
    SGiMedICType, SGiMedGender, SGiMedNationality, SGiMedLanguage, PhoneCountryCode,
)
from routers.patient.appointment import calculate_appointment_timings, ensure_slot_allocation, GetAppointmentTimingsReq
from utils.appointment import get_category_full_slots, get_corporate_slot_counts, clear_operating_hours_cache
from utils.sg_datetime import sgtz

T = sgtz.localize(datetime(2031, 3, 3, 9, 0))  # Fixed slot for the unit tests
M15 = timedelta(minutes=15)


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
    clear_operating_hours_cache()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def branch(db):
    branch = Branch(
        id=uuid.uuid4(), name='Test Branch', category='Test', branch_type=BranchType.MAIN,
        sgimed_branch_id='SG_BRANCH', sgimed_calendar_id='SG_CAL', deleted=False, hidden=False,
    )
    db.add(branch)
    db.flush()
    return branch


@pytest.fixture
def account(db):
    account = Account(
        id=uuid.uuid4(), name='John Doe', nric=f'S{uuid.uuid4().hex[:7]}A', mobile_number='12345678',
        ic_type=SGiMedICType.PINK_IC, gender=SGiMedGender.MALE, date_of_birth=date(1990, 1, 1),
        nationality=SGiMedNationality.SINGAPORE_CITIZEN, language=SGiMedLanguage.ENGLISH,
        mobile_code=PhoneCountryCode.SINGAPORE,
    )
    db.add(account)
    db.flush()
    return account


def add_appt(db, branch, account, start, duration=15, code='CODE_A', status=AppointmentStatus.CONFIRMED, group_id=None, index=None):
    appt = Appointment(
        corporate_code=code, services=[], branch={'id': str(branch.id)}, start_datetime=start, duration=duration,
        payment_breakdown={}, status=status, group_id=group_id, index=index, created_by=account.id,
    )
    db.add(appt)
    db.flush()
    return appt


def remaining(db, branch, cap_corporate, code_cap):
    '''Corporate slots a code can still book at T (min of branch corporate cap and code cap, minus all corporate bookings)'''
    counts = get_corporate_slot_counts(db, branch, T, T + M15)
    return min(c for c in (cap_corporate, code_cap) if c is not None) - counts.get(T, 0)


def test_no_split_configured_restricts_nothing(db, branch, account):
    add_appt(db, branch, account, T)
    assert get_category_full_slots(db, branch, {T}, {}, {}, is_corporate=True) == set()
    assert get_category_full_slots(db, branch, {T}, {}, {}, is_corporate=False) == set()


def test_pdf_example_project_limits_do_not_stack(db, branch, account):
    # Clinic gives corporate 3 slots per 15 min; project A=1, B=2, C=3
    max_corporate = {T: 3}

    def full(code_cap):
        return T in get_category_full_slots(db, branch, {T}, {}, max_corporate, True, code_cap)

    add_appt(db, branch, account, T, code='CODE_A')  # 1 slot filled
    assert full(1)          # A sees 0
    assert not full(2)      # B sees 1 more
    assert not full(3)      # C sees 2 more
    assert remaining(db, branch, 3, 1) == 0
    assert remaining(db, branch, 3, 2) == 1
    assert remaining(db, branch, 3, 3) == 2

    add_appt(db, branch, account, T, code='CODE_B')
    assert full(2) and not full(3)
    add_appt(db, branch, account, T, code='CODE_C')
    assert full(3)
    assert full(None)       # Branch corporate cap of 3 reached for any code


def test_clinic_count_is_sgimed_total_minus_corporate(db, branch, account):
    db.add(AppointmentCount(sgimed_branch_id='SG_BRANCH', sgimed_calendar_id='SG_CAL', time=T, count=2))
    add_appt(db, branch, account, T)  # One of the 2 SGiMed bookings is corporate
    db.flush()
    assert get_category_full_slots(db, branch, {T}, {T: 1}, {}, is_corporate=False) == {T}
    assert get_category_full_slots(db, branch, {T}, {T: 2}, {}, is_corporate=False) == set()


def test_zero_blocks_only_that_patient_type(db, branch, account):
    # e.g. Saturdays corporate only
    assert get_category_full_slots(db, branch, {T}, {T: 0}, {}, is_corporate=False) == {T}
    assert get_category_full_slots(db, branch, {T}, {T: 0}, {}, is_corporate=True) == set()


def test_booking_with_several_patients_runs_back_to_back(db, branch, account):
    group_id = str(uuid.uuid4())
    add_appt(db, branch, account, T, duration=15, group_id=group_id, index=0)  # Main (self)
    add_appt(db, branch, account, T, duration=15, group_id=group_id, index=1)  # Family member
    assert get_corporate_slot_counts(db, branch, T, T + 3 * M15) == {T: 1, T + M15: 1}


def test_cancelled_member_keeps_place_and_released_statuses_ignored(db, branch, account):
    group_id = str(uuid.uuid4())
    add_appt(db, branch, account, T, group_id=group_id, index=0)
    add_appt(db, branch, account, T, group_id=group_id, index=1, status=AppointmentStatus.CANCELLED)
    add_appt(db, branch, account, T, group_id=group_id, index=2)
    add_appt(db, branch, account, T, status=AppointmentStatus.PREPAYMENT)
    add_appt(db, branch, account, T, status=AppointmentStatus.PAYMENT_STARTED)
    add_appt(db, branch, account, T, code=None)  # Clinic patient
    assert get_corporate_slot_counts(db, branch, T, T + 3 * M15) == {T: 1, T + 2 * M15: 1}


def test_excluded_appointments_do_not_count(db, branch, account):
    appt = add_appt(db, branch, account, T)
    assert get_category_full_slots(db, branch, {T}, {}, {T: 1}, True, exclude_appointment_ids=[appt.id]) == set()
    assert get_category_full_slots(db, branch, {T}, {}, {T: 1}, True) == {T}


# Integration through /timings and the booking checks
def next_monday(days_ahead=14):
    d = date.today() + timedelta(days=days_ahead)
    return d + timedelta(days=(7 - d.weekday()) % 7)


@pytest.fixture
def setup(db, branch, account):
    day = next_monday()

    def at(h, m):
        return sgtz.localize(datetime.combine(day, time(h, m)))
    db.add(OperatingHour(branch_id=branch.id, day=DayOfWeek.MONDAY, start_time=time(9), end_time=time(10)))
    hours = AppointmentBranchOperatingHours(
        branch_id=branch.id, day=DayOfWeek.MONDAY, start_time=time(9), end_time=time(10),
        max_bookings=2, max_clinic_bookings=1, max_corporate_bookings=1,
    )
    db.add(hours)
    code = AppointmentCorporateCode(code='CODE_A', organization='A', patient_survey={}, corporate_survey={})
    db.add(code)
    db.flush()
    groups = {}
    for name, code_id in (('general', None), ('corporate', code.id)):
        group = AppointmentServiceGroup(
            name=name, index=0, icon='', duration=15, type=AppointmentServiceGroupType.NO_DETAIL, corporate_code_id=code_id,
        )
        db.add(group)
        db.flush()
        service = AppointmentService(name=name, index=0, group_id=group.id, min_booking_ahead_days=2)
        db.add(service)
        db.flush()
        groups[name] = str(service.id)
    # 09:00 clinic booking and 09:15 corporate booking, both already counted by SGiMed
    db.add(AppointmentCount(sgimed_branch_id='SG_BRANCH', sgimed_calendar_id='SG_CAL', time=at(9, 0), count=1))
    db.add(AppointmentCount(sgimed_branch_id='SG_BRANCH', sgimed_calendar_id='SG_CAL', time=at(9, 15), count=1))
    corporate_appt = add_appt(db, branch, account, at(9, 15))
    return dict(day=day, at=at, hours=hours, code=code, services=groups, corporate_appt=corporate_appt)


def timings(db, branch, setup, kind, **kwargs):
    req = GetAppointmentTimingsReq(service_ids=[setup['services'][kind]], num_patients=1, branch_id=str(branch.id), curr_date=setup['day'])
    # Monday hours repeat every week, so keep only the day under test
    return [t for t in calculate_appointment_timings(db, req, **kwargs).timings if t.date() == setup['day']]


def test_timings_split_by_patient_type(db, branch, setup):
    at = setup['at']
    assert timings(db, branch, setup, 'general') == [at(9, 15), at(9, 30), at(9, 45)]
    assert timings(db, branch, setup, 'corporate') == [at(9, 0), at(9, 30), at(9, 45)]
    # Rescheduling the corporate booking frees its own slot
    assert timings(db, branch, setup, 'corporate', exclude_appointment_ids=[setup['corporate_appt'].id]) == [at(9, 0), at(9, 15), at(9, 30), at(9, 45)]


def test_timings_unchanged_without_split(db, branch, setup):
    setup['hours'].max_clinic_bookings = None
    setup['hours'].max_corporate_bookings = None
    db.flush()
    clear_operating_hours_cache()
    at = setup['at']
    expected = [at(9, 0), at(9, 15), at(9, 30), at(9, 45)]  # max_bookings 2, only 1 booked per slot
    assert timings(db, branch, setup, 'general') == expected
    assert timings(db, branch, setup, 'corporate') == expected


def test_code_limit_applies_with_no_branch_corporate_cap(db, branch, setup):
    setup['hours'].max_corporate_bookings = None
    setup['code'].max_bookings_per_slot = 1
    db.flush()
    clear_operating_hours_cache()
    at = setup['at']
    assert timings(db, branch, setup, 'corporate') == [at(9, 0), at(9, 30), at(9, 45)]


def test_ensure_slot_allocation(db, branch, setup):
    at = setup['at']
    ensure_slot_allocation(db, branch, at(9, 0), 15, 'CODE_A')
    with pytest.raises(HTTPException):
        ensure_slot_allocation(db, branch, at(9, 15), 15, 'CODE_A')
    with pytest.raises(HTTPException):
        ensure_slot_allocation(db, branch, at(9, 0), 30, 'CODE_A')  # Second patient lands on 09:15
    with pytest.raises(HTTPException):
        ensure_slot_allocation(db, branch, at(9, 0), 15, None)  # Clinic share used at 09:00
    ensure_slot_allocation(db, branch, at(9, 15), 15, None)
    ensure_slot_allocation(db, branch, at(9, 15), 15, 'CODE_A', exclude_appointment_ids=[setup['corporate_appt'].id])
