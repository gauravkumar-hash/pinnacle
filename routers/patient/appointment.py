from datetime import date, datetime, time, timedelta
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import Any, List, Literal, Optional
from pydantic import BaseModel
from config import SGIMED_GST_RATE
from models import get_db, Account, Branch
from models.appointment import Appointment, AppointmentCorporateCode, AppointmentServiceGroup, AppointmentService, AppointmentOnsiteBranch, PaymentBreakdownCol, PaymentBreakdownItemCol, ServiceGroupCol, ServiceItemCol, BranchCol, GuestCol
from models.model_enums import AppointmentServiceGroupType, AppointmentStatus, BranchType, FileViewerType
from repository.appointment import get_grouped_appointments
from routers.patient.utils import validate_user
from models.payments import Payment, PaymentMethod
from services.appointment import appointment_success_webhook
from services.teleconsult import get_corporate_membership
from services.visits import get_invoice_document_html
from utils.integrations.sgimed_appointment import update_appointment_start_datetime, update_appointment_status
from utils import sg_datetime
from utils.sg_datetime import sg, sgtz
from utils.fastapi import SuccessResp
from utils.appointment import get_appointment_operating_hours, get_appointment_booked_slots, get_available_slots
from dateutil.relativedelta import relativedelta
from repository.payments import create_appointment_payment, get_default_payment
from .teleconsult_family import DocumentDict
from repository.appointment import AppointmentRow, process_grouped_appts

router = APIRouter(dependencies=[Depends(validate_user)])

def get_minmax_booking_dates(
    db: Session,
    base_date: datetime,
    service_ids: list[str],
    branch_id: str,
) -> tuple[datetime, datetime]:
    """
    Calculate minimum and maximum booking dates considering:
    - 2-day minimum booking ahead (default)
    - 6-month default limit
    - Service group date range (if applicable)
    - Onsite branch date range (if applicable)

    Note: Corporate code validity period does NOT restrict max booking date.
    Bookings can extend beyond corporate code expiry if service group allows it.

    Returns tuple of (min_date, max_date) with the most restrictive dates.
    """
    # Calculate minimum booking ahead days from services and get service groups
    services = db.query(AppointmentService.min_booking_ahead_days, AppointmentService.group_id).filter(
        AppointmentService.id.in_(service_ids)
    ).all()
    min_booking_ahead_days = max([row[0] for row in services]) if services else 2

    # Min date: base_date + min_booking_ahead_days + 1 hour buffer
    min_date = base_date + timedelta(hours=min_booking_ahead_days * 24 + 1)

    # Max date: Start with 6-month default
    max_date = base_date + relativedelta(months=6)

    # Get service groups to check for date constraints
    if services:
        service_group_ids = set([row[1] for row in services])
        service_groups = db.query(AppointmentServiceGroup).filter(
            AppointmentServiceGroup.id.in_(service_group_ids)
        ).all()

        # Apply service group date constraints
        for service_group in service_groups:
            if service_group.start_date:
                start_date_sg = sg(service_group.start_date)
                if start_date_sg >= base_date:
                    min_date = max(min_date, start_date_sg)

            if service_group.end_date:
                end_date_sg = sg(service_group.end_date)
                if end_date_sg >= base_date:
                    max_date = min(max_date, end_date_sg)

    # Corporate code validity period is no longer used to restrict max booking date
    # This allows bookings to extend beyond corporate code expiry based on service group end_date

    # Check if branch is onsite and apply onsite restrictions
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if branch and branch.branch_type == BranchType.ONSITE:
        onsite_branch = db.query(AppointmentOnsiteBranch).filter(
            AppointmentOnsiteBranch.branch_id == branch.id,
        ).first()
        if onsite_branch:
            onsite_start_sg = sg(onsite_branch.start_date)
            onsite_end_sg = sg(onsite_branch.end_date)

            # Apply onsite restrictions
            min_date = max(min_date, onsite_start_sg)
            max_date = min(max_date, onsite_end_sg)

    # Set max_date to 23:59:59 SGT
    max_date = max_date.replace(hour=23, minute=59, second=59, microsecond=0)

    return min_date, max_date

def get_corporate_code(code: str, db: Session = Depends(get_db)):
    curr_time = sg_datetime.now()
    record = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.code == code.upper(),
        AppointmentCorporateCode.valid_from <= curr_time,
        AppointmentCorporateCode.valid_to >= curr_time,
        AppointmentCorporateCode.is_active == True
    ).first()
    if not record:
        raise HTTPException(404, "Invalid Corporate/Student Code")

    return record

class ValidateCorporateCodeResp(BaseModel):
    code: str
    organization: str
    patient_survey_template: list[str] | None
    corporate_survey_template: dict | None
    only_primary_user: bool

@router.get("/validate_corporate_code", response_model=ValidateCorporateCodeResp)
def validate_corporate_code(code: str, db: Session = Depends(get_db)):
    record = get_corporate_code(code, db)
    return ValidateCorporateCodeResp(
        code=record.code,
        organization=record.organization,
        patient_survey_template=record.patient_survey.get('patient', None),
        corporate_survey_template=record.corporate_survey if record.corporate_survey else None,
        only_primary_user=record.only_primary_user
    )

class DeeplinkResp(BaseModel):
    redirect_pathname: Literal['/profile/yuu'] | None = None

@router.get('/deeplink', response_model=DeeplinkResp)
def deeplink_check(code: str, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    if code == 'YUU' and not user.yuu_link:
        return DeeplinkResp(redirect_pathname='/profile/yuu')

    return DeeplinkResp(redirect_pathname=None)

class TestItem(BaseModel):
    name: str
    exclusion: str

class ServiceItem(BaseModel):
    id: str
    name: str
    remarks: str | None = None
    price: Optional[float]
    tests: Optional[list[TestItem]]

class ServiceGroup(BaseModel):
    id: str
    name: str
    title: str | None = None # Used as Title when displaying services. If None, use name as title.
    icon: str
    duration: int
    default_item: Optional[ServiceItem] = None

class ServiceResp(BaseModel):
    services: List[ServiceGroup]

@router.get("/services", response_model=ServiceResp)
def get_services(code: Optional[str] = None, branch_ids: Optional[str] = None, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    qry = db.query(AppointmentServiceGroup)
    if code:
        corp_code_record = get_corporate_code(code, db)
        qry = qry.filter(AppointmentServiceGroup.corporate_code_id == corp_code_record.id)
    else:
        membership = get_corporate_membership(str(user.id))
        qry = qry.filter(AppointmentServiceGroup.corporate_code_id == None)
        if membership:
            qry = qry.filter(
                or_(
                    AppointmentServiceGroup.restricted_memberships == [],
                    AppointmentServiceGroup.restricted_memberships.any(membership.code) # type: ignore
                )
            )
        else:
            qry = qry.filter(AppointmentServiceGroup.restricted_memberships == [])

    # Filter by branch_ids if provided
    if branch_ids:
        branch_id_list = branch_ids.split(',')
        qry = qry.filter(
            or_(
                # Show if restricted_branches is empty (no inclusion restriction)
                AppointmentServiceGroup.restricted_branches == [],
                # OR if branch matches restricted_branches (inclusion list)
                AppointmentServiceGroup.restricted_branches.bool_op('&&')(branch_id_list)
            ),
            or_(
                # Show if unsupported_branches is empty (no exclusion restriction)
                AppointmentServiceGroup.unsupported_branches == [],
                # OR if branch does NOT match unsupported_branches (exclusion list)
                ~AppointmentServiceGroup.unsupported_branches.bool_op('&&')(branch_id_list)
            )
        )

    services = qry.order_by(AppointmentServiceGroup.index).all()

    def get_no_detail_service_id(service: AppointmentServiceGroup):
        if service.type != AppointmentServiceGroupType.NO_DETAIL:
            return None

        record = db.query(AppointmentService).filter(
            AppointmentService.group_id == service.id
        ).first()
        if not record:
            return None

        return ServiceItem(
            id=str(record.id),
            name='',
            price=record.display_price,
            tests=[
                TestItem(name=test['name'], exclusion=test['exclusion'])
                for test in record.tests
            ] if record.tests else None
        )

    rows = [
        ServiceGroup(
            id=str(service.id),
            name=service.name,
            title=service.title,
            icon=service.icon,
            duration=service.duration,
            default_item=get_no_detail_service_id(service)
        )
        for service in services
    ]
    return ServiceResp(
        services=rows
    )

class GetServiceResp(BaseModel):
    type: AppointmentServiceGroupType
    id: str
    icon: str
    title: str
    description: Optional[str] = None
    services: List[ServiceItem]

@router.get("/service/{id}", response_model=GetServiceResp)
def get_service(id: str, branch_ids: Optional[str] = None, db: Session = Depends(get_db)):
    service_group = db.query(AppointmentServiceGroup).filter(
        AppointmentServiceGroup.id == id
    ).first()
    if not service_group:
        raise HTTPException(404, "Service group not found")

    services_qry = db.query(AppointmentService).filter(
        AppointmentService.group_id == id
    )

    # Filter by branch_ids if provided
    branch_id_list: list[str] = []
    if branch_ids:
        branch_id_list = branch_ids.split(',')
        services_qry = services_qry.filter(
            or_(
                # Show if restricted_branches is empty (no inclusion restriction)
                AppointmentService.restricted_branches == [],
                # OR if branch matches restricted_branches (inclusion list)
                AppointmentService.restricted_branches.bool_op('&&')(branch_id_list)
            ),
            or_(
                # Show if unsupported_branches is empty (no exclusion restriction)
                AppointmentService.unsupported_branches == [],
                # OR if branch does NOT match unsupported_branches (exclusion list)
                ~AppointmentService.unsupported_branches.bool_op('&&')(branch_id_list)
            )
        )

    services = services_qry.order_by(AppointmentService.index).all()

    def get_service_remarks(service: AppointmentService, branch_id_list: list[str]):
        additional_info = []
        if service.prepayment_price > 0:
            additional_info.append('Prepayment Required')
        if service.restricted_branches:
            branches = db.query(Branch).filter(
                Branch.id.in_(service.restricted_branches),
                Branch.id.not_in(branch_id_list)
            ).all()
            if branches:
                additional_info.append('Available in ' + ', '.join([branch.name for branch in branches]) + ' only')

        if additional_info:
            return ', '.join(additional_info)
        return None

    return GetServiceResp(
        id=str(service_group.id),
        type=service_group.type,
        icon=service_group.icon,
        title=service_group.title if service_group.title else service_group.name,
        description=service_group.description,
        services=[
            ServiceItem(
                id=str(service.id),
                name=service.name,
                remarks=get_service_remarks(service, branch_id_list),
                price=service.display_price,
                tests=[
                    TestItem(name=test['name'], exclusion=test['exclusion'])
                    for test in service.tests
                ] if service.tests else None
            )
            for service in services
        ]
    )

class GetLocationsReq(BaseModel):
    code: Optional[str] = None
    services: list[str]
    branch_ids: Optional[list[str]] = None

class ApptBranch(BaseModel):
    id: str
    header: Optional[str] = None
    name: str
    category: str
    branch_type: str

class GetLocationsResp(BaseModel):
    type: Literal['onsite', 'clinic']
    header: Optional[str] = None
    branches: list[ApptBranch]

@router.post("/locations", response_model=GetLocationsResp)
def get_locations(req: GetLocationsReq, db: Session = Depends(get_db)):
    if req.code:
        corp_code_record = get_corporate_code(req.code, db)

        # Onsite Locations by Code and check end date is at least 2 days from now
        onsite_branches = db.query(AppointmentOnsiteBranch.branch_id, AppointmentOnsiteBranch.start_date, AppointmentOnsiteBranch.end_date).filter(
            AppointmentOnsiteBranch.corporate_code_id == corp_code_record.id,
            AppointmentOnsiteBranch.end_date >= (sg_datetime.now() + timedelta(days=2)),
        ).all()

        # Check if there are onsite branches available, if not, return clinic locations
        branch_ids = [row[0] for row in onsite_branches]
        if branch_ids:
            branches = db.query(Branch).filter(
                Branch.id.in_(branch_ids)
            ).all()

            def get_onsite_start_end_date(row):
                start_date = row[1].astimezone(sgtz).strftime("%d %b %Y")
                end_date = row[2].astimezone(sgtz).strftime("%d %b %Y")
                onsite_start_end_date = f'{start_date} - {end_date}'
                if start_date == end_date:
                    onsite_start_end_date = start_date
                return onsite_start_end_date

            onsite_start_end_dates = {
                row[0]: f'**Available from: {get_onsite_start_end_date(row)}**'
                for row in onsite_branches
            }

            start_date = min([row[1] for row in onsite_branches]).astimezone(sgtz).strftime("%d %b %Y")
            end_date = max([row[2] for row in onsite_branches]).astimezone(sgtz).strftime("%d %b %Y")
            onsite_min_max_date = f'{start_date} - {end_date}'
            if start_date == end_date:
                onsite_min_max_date = start_date

            return GetLocationsResp(
                type='onsite',
                header=f'Onsite services are available from\n**{onsite_min_max_date}**',
                branches=[
                    ApptBranch(
                        id=str(branch.id),
                        header=onsite_start_end_dates[branch.id],
                        name=branch.name,
                        category=branch.category,
                        branch_type=branch.branch_type.value,
                    ) for branch in branches
                ]
            )

    # Limited Locations due to Services Selected
    restricted_branches = set()
    unsupported_branches = set()
    if req.services:
        # Get services and groups 
        services = db.query(
            AppointmentService.restricted_branches,
            AppointmentService.unsupported_branches,
            AppointmentService.group_id,
        ).filter(
            AppointmentService.id.in_(req.services)
        ).all()
        groups = db.query(
            AppointmentServiceGroup.restricted_branches,
            AppointmentServiceGroup.unsupported_branches
        ).filter(
            AppointmentServiceGroup.id.in_(set([row[2] for row in services]))
        ).all()

        # Update restricted_branches and unsupported_branches        
        for row in services:
            if row[0]:  # restricted_branches
                restricted_branches.update(row[0])
            if row[1]:  # unsupported_branches
                unsupported_branches.update(row[1])
        for row in groups:
            if row[0]:  # restricted_branches
                restricted_branches.update(row[0])
            if row[1]:  # unsupported_branches
                unsupported_branches.update(row[1])

    # All Locations, if restricted, even hidden also display else only show non hidden branches
    qry = db.query(Branch).filter(Branch.deleted == False)
    effective_branches = list(restricted_branches - unsupported_branches)
    if restricted_branches and not effective_branches:
        logging.error(f"No effective branches found for appointment services: {req.services}. Restricted branches: {restricted_branches}, Unsupported branches: {unsupported_branches}")

    # Calculate effective branches: restricted minus unsupported
    if effective_branches:        
        qry = qry.filter(Branch.id.in_(effective_branches))
    else:
        qry = qry.filter(Branch.hidden == False)

    # Apply branch_ids filter if provided
    if req.branch_ids:
        qry = qry.filter(Branch.id.in_(req.branch_ids))

    branches = qry.all()
    return GetLocationsResp(
        type='clinic',
        branches=[
            ApptBranch(
                id=str(branch.id),
                name=branch.name,
                category=branch.category,
                branch_type=branch.branch_type.value,
            ) for branch in branches
        ]
    )

class GetPatientSurveyResp(BaseModel):
    patient_survey: list[str] | None
# DEPRECATED: Use /validate_corporate_code instead
@router.get("/patient_survey", response_model=GetPatientSurveyResp)
def get_patient_survey(code: str, db: Session = Depends(get_db)):
    try:
        if not code or not code.strip():
            return GetPatientSurveyResp(patient_survey=None)
        corp_code_record = get_corporate_code(code, db)
        return GetPatientSurveyResp(patient_survey=corp_code_record.patient_survey.get('patient', None))
    except Exception as e:
        logging.error(f"Unexpected Exception: Get Patient Survey Fields - {code}. {e}", exc_info=True)
        return GetPatientSurveyResp(patient_survey=None)

class GetAppointmentTimingsReq(BaseModel):
    service_ids: list[str]
    num_patients: int
    branch_id: str
    curr_date: date

class GetAppointmentTimingsResp(BaseModel):
    min_date: datetime
    max_date: datetime
    timings: list[datetime]

@router.post("/timings", response_model=GetAppointmentTimingsResp)
def get_appointment_timings(req: GetAppointmentTimingsReq, db: Session = Depends(get_db)):
    curr_dt = sg_datetime.now()

    # Get min and max booking dates using the helper function
    min_date, max_date = get_minmax_booking_dates(
        db, curr_dt, req.service_ids, req.branch_id
    )

    # Calculate Service Duration Required
    services = db.query(AppointmentService.group_id).filter(
        AppointmentService.id.in_(req.service_ids)
    ).all()
    service_groups = db.query(AppointmentServiceGroup.duration).filter(
        AppointmentServiceGroup.id.in_(set([row[0] for row in services]))
    ).all()
    service_duration = sum([row[0] for row in service_groups]) * req.num_patients

    # Get the start and end of the month
    start_of_month = sgtz.localize(datetime.combine(req.curr_date.replace(day=1), datetime.min.time()))
    end_of_month = start_of_month + relativedelta(months=1, seconds=-1)
    # Get the start and end date to retrieve available slots
    start_date = max(min_date, start_of_month)
    end_date = min(max_date, end_of_month)

    start_date = sgtz.localize(datetime.combine(start_date, time.min))
    end_date = sgtz.localize(datetime.combine(end_date, time.max))

    # Get branch for slot calculation
    branch = db.query(Branch).filter(Branch.id == req.branch_id).first()
    if not branch:
        raise Exception("Branch not found")

    # Get Available Appointment Slots
    available_slots, appt_operating_hours_discrete_max_bookings = get_appointment_operating_hours(db, branch, start_date, end_date)
    available_slots = set(filter(lambda x: x >= start_date and x <= end_date, available_slots))
    if len(available_slots) == 0:
        return GetAppointmentTimingsResp(
            min_date=min_date,
            max_date=max_date,
            timings=[]
        )
    booked_slots = get_appointment_booked_slots(db, branch, start_date, end_date, available_slots, appt_operating_hours_discrete_max_bookings)
    max_date_with_time = max_date.replace(hour=23, minute=59, second=59)
    start_timings = get_available_slots(available_slots - booked_slots, service_duration)
    start_timings = [timing for timing in start_timings if timing > min_date and timing < max_date_with_time]

    return GetAppointmentTimingsResp(
        min_date=min_date,
        max_date=max_date,
        timings=start_timings
    )

class ServiceGroupItems(BaseModel):
    id: str
    items: list[str]

class GuestInfo(BaseModel):
    id: str
    name: str
    mobile: str

class PatientInfo(BaseModel):
    type: Literal['myself', 'family', 'guest']
    # Used for family
    id: Optional[str] = None
    # Used for guest
    name: Optional[str] = None
    mobile: Optional[str] = None

class GetPriceBreakdownReq(BaseModel):
    code: Optional[str] = None
    affiliate_code: Optional[str] = None
    service_groups: list[ServiceGroupItems]
    patients: list[PatientInfo]
    branch_id: str
    start_dt: datetime
    patient_survey: Optional[dict] = None
    corporate_survey: Optional[dict] = None

class PriceBreakdownItem(BaseModel):
    title: str
    amount: float

class GetPriceBreakdownResp(BaseModel):
    id: str
    items: list[PriceBreakdownItem]
    gst: float
    total: float

@router.post("/review", response_model=GetPriceBreakdownResp)
def get_price(req: GetPriceBreakdownReq, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    # Delete any prepayment appointments
    db.query(Appointment).filter(
        Appointment.status == AppointmentStatus.PREPAYMENT,
        Appointment.created_by == user.id,
    ).delete()

    # Check Code
    corporate_code_id = None
    corporate_code = None
    corporate_code_record = None
    if req.code:
        corporate_code_record = get_corporate_code(req.code, db)
        corporate_code_id = corporate_code_record.id
        corporate_code = corporate_code_record.code
    # Check Branch
    branch = db.query(Branch).filter(Branch.id == req.branch_id).first()
    if not branch:
        raise HTTPException(400, "Invalid branch")
    service_groups = db.query(AppointmentServiceGroup).filter(
        AppointmentServiceGroup.id.in_(set([row.id for row in req.service_groups])),
        AppointmentServiceGroup.corporate_code_id == corporate_code_id
    ).all()
    if len(service_groups) != len(req.service_groups):
        raise HTTPException(400, "Invalid services")

    service_ids = [service_id for row in req.service_groups for service_id in row.items]
    services = db.query(AppointmentService).filter(
        AppointmentService.id.in_(service_ids)
    ).all()
    if len(services) != len(service_ids):
        raise HTTPException(400, "Invalid services")

    # Check Start Date - use new helper with service_ids
    start_dt = req.start_dt
    min_date, max_date = get_minmax_booking_dates(
        db, sg_datetime.now(), service_ids, req.branch_id
    )
    if start_dt < min_date or start_dt > max_date:
        raise HTTPException(400, f"Start date must be between {min_date.strftime('%d %b %Y')} and {max_date.strftime('%d %b %Y')}")

    # Convert to dicts
    service_duration = sum([row.duration for row in service_groups])
    service_groups = {str(row.id): row for row in service_groups}
    services = {str(row.id): row for row in services}

    include_self = bool(next(filter(lambda x: x.type == 'myself', req.patients), None))
    guests = [row for row in req.patients if row.type == 'guest']
    family_members = [row.id for row in req.patients if row.type == 'family']

    # Check only_primary_user restriction
    if corporate_code_record and corporate_code_record.only_primary_user and family_members:
        raise HTTPException(400, "This corporate code is restricted to primary users only. Family members cannot be included.")

    # Create JSON dicts for database
    services = [
        ServiceGroupCol(
            id=service_group.id,
            name=service_groups[service_group.id].name,
            items=[
                ServiceItemCol(
                    id=service_id,
                    name=services[service_id].name,
                    prepayment_price=services[service_id].prepayment_price,
                    display_price=services[service_id].display_price,
                )
                for service_id in service_group.items
            ]
        )
        for service_group in req.service_groups
    ]
    branch_col = BranchCol(
        id=str(branch.id),
        sgimed_branch_id=branch.sgimed_branch_id or '',
        sgimed_appointment_type_id=branch.sgimed_appointment_type_id or '',
        name=branch.name,
        address=branch.address or '',
        url=branch.url or ''
    )

    # Create Payment Items
    payment_items = [
        PaymentBreakdownItemCol(
            title='**' + service_group.name + '**\n' + service.name,
            amount=round(service.prepayment_price, 2)
        )
        for service_group in services
        for service in service_group.items
        if service.prepayment_price > 0
    ]
    payment_total = sum([service.prepayment_price for service_group in services for service in service_group.items])
    payment_gst = round(payment_total * float(SGIMED_GST_RATE), 2)
    payment_total = payment_total + payment_gst
    group_id = str(uuid.uuid4()) if family_members else None

    # Create Appointment Record for self and guests
    self_guests_cnt = len(guests) + int(include_self)
    total_pax = self_guests_cnt + len(family_members)
    payment_breakdown = PaymentBreakdownCol(
        items=[
            PaymentBreakdownItemCol(
                title=item.title + f" ({total_pax}x)",
                amount=round(item.amount * total_pax, 2)
            )
            for item in payment_items
        ],
        gst=round(payment_gst * total_pax, 2),
        total=round(payment_total * total_pax, 2),
    )
    main_appt = Appointment(
        affiliate_code=req.affiliate_code,
        corporate_code=corporate_code,
        services=[s.model_dump() for s in services],
        account_id=user.id if include_self else None,
        guests=[
            GuestCol(
                name=row.name or '',
                mobile=row.mobile or ''
            ).model_dump()
            for row in guests
        ],
        branch=branch_col.model_dump(),
        start_datetime=start_dt,
        duration=service_duration * self_guests_cnt,
        # Main person paying should be able to see the full breakdown of all payments
        payment_breakdown=payment_breakdown.model_dump(),
        status=AppointmentStatus.PREPAYMENT,
        group_id=group_id,
        created_by=user.id,
        index=0 if family_members else None,
        patient_survey=req.patient_survey.get('myself', None) if corporate_code and req.patient_survey else None,
        corporate_survey=req.corporate_survey.get('myself', None) if corporate_code and req.corporate_survey else None,
    )
    db.add(main_appt)

    # Create Appointment Records for family members
    for i, account_id in enumerate(family_members):
        sub_appt = Appointment(
            corporate_code=corporate_code,
            services=main_appt.services,
            account_id=account_id,
            branch=main_appt.branch,
            start_datetime=start_dt,
            duration=service_duration,
            payment_breakdown=main_appt.payment_breakdown,
            status=AppointmentStatus.PREPAYMENT,
            group_id=group_id,
            created_by=user.id,
            index=i+1,
            patient_survey=req.patient_survey.get(str(account_id), None) if corporate_code and req.patient_survey else None,
            corporate_survey=req.corporate_survey.get(str(account_id), None) if corporate_code and req.corporate_survey else None,
        )
        db.add(sub_appt)
    db.commit()

    return GetPriceBreakdownResp(
        id=str(main_appt.id),
        **payment_breakdown.model_dump()
    )

class ConfirmAppointmentResp(BaseModel):
    id: str

@router.post("/confirm", response_model=ConfirmAppointmentResp)
def confirm_appointment(appointment_id: str, db: Session = Depends(get_db)):
    # Get the total cost of the appointment
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.status == AppointmentStatus.PREPAYMENT
    ).first()
    if not appt:
        raise HTTPException(400, "Invalid appointment")
    total = appt.payment_breakdown['total']

    # Confirm with all sub appointments
    sub_appts = []
    if appt.group_id:
        sub_appts = db.query(Appointment).filter(
            Appointment.group_id == appt.group_id,
            Appointment.status == AppointmentStatus.PREPAYMENT
        ).all()
        total += sum([row.payment_breakdown['total'] for row in sub_appts])

        # Double-check only_primary_user restriction at confirmation
        if appt.corporate_code:
            corporate_code_record = get_corporate_code(appt.corporate_code, db)
            if corporate_code_record.only_primary_user and sub_appts:
                # sub_appts include family members
                raise HTTPException(400, "This corporate code is restricted to primary users only. Family members cannot be included.")

    if total > 0:
        raise HTTPException(400, "Invalid appointment due to payment fees")

    appointment_success_webhook(db, appt=appt)
    return ConfirmAppointmentResp(
        id=str(appt.id),
    )

class PaymentResp(BaseModel):
    payment_provider_params: dict
    redirect_pathname: Literal['/payments/stripe/paynow', '/payments/2c2p/payment_cvc', '/appointment/consultation']

def check_appointment_payment_success(appointment_id: str, db: Session = Depends(get_db)):
    appt = db.query(Appointment.id).filter(
        Appointment.id == appointment_id,
        Appointment.status == AppointmentStatus.CONFIRMED
    ).first()
    return bool(appt)

@router.post("/payment", response_model=PaymentResp)
def make_payment(appointment_id: str, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    # If payment is already successful, return the redirect pathname
    if check_appointment_payment_success(appointment_id, db):
        return PaymentResp(
            payment_provider_params={},
            redirect_pathname='/appointment/consultation'
        )

    # Get the total amount to be paid
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.status.in_([AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED])
    ).first()
    if not appt:
        raise HTTPException(400, "Invalid appointment")
    appts = get_grouped_appointments(db, appt)
    txn_amount = appts[0].payment_breakdown['total']

    default_payment = get_default_payment(db, user)
    payment, payment_provider_params = create_appointment_payment(
        db,
        user,
        txn_amount,
        default_payment.method,
        default_payment.id,
    )
    appts[0].payment_ids = [str(payment.id)]
    for appt in appts:
        appt.status = AppointmentStatus.PAYMENT_STARTED
    db.commit()

    pathnames: dict[PaymentMethod, Literal['/payments/stripe/paynow', '/payments/2c2p/payment_cvc']] = {
        PaymentMethod.CARD_2C2P: '/payments/2c2p/payment_cvc',
        PaymentMethod.PAYNOW_STRIPE: '/payments/stripe/paynow',
    }
    return PaymentResp(
        payment_provider_params=payment_provider_params,
        redirect_pathname=pathnames[default_payment.method],
    )

@router.post('/payment/success', response_model=SuccessResp)
def check_payment_success(appointment_id: str, db: Session = Depends(get_db)):
    return SuccessResp(success=check_appointment_payment_success(appointment_id, db))

@router.get('/appointments', response_model=list[AppointmentRow])
def get_appointments(db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    appts = db.query(Appointment).filter(
        Appointment.created_by == user.id,
        Appointment.status.not_in([AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED]),
    ).order_by(Appointment.start_datetime.desc(), Appointment.group_id.asc(), Appointment.index.asc()).all()

    # Group appointments by group_id
    family_members = {r.nok_id: r.nok_account for r in user.family_members }
    grouped_appts: list[AppointmentRow] = []

    prev_group_id = None
    cached_appts: list[Appointment] = []
    for row in appts:
        # Process previous grouped entries
        if prev_group_id != row.group_id and cached_appts:
            grouped_appts += process_grouped_appts(cached_appts, family_members, user)
            cached_appts = []

        # Process single entry
        if row.group_id is None:
            grouped_appts += process_grouped_appts([row], family_members, user)
            prev_group_id = None
            continue

        cached_appts.append(row)
        prev_group_id = row.group_id

    if cached_appts:
        grouped_appts += process_grouped_appts(cached_appts, family_members, user)

    return grouped_appts

class AppointmentDetailsService(BaseModel):
    icon: str
    name: str
    details: str

class AppointmentDetailsBranch(BaseModel):
    icon: str
    name: str
    address: str
    url: str

class AppointmentDetailsActions(BaseModel):
    cancel: bool
    reschedule: bool

class AppointmentDetailsPaymentsBreakdown(BaseModel):
    title: str
    amount: float

class AppointmentDetailsPaymentsPayment(BaseModel):
    payment_amount: float
    updated_at: str
    payment_method: PaymentMethod
    remarks: dict[str, Any] | None = None

class AppointmentDetailsPayments(BaseModel):
    items: list[AppointmentDetailsPaymentsBreakdown]
    gst: float
    total: float
    payments: list[AppointmentDetailsPaymentsPayment]
    invoices: list[DocumentDict]

class GetAppointmentResp(BaseModel):
    id: str
    start_datetime: str
    status: AppointmentStatus
    services: list[AppointmentDetailsService]
    branch: AppointmentDetailsBranch
    consult_for: list[str]
    actions: AppointmentDetailsActions
    payments: AppointmentDetailsPayments

@router.get('/appointments/{id}', response_model=GetAppointmentResp)
def get_appointment_details(id: str, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    appt = db.query(Appointment).filter(
        Appointment.id == id,
        Appointment.status.not_in([AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED]),
    ).first()
    if not appt:
        raise HTTPException(400, "Invalid appointment")

    appts = get_grouped_appointments(db, appt)
    family_members = {r.nok_id: r.nok_account for r in user.family_members }

    # Filter out self and family members.
    # If myself is not in the list, account_id is None
    appts = [r for r in appts if r.index is None or r.index == 0 or r.account_id in family_members]

    # Generate consult_for
    consult_for = []
    for r in appts:
        if r.account_id in family_members:
            consult_for.append(family_members[r.account_id].name)
        elif r.account_id == user.id:
            consult_for = ['Myself'] + consult_for
    if appt.guests:
        consult_for += [g['name'] for g in appt.guests]

    payments = db.query(Payment).filter(
        Payment.id.in_(appt.payment_ids),
    ).all()

    # can_modify: Cancel is only allowed up till 24 hours from start time
    # can_reschedule: Reschedule is only allowed up till 6 months from creation date
    curr_time = sg_datetime.now()
    can_modify = appt.status == AppointmentStatus.CONFIRMED and appt.start_datetime > (curr_time + timedelta(hours=24))
    can_reschedule = can_modify and curr_time < (appt.created_at + timedelta(days=183))

    return GetAppointmentResp(
        id=str(appt.id),
        start_datetime=appt.start_datetime.astimezone(sgtz).strftime('%d %b %Y, %I:%M %p'),
        status=appt.status,
        services=[
            AppointmentDetailsService(
                icon=svc.get('icon', 'https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/appointments/chronic.png'),
                name=svc['name'],
                details='\n'.join([item['name'] for item in svc['items']]),
            )
            for svc in appt.services
        ],
        branch=AppointmentDetailsBranch(
            icon='https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/appointments/branch.png',
            name=appt.branch['name'],
            address=appt.branch['address'],
            url=appt.branch['url'],
        ),
        consult_for=consult_for,
        actions=AppointmentDetailsActions(
            cancel=can_modify,
            reschedule=can_reschedule,
        ),
        payments=AppointmentDetailsPayments(
            items=[
                AppointmentDetailsPaymentsBreakdown(
                    title=payment_item['title'],
                    amount=payment_item['amount'],
                )
                for payment_item in appt.payment_breakdown['items']
            ],
            gst=appt.payment_breakdown['gst'],
            total=appt.payment_breakdown['total'],
            payments=[
                AppointmentDetailsPaymentsPayment(
                    payment_amount=payment.payment_amount,
                    updated_at=payment.updated_at.isoformat(),
                    payment_method=payment.payment_method,
                    remarks=payment.remarks,
                )
                for payment in payments
            ],
            invoices=[
                DocumentDict(
                    id=str(invoice_id),
                    title='Invoice',
                    filename=f'Invoice {appt.created_at.astimezone(sgtz).strftime("%d %b %Y")}.pdf',
                    url=f'/api/appointment/v1/appointments/{id}/invoice/{invoice_id}',
                    filetype=FileViewerType.HTML,
                )
                for invoice_id in appt.invoice_ids
            ],
        ),
    )

@router.get('/appointments/{id}/invoice/{invoice_id}')
def get_appointment_invoice_html(id: str, invoice_id: str, db: Session = Depends(get_db)):
    appt = db.query(Appointment).filter(
        Appointment.id == id,
        Appointment.status.not_in([AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED]),
    ).first()
    if not appt:
        raise HTTPException(400, "Invalid appointment")

    if invoice_id not in appt.invoice_ids:
        raise HTTPException(400, "Invalid invoice")

    return get_invoice_document_html(invoice_id)

def _ensure_outside_24_hours(appt: Appointment, action: str):
    cutoff = sg_datetime.now() + timedelta(hours=24)
    if appt.start_datetime <= cutoff:
        raise HTTPException(400, f"Appointments cannot be {action} within 24 hours of the start time")

@router.post('/appointments/{id}/cancel')
def cancel_appointment(id: str, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    appt = db.query(Appointment).filter(
        Appointment.id == id,
        Appointment.status == AppointmentStatus.CONFIRMED,
    ).first()
    if not appt:
        raise HTTPException(400, "Invalid appointment")

    _ensure_outside_24_hours(appt, 'cancelled')
    appts = get_grouped_appointments(db, appt)
    for appt in appts:
        if appt.sgimed_appointment_id:
            update_appointment_status(
                appt.sgimed_appointment_id,
                is_cancelled=True,
            )
        if appt.guests:
            for guest in appt.guests:
                update_appointment_status(
                    guest['sgimed_appointment_id'],
                    is_cancelled=True,
                )
        appt.status = AppointmentStatus.CANCELLED
    db.commit()

class GetRescheduleAppointmentTimingsReq(BaseModel):
    curr_date: date

@router.post('/appointments/{id}/reschedule_timings', response_model=GetAppointmentTimingsResp)
def get_reschedule_appointment_timings(id: str, req: GetRescheduleAppointmentTimingsReq, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    appt = db.query(Appointment).filter(
        Appointment.id == id,
        Appointment.status == AppointmentStatus.CONFIRMED,
    ).first()
    if not appt:
        raise HTTPException(400, "Invalid appointment")
    _ensure_outside_24_hours(appt, 'rescheduled')

    appts = get_grouped_appointments(db, appt)
    num_patients = int(bool(appt.account_id)) + len(appt.guests if appt.guests else []) + max(len(appts) - 1, 0)
    service_ids = [item['id'] for svc in appt.services for item in svc['items']]

    # Calculate max date based on creation date
    _, max_reschedule_date = get_minmax_booking_dates(
        db, appt.created_at, service_ids, appt.branch['id']
    )

    resp = get_appointment_timings(
        GetAppointmentTimingsReq(
            service_ids=service_ids,
            num_patients=num_patients,
            branch_id=appt.branch['id'],
            curr_date=req.curr_date,
        ),
        db,
    )

    resp.timings = [t for t in resp.timings if t <= max_reschedule_date and t != appt.start_datetime]
    resp.max_date = max_reschedule_date
    return resp

class RescheduleAppointmentReq(BaseModel):
    new_start_datetime: datetime

@router.post('/appointments/{id}/reschedule', response_model=SuccessResp)
def reschedule_appointment(id: str, req: RescheduleAppointmentReq, db: Session = Depends(get_db), user: Account = Depends(validate_user)):
    appt = db.query(Appointment).filter(
        Appointment.id == id,
        Appointment.status == AppointmentStatus.CONFIRMED,
    ).first()
    if not appt:
        raise HTTPException(400, "Invalid appointment")
    _ensure_outside_24_hours(appt, 'rescheduled')

    service_ids = [item['id'] for svc in appt.services for item in svc['items']]
    min_reschedule_date, _ = get_minmax_booking_dates(
        db, sg_datetime.now(), service_ids, appt.branch['id']
    )
    if req.new_start_datetime < min_reschedule_date:
        raise HTTPException(400, f"New appointment date must not be earlier than {min_reschedule_date.strftime('%d %b %Y, %I:%M %p')}")

    _, max_reschedule_date = get_minmax_booking_dates(
        db, appt.created_at, service_ids, appt.branch['id']
    )
    if req.new_start_datetime > max_reschedule_date:
        raise HTTPException(400, f"New appointment date must not exceed {max_reschedule_date.strftime('%d %b %Y')}")

    # Update SGiMed & Database
    time_diff = req.new_start_datetime - appt.start_datetime
    appts = get_grouped_appointments(db, appt)
    appt_index = 0
    for appt in appts:
        duration = appt.duration / (int(bool(appt.account_id)) + len(appt.guests if appt.guests else []))
        if appt.sgimed_appointment_id:
            update_appointment_start_datetime(
                appt.sgimed_appointment_id,
                req.new_start_datetime + timedelta(minutes=appt_index * duration),
                duration,
            )
            appt_index += 1
        if appt.guests:
            for guest in appt.guests:
                if 'sgimed_appointment_id' in guest:
                    update_appointment_start_datetime(
                        guest['sgimed_appointment_id'],
                        req.new_start_datetime + timedelta(minutes=appt_index * duration),
                        duration,
                    )
                    appt_index += 1

        appt.start_datetime = appt.start_datetime + time_diff
    db.commit()
    return SuccessResp(success=True)
