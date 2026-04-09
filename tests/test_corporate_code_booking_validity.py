import pytest
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import testing.postgresql

from models import Base, Branch
from models.appointment import AppointmentCorporateCode, AppointmentServiceGroup, AppointmentService, AppointmentOnsiteBranch
from models.model_enums import AppointmentServiceGroupType, BranchType
from routers.patient.appointment import get_minmax_booking_dates
from utils.sg_datetime import sg, sgtz


@pytest.fixture(scope='module')
def db():
    """Create a test database for the module"""
    with testing.postgresql.Postgresql() as postgresql:
        engine = create_engine(postgresql.url())
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()
        yield session
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def sample_branch(db):
    """Create a sample branch for testing"""
    branch = Branch(
        id=uuid.uuid4(),
        name='Test Branch',
        category='Test',
        branch_type=BranchType.CLINIC,
        deleted=False,
        hidden=False
    )
    db.add(branch)
    db.commit()
    return branch


@pytest.fixture
def sample_onsite_branch(db):
    """Create a sample onsite branch for testing"""
    branch = Branch(
        id=uuid.uuid4(),
        name='Test Onsite Branch',
        category='Test',
        branch_type=BranchType.ONSITE,
        deleted=False,
        hidden=False
    )
    db.add(branch)
    db.commit()
    return branch


@pytest.fixture
def sample_corporate_code(db):
    """Create a sample corporate code for testing"""
    now = datetime.now(sgtz)
    corp_code = AppointmentCorporateCode(
        id=uuid.uuid4(),
        code='TEST123',
        organization='Test Organization',
        patient_survey={},
        corporate_survey={},
        only_primary_user=False,
        valid_from=now,
        valid_to=now + relativedelta(months=3),
        is_active=True
    )
    db.add(corp_code)
    db.commit()
    return corp_code


@pytest.fixture
def sample_service_group(db, sample_corporate_code):
    """Create a sample service group linked to corporate code"""
    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='Test Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=sample_corporate_code.id
    )
    db.add(service_group)
    db.commit()
    return service_group


@pytest.fixture
def sample_service(db, sample_service_group):
    """Create a sample service"""
    service = AppointmentService(
        id=uuid.uuid4(),
        name='Test Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=sample_service_group.id
    )
    db.add(service)
    db.commit()
    return service


@pytest.fixture
def sample_service_no_corporate_code(db):
    """Create a service without corporate code link"""
    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='Regular Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=None
    )
    db.add(service_group)
    db.commit()

    service = AppointmentService(
        id=uuid.uuid4(),
        name='Regular Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=service_group.id
    )
    db.add(service)
    db.commit()
    return service


def test_get_minmax_booking_dates_no_corporate_code(db, sample_branch, sample_service_no_corporate_code):
    """Test that get_minmax_booking_dates returns 6 months when no corporate code is provided"""
    base_date = datetime.now(sgtz)
    expected_min_date = base_date + timedelta(hours=2 * 24 + 1)
    expected_max_date = base_date + relativedelta(months=6)

    min_date, max_date = get_minmax_booking_dates(
        db, base_date, [str(sample_service_no_corporate_code.id)], str(sample_branch.id)
    )

    # Compare dates (ignoring microseconds)
    assert min_date.date() == expected_min_date.date()
    assert max_date.date() == expected_max_date.date()


def test_get_minmax_booking_dates_with_corporate_code_shorter_validity(db, sample_branch, sample_service, sample_corporate_code):
    """Test that get_minmax_booking_dates returns 6 months even when corporate code expires before 6 months"""
    base_date = datetime.now(sgtz)
    expected_min_date = base_date + timedelta(hours=2 * 24 + 1)
    expected_max_date = base_date + relativedelta(months=6)  # Should use default 6 months, not corporate code validity

    # Service is linked to corporate code, so it should extract it automatically
    min_date, max_date = get_minmax_booking_dates(
        db, base_date, [str(sample_service.id)], str(sample_branch.id)
    )

    # The result should be the default 6 months, NOT the corporate code's valid_to date
    # Corporate code validity no longer restricts max booking date
    assert min_date.date() == expected_min_date.date()
    assert max_date.date() == expected_max_date.date()


def test_get_minmax_booking_dates_with_corporate_code_longer_validity(db, sample_branch):
    """Test that get_minmax_booking_dates returns 6 months when corporate code expires after 6 months"""
    now = datetime.now(sgtz)
    corp_code = AppointmentCorporateCode(
        id=uuid.uuid4(),
        code='LONGVALID',
        organization='Long Validity Test',
        patient_survey={},
        corporate_survey={},
        only_primary_user=False,
        valid_from=now,
        valid_to=now + relativedelta(months=12),  # Expires after 6 months
        is_active=True
    )
    db.add(corp_code)

    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='Long Valid Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=corp_code.id
    )
    db.add(service_group)

    service = AppointmentService(
        id=uuid.uuid4(),
        name='Long Valid Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=service_group.id
    )
    db.add(service)
    db.commit()

    base_date = datetime.now(sgtz)
    expected_max_date = base_date + relativedelta(months=6)

    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(service.id)], str(sample_branch.id)
    )

    # The result should be 6 months, not the corporate code's valid_to
    assert max_date.date() == expected_max_date.date()


def test_get_minmax_booking_dates_with_corporate_code_no_end_date(db, sample_branch):
    """Test that get_minmax_booking_dates returns 6 months when corporate code has no end date"""
    now = datetime.now(sgtz)
    corp_code = AppointmentCorporateCode(
        id=uuid.uuid4(),
        code='TESTNOEND',
        organization='Test Organization No End',
        patient_survey={},
        corporate_survey={},
        only_primary_user=False,
        valid_from=now,
        valid_to=None,
        is_active=True
    )
    db.add(corp_code)

    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='No End Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=corp_code.id
    )
    db.add(service_group)

    service = AppointmentService(
        id=uuid.uuid4(),
        name='No End Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=service_group.id
    )
    db.add(service)
    db.commit()

    base_date = datetime.now(sgtz)
    expected_max_date = base_date + relativedelta(months=6)

    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(service.id)], str(sample_branch.id)
    )

    # The result should be 6 months since there's no valid_to date
    assert max_date.date() == expected_max_date.date()


def test_get_minmax_booking_dates_with_onsite_end_date(db, sample_onsite_branch, sample_service_no_corporate_code):
    """Test that get_minmax_booking_dates respects onsite branch end date"""
    base_date = datetime.now(sgtz)
    onsite_end_date = base_date + relativedelta(months=2)  # Ends in 2 months

    # Create onsite branch record
    onsite_record = AppointmentOnsiteBranch(
        branch_id=sample_onsite_branch.id,
        start_date=base_date,
        end_date=onsite_end_date
    )
    db.add(onsite_record)
    db.commit()

    min_date, max_date = get_minmax_booking_dates(
        db, base_date, [str(sample_service_no_corporate_code.id)], str(sample_onsite_branch.id)
    )

    # The result should be the onsite end date (2 months), not 6 months
    assert max_date.date() == sg(onsite_end_date).date()


def test_get_minmax_booking_dates_with_both_corporate_and_onsite(db, sample_onsite_branch, sample_service, sample_corporate_code):
    """Test that get_minmax_booking_dates returns the most restrictive date when both corporate code and onsite are provided"""
    base_date = datetime.now(sgtz)
    onsite_end_date = base_date + relativedelta(months=1)  # Ends in 1 month (more restrictive)

    # Create onsite branch record
    onsite_record = AppointmentOnsiteBranch(
        branch_id=sample_onsite_branch.id,
        corporate_code_id=sample_corporate_code.id,
        start_date=base_date,
        end_date=onsite_end_date
    )
    db.add(onsite_record)
    db.commit()

    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(sample_service.id)], str(sample_onsite_branch.id)
    )

    # The result should be the onsite end date (1 month), the most restrictive
    assert max_date.date() == sg(onsite_end_date).date()


def test_get_minmax_booking_dates_with_explicit_corporate_code(db, sample_branch, sample_service_no_corporate_code, sample_corporate_code):
    """Test that get_minmax_booking_dates ignores corporate code validity period"""
    base_date = datetime.now(sgtz)
    expected_max_date = base_date + relativedelta(months=6)  # Should use default 6 months

    # Pass corporate code explicitly even though service has no corporate code
    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(sample_service_no_corporate_code.id)], str(sample_branch.id), sample_corporate_code.code
    )

    # The result should be 6 months, NOT the corporate code's valid_to date
    assert max_date.date() == expected_max_date.date()


def test_get_minmax_booking_dates_case_insensitive(db, sample_branch, sample_service_no_corporate_code, sample_corporate_code):
    """Test that get_minmax_booking_dates ignores corporate code validity regardless of case"""
    base_date = datetime.now(sgtz)
    expected_max_date = base_date + relativedelta(months=6)  # Should use default 6 months

    # Use lowercase code
    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(sample_service_no_corporate_code.id)], str(sample_branch.id), 'test123'
    )

    # The result should be 6 months, NOT the corporate code's valid_to date
    assert max_date.date() == expected_max_date.date()


def test_get_minmax_booking_dates_expired_corporate_code(db, sample_branch):
    """Test that get_minmax_booking_dates ignores expired corporate codes"""
    now = datetime.now(sgtz)
    corp_code = AppointmentCorporateCode(
        id=uuid.uuid4(),
        code='EXPIRED',
        organization='Expired Test',
        patient_survey={},
        corporate_survey={},
        only_primary_user=False,
        valid_from=now - relativedelta(months=3),
        valid_to=now - relativedelta(days=1),  # Expired yesterday
        is_active=True
    )
    db.add(corp_code)

    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='Expired Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=corp_code.id
    )
    db.add(service_group)

    service = AppointmentService(
        id=uuid.uuid4(),
        name='Expired Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=service_group.id
    )
    db.add(service)
    db.commit()

    base_date = datetime.now(sgtz)
    expected_max_date = base_date + relativedelta(months=6)

    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(service.id)], str(sample_branch.id)
    )

    # Since the corporate code is expired, should fall back to 6-month default
    assert max_date.date() == expected_max_date.date()


def test_get_minmax_booking_dates_onsite_min_date(db, sample_onsite_branch, sample_service_no_corporate_code):
    """Test that get_minmax_booking_dates respects onsite branch start date for min_date"""
    base_date = datetime.now(sgtz)
    onsite_start_date = base_date + relativedelta(days=5)  # Starts in 5 days
    onsite_end_date = base_date + relativedelta(months=2)

    # Create onsite branch record
    onsite_record = AppointmentOnsiteBranch(
        branch_id=sample_onsite_branch.id,
        start_date=onsite_start_date,
        end_date=onsite_end_date
    )
    db.add(onsite_record)
    db.commit()

    min_date, _ = get_minmax_booking_dates(
        db, base_date, [str(sample_service_no_corporate_code.id)], str(sample_onsite_branch.id)
    )

    # The min_date should be the onsite start date (5 days from now)
    assert min_date.date() == sg(onsite_start_date).date()


def test_get_minmax_booking_dates_with_service_group_end_date(db, sample_branch):
    """Test that get_minmax_booking_dates respects service group end date"""
    base_date = datetime.now(sgtz)
    service_group_end_date = base_date + relativedelta(months=2)  # Ends in 2 months

    # Create service group with end date
    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='Limited Time Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=None,
        end_date=service_group_end_date
    )
    db.add(service_group)

    service = AppointmentService(
        id=uuid.uuid4(),
        name='Limited Time Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=service_group.id
    )
    db.add(service)
    db.commit()

    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(service.id)], str(sample_branch.id)
    )

    # The result should be the service group end date (2 months), not 6 months
    assert max_date.date() == sg(service_group_end_date).date()


def test_get_minmax_booking_dates_with_service_group_start_date(db, sample_branch):
    """Test that get_minmax_booking_dates respects service group start date"""
    base_date = datetime.now(sgtz)
    service_group_start_date = base_date + relativedelta(days=7)  # Starts in 7 days
    service_group_end_date = base_date + relativedelta(months=3)

    # Create service group with start date
    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='Future Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=None,
        start_date=service_group_start_date,
        end_date=service_group_end_date
    )
    db.add(service_group)

    service = AppointmentService(
        id=uuid.uuid4(),
        name='Future Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=service_group.id
    )
    db.add(service)
    db.commit()

    min_date, _ = get_minmax_booking_dates(
        db, base_date, [str(service.id)], str(sample_branch.id)
    )

    # The min_date should be the service group start date (7 days from now)
    assert min_date.date() == sg(service_group_start_date).date()


def test_get_minmax_booking_dates_with_multiple_constraints(db, sample_branch):
    """Test that get_minmax_booking_dates uses the most restrictive date across all constraints"""
    base_date = datetime.now(sgtz)

    # Create corporate code (3 months validity)
    corp_code = AppointmentCorporateCode(
        id=uuid.uuid4(),
        code='MULTI',
        organization='Multi Constraint Test',
        patient_survey={},
        corporate_survey={},
        only_primary_user=False,
        valid_from=base_date,
        valid_to=base_date + relativedelta(months=3),
        is_active=True
    )
    db.add(corp_code)

    # Create service group with end date (2 months - most restrictive)
    service_group = AppointmentServiceGroup(
        id=uuid.uuid4(),
        name='Multi Constraint Service Group',
        icon='test.png',
        duration=30,
        type=AppointmentServiceGroupType.SINGLE,
        index=0,
        corporate_code_id=corp_code.id,
        end_date=base_date + relativedelta(months=2)
    )
    db.add(service_group)

    service = AppointmentService(
        id=uuid.uuid4(),
        name='Multi Constraint Service',
        prepayment_price=0.0,
        display_price=50.0,
        index=0,
        min_booking_ahead_days=2,
        group_id=service_group.id
    )
    db.add(service)
    db.commit()

    _, max_date = get_minmax_booking_dates(
        db, base_date, [str(service.id)], str(sample_branch.id)
    )

    # The result should be the service group end date (2 months) - the most restrictive
    # Corporate code validity (3 months) no longer affects max date, so it's compared against default (6 months)
    assert max_date.date() == sg(service_group.end_date).date()
    assert max_date < base_date + relativedelta(months=6)
