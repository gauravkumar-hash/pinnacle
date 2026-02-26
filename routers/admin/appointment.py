from datetime import datetime, time
import logging
from typing import Any
from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import StreamingResponse
from pyfa_converter_v2 import FormDepends
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func, cast, text, String
from pydantic import BaseModel
import uuid
import os.path as osp
from io import StringIO
import csv

from models import get_db, Branch, Account
from models.pinnacle import OperatingHour
from models.appointment import (
    AppointmentServiceGroup,
    AppointmentService,
    AppointmentCorporateCode,
    AppointmentOnsiteBranch,
    AppointmentBranchOperatingHours,
    Appointment
)
from models.sgimed import SGiMedInventory
from models.model_enums import AppointmentServiceGroupType, AppointmentStatus, DayOfWeek, BranchType, AppointmentCategory
from utils.admin_query.models import AdminQueryApiParams
from .utils import get_current_user
from utils.fastapi import HTTPJSONException
from utils.sg_datetime import sgtz
from utils.pagination import Page, PaginationInput, paginate
from utils.system_config import get_config_value
from config import SUPABASE_UPLOAD_BUCKET, supabase
from .actions.appointment_queries import get_csv_response

router = APIRouter(dependencies=[Depends(get_current_user)])

# Common Response Models
class SuccessResponse(BaseModel):
    success: bool

class CreateResponse(BaseModel):
    id: str

# Service Group Models
class ServiceGroupBase(BaseModel):
    name: str
    title: str | None = None
    description: str | None = None
    index: int
    duration: int
    type: AppointmentServiceGroupType
    restricted_branches: list[str] = []
    corporate_code_id: str | None = None
    category: AppointmentCategory = AppointmentCategory.GENERAL

class ServiceGroupCreate(ServiceGroupBase):
    pass

class ServiceGroupUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    description: str | None = None
    index: int | None = None
    duration: int | None = None
    type: AppointmentServiceGroupType | None = None
    restricted_branches: list[str] | None = None
    corporate_code_id: str | None = None
    category: AppointmentCategory | None = None

class ServiceGroupDetails(ServiceGroupBase):
    id: str
    services_count: int
    created_at: datetime
    updated_at: datetime

# Service Group Endpoints
@router.get("/service-groups", response_model=list[ServiceGroupDetails])
def get_service_groups(
    category: AppointmentCategory = AppointmentCategory.GENERAL,
    db: Session = Depends(get_db)
):
    service_groups = db.query(AppointmentServiceGroup) \
        .filter(AppointmentServiceGroup.category == category) \
        .order_by(AppointmentServiceGroup.corporate_code_id.desc(), AppointmentServiceGroup.index).all()

    # Get service counts in one query
    service_counts = db.query(
        AppointmentService.group_id,
        func.count(AppointmentService.id).label('total')
    ).group_by(AppointmentService.group_id).all()

    count_map = {str(sc.group_id): int(sc.total) for sc in service_counts}

    result = []
    for group in service_groups:
        services_count = count_map.get(str(group.id), 0)
        result.append(ServiceGroupDetails(
            id=str(group.id),
            name=group.name,
            title=group.title,
            description=group.description,
            index=group.index,
            duration=group.duration,
            type=group.type,
            restricted_branches=group.restricted_branches,
            corporate_code_id=str(group.corporate_code_id) if group.corporate_code_id else None,
            services_count=services_count,
            created_at=group.created_at.astimezone(sgtz),
            updated_at=group.updated_at.astimezone(sgtz)
        ))

    return result

@router.post("/service-groups", response_model=CreateResponse)
def create_service_group(req: ServiceGroupCreate, db: Session = Depends(get_db)):
    # Validate corporate_code_id if provided
    if req.corporate_code_id:
        corp_code = db.query(AppointmentCorporateCode).filter(
            AppointmentCorporateCode.id == req.corporate_code_id
        ).first()
        if not corp_code:
            raise HTTPJSONException(
                title="Invalid Corporate Code",
                message="Corporate code not found",
                status_code=404
            )

    service_group = AppointmentServiceGroup(
        icon='',
        name=req.name,
        title=req.title,
        description=req.description,
        index=req.index,
        duration=req.duration,
        type=req.type,
        restricted_branches=req.restricted_branches,
        corporate_code_id=uuid.UUID(req.corporate_code_id) if req.corporate_code_id else None
    )

    db.add(service_group)
    db.commit()

    return CreateResponse(id=str(service_group.id))

@router.get("/service-groups/{group_id}", response_model=ServiceGroupDetails)
def get_service_group(group_id: str, db: Session = Depends(get_db)):
    service_group = db.query(AppointmentServiceGroup).filter(
        AppointmentServiceGroup.id == group_id
    ).first()

    if not service_group:
        raise HTTPJSONException(
            title="Not Found",
            message="Service group not found",
            status_code=404
        )

    services_count = db.query(AppointmentService).filter(AppointmentService.group_id == group_id).count()

    return ServiceGroupDetails(
        id=str(service_group.id),
        name=service_group.name,
        title=service_group.title,
        description=service_group.description,
        index=service_group.index,
        duration=service_group.duration,
        type=service_group.type,
        restricted_branches=service_group.restricted_branches,
        corporate_code_id=str(service_group.corporate_code_id) if service_group.corporate_code_id else None,
        services_count=services_count,
        created_at=service_group.created_at.astimezone(sgtz),
        updated_at=service_group.updated_at.astimezone(sgtz)
    )

@router.put("/service-groups/{group_id}", response_model=SuccessResponse)
def update_service_group(group_id: str, req: ServiceGroupUpdate, db: Session = Depends(get_db)):
    service_group = db.query(AppointmentServiceGroup).filter(
        AppointmentServiceGroup.id == group_id
    ).first()

    if not service_group:
        raise HTTPJSONException(
            title="Not Found",
            message="Service group not found",
            status_code=404
        )

    # Validate corporate_code_id if provided
    if req.corporate_code_id:
        corp_code = db.query(AppointmentCorporateCode).filter(
            AppointmentCorporateCode.id == req.corporate_code_id
        ).first()
        if not corp_code:
            raise HTTPJSONException(
                title="Invalid Corporate Code",
                message="Corporate code not found",
                status_code=404
            )

    # Update fields
    if req.name is not None:
        service_group.name = req.name
    if req.title is not None:
        service_group.title = req.title
    if req.description is not None:
        service_group.description = req.description
    if req.index is not None:
        service_group.index = req.index
    if req.duration is not None:
        service_group.duration = req.duration
    if req.type is not None:
        service_group.type = req.type
    if req.restricted_branches is not None:
        service_group.restricted_branches = req.restricted_branches

    service_group.corporate_code_id = uuid.UUID(req.corporate_code_id) if req.corporate_code_id else None
    db.commit()
    return SuccessResponse(success=True)

@router.delete("/service-groups/{group_id}", response_model=SuccessResponse)
def delete_service_group(group_id: str, db: Session = Depends(get_db)):
    service_group = db.query(AppointmentServiceGroup).filter(
        AppointmentServiceGroup.id == group_id
    ).first()

    if not service_group:
        raise HTTPJSONException(
            title="Not Found",
            message="Service group not found",
            status_code=404
        )

    # Delete all services in this group
    db.query(AppointmentService).filter(AppointmentService.group_id == group_id).delete()
    db.delete(service_group)
    db.commit()
    return SuccessResponse(success=True)

# Inventory Models
class DropdownItem(BaseModel):
    label: str
    value: str

class InventorySearchResponse(BaseModel):
    inventories: list[DropdownItem]

# Inventory Endpoints
@router.get("/inventory/search", response_model=InventorySearchResponse)
def search_inventory(
    search: str,
    db: Session = Depends(get_db)
):
    inventories = db.query(SGiMedInventory) \
        .filter(or_(
            SGiMedInventory.id.ilike(f"%{search}%"),
            SGiMedInventory.name.ilike(f"%{search}%"),
            SGiMedInventory.code.ilike(f"%{search}%")
        )) \
        .limit(50).all()

    result = []
    for inventory in inventories:
        result.append(DropdownItem(
            label=f'{inventory.name} ({inventory.code}): ${inventory.price:.2f}',
            value=inventory.id
        ))

    return InventorySearchResponse(inventories=result)

# Branch Models
class BranchItem(BaseModel):
    id: str
    name: str
    address: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    url: str | None = None
    category: str
    hidden: bool
    branch_type: str
    operating_hours: dict[str, list[dict[str, Any]]] | None = None

class BranchListResponse(BaseModel):
    branches: list[BranchItem]

# Branch Endpoints
@router.get("/branches", response_model=BranchListResponse)
def get_branches(
    include_hidden: bool = True,
    include_operating_hours: bool = False,
    db: Session = Depends(get_db)
):
    """Get all branches from pinnacle.py:Branch with optional operating hours"""
    query = db.query(Branch).filter(Branch.deleted == False)

    if not include_hidden:
        query = query.filter(Branch.hidden == False)

    branches = query.order_by(Branch.name).all()

    result = []
    for branch in branches:
        operating_hours = None

        # Include operating hours if requested
        if include_operating_hours:
            # Get basic branch operating hours from pinnacle_branches_operating_hours
            branch_operating_hours = db.query(OperatingHour).filter(
                OperatingHour.branch_id == branch.id
            ).all()

            # Group by day
            hours_by_day = {}
            for day in DayOfWeek:
                hours_by_day[day.value] = []

            for hour in branch_operating_hours:
                hours_by_day[hour.day.value].append({
                    "id": str(hour.id),
                    "start_time": hour.start_time.strftime("%H:%M"),
                    "end_time": hour.end_time.strftime("%H:%M")
                })

            operating_hours = hours_by_day

        result.append(BranchItem(
            id=str(branch.id),
            name=branch.name,
            address=branch.address,
            phone=branch.phone,
            whatsapp=branch.whatsapp,
            email=branch.email,
            url=branch.url,
            category=branch.category,
            hidden=branch.hidden,
            branch_type=branch.branch_type.value,
            operating_hours=operating_hours
        ))

    return BranchListResponse(branches=result)

# SGiMed Calendar Models
class CalendarItem(BaseModel):
    id: str
    name: str
    remark: str | None = None
    is_enabled: bool

class CalendarListResponse(BaseModel):
    calendars: list[CalendarItem]

# SGiMed Calendar Endpoints
@router.get("/sgimed/calendars", response_model=CalendarListResponse)
def get_sgimed_calendars(
    branch_id: str,
    db: Session = Depends(get_db)
):
    """
    Get all calendars from SGiMed for a specific branch.
    Used for selecting existing calendars when creating onsite branches.
    """
    from utils.integrations.sgimed import get_calendars

    try:
        calendars = get_calendars()

        result = []
        for calendar in calendars:
            if calendar.branch_id != branch_id:
                continue

            result.append(CalendarItem(
                id=calendar.id,
                name=calendar.name,
                is_enabled=calendar.is_enabled
            ))

        return CalendarListResponse(calendars=result)

    except Exception as e:
        raise HTTPJSONException(
            title="Failed to Fetch Calendars",
            message=f"Could not retrieve calendars from SGiMed: {str(e)}",
            status_code=500
        )

# Service Models
class TestItem(BaseModel):
    name: str
    exclusion: str

class ServiceBase(BaseModel):
    name: str
    prepayment_price: float = 0.0
    display_price: float = 0.0
    index: int
    min_booking_ahead_days: int = 2
    sgimed_inventory_id: str | None = None
    sgimed_inventory: DropdownItem | None = None
    restricted_branches: list[str] = []
    tests: list[TestItem] | None = None
    group_id: str

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    name: str | None = None
    prepayment_price: float | None = None
    display_price: float | None = None
    index: int | None = None
    min_booking_ahead_days: int | None = None
    sgimed_inventory: DropdownItem | None = None
    restricted_branches: list[str] | None = None
    tests: list[TestItem] | None = None
    group_id: str | None = None

class ServiceDetails(ServiceBase):
    id: str
    group_name: str
    created_at: datetime
    updated_at: datetime

# Service Endpoints
@router.get("/services", response_model=list[ServiceDetails])
def get_services(group_id: str | None = None, db: Session = Depends(get_db)):
    query = db.query(AppointmentService) \
        .join(AppointmentServiceGroup) \
        .options(
            joinedload(AppointmentService.sgimed_inventory).load_only(SGiMedInventory.code),
        )

    if group_id:
        query = query.filter(AppointmentService.group_id == group_id)

    services = query.order_by(AppointmentService.index).all()

    result = []
    for service in services:
        result.append(ServiceDetails(
            id=str(service.id),
            name=service.name,
            prepayment_price=service.prepayment_price,
            display_price=service.display_price,
            index=service.index,
            min_booking_ahead_days=service.min_booking_ahead_days,
            sgimed_inventory=DropdownItem(
                label=f'{service.sgimed_inventory.name} ({service.sgimed_inventory.code}): ${service.sgimed_inventory.price:.2f}',
                value=service.sgimed_inventory.id
            ) if service.sgimed_inventory else None,
            restricted_branches=service.restricted_branches,
            tests=[TestItem(name=test['name'], exclusion=test['exclusion']) for test in service.tests] if service.tests else None,
            group_id=str(service.group_id),
            group_name=service.group.name,
            created_at=service.created_at.astimezone(sgtz),
            updated_at=service.updated_at.astimezone(sgtz)
        ))

    return result

@router.post("/services", response_model=CreateResponse)
def create_service(req: ServiceCreate, db: Session = Depends(get_db)):
    # Validate group_id
    service_group = db.query(AppointmentServiceGroup).filter(
        AppointmentServiceGroup.id == req.group_id
    ).first()
    if not service_group:
        raise HTTPJSONException(
            title="Invalid Service Group",
            message="Service group not found",
            status_code=404
        )

    # Validate inventory_id requirement when prepayment_price > 0
    if req.prepayment_price > 0 and not req.sgimed_inventory:
        raise HTTPJSONException(
            title="Inventory Required",
            message="SGiMed inventory ID is required when prepayment price is greater than 0",
            status_code=400
        )

    # Validate inventory_id exists if provided
    if req.sgimed_inventory_id:
        inventory = db.query(SGiMedInventory).filter(
            SGiMedInventory.id == req.sgimed_inventory_id
        ).first()
        if not inventory:
            raise HTTPJSONException(
                title="Invalid Inventory",
                message="SGiMed inventory not found",
                status_code=404
            )

    # Convert tests to dict format
    tests_dict = None
    if req.tests:
        tests_dict = [{"name": test.name, "exclusion": test.exclusion} for test in req.tests]

    service = AppointmentService(
        name=req.name,
        prepayment_price=req.prepayment_price,
        display_price=req.display_price,
        index=req.index,
        min_booking_ahead_days=req.min_booking_ahead_days,
        sgimed_inventory_id=req.sgimed_inventory.value if req.sgimed_inventory else None,
        restricted_branches=req.restricted_branches,
        tests=tests_dict,
        group_id=uuid.UUID(req.group_id)
    )

    db.add(service)
    db.commit()

    return CreateResponse(id=str(service.id))

@router.get("/services/{service_id}", response_model=ServiceDetails)
def get_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(AppointmentService).join(AppointmentServiceGroup).filter(
        AppointmentService.id == service_id
    ).first()

    if not service:
        raise HTTPJSONException(
            title="Not Found",
            message="Service not found",
            status_code=404
        )

    return ServiceDetails(
        id=str(service.id),
        name=service.name,
        prepayment_price=service.prepayment_price,
        display_price=service.display_price,
        index=service.index,
        min_booking_ahead_days=service.min_booking_ahead_days,
        sgimed_inventory_id=service.sgimed_inventory_id,
        restricted_branches=service.restricted_branches,
        tests=[TestItem(name=test['name'], exclusion=test['exclusion']) for test in service.tests] if service.tests else None,
        group_id=str(service.group_id),
        group_name=service.group.name,
        created_at=service.created_at,
        updated_at=service.updated_at
    )

@router.put("/services/{service_id}", response_model=SuccessResponse)
def update_service(service_id: str, req: ServiceUpdate, db: Session = Depends(get_db)):
    service = db.query(AppointmentService).filter(
        AppointmentService.id == service_id
    ).first()

    if not service:
        raise HTTPJSONException(
            title="Not Found",
            message="Service not found",
            status_code=404
        )

    # Validate group_id if provided
    if req.group_id:
        service_group = db.query(AppointmentServiceGroup).filter(
            AppointmentServiceGroup.id == req.group_id
        ).first()
        if not service_group:
            raise HTTPJSONException(
                title="Invalid Service Group",
                message="Service group not found",
                status_code=404
            )

    # Validate inventory_id exists if provided
    if req.sgimed_inventory is not None:
        inventory = db.query(SGiMedInventory).filter(
            SGiMedInventory.id == req.sgimed_inventory.value
        ).first()
        if not inventory:
            raise HTTPJSONException(
                title="Invalid Inventory",
                message="SGiMed inventory not found",
                status_code=404
            )

    # Update fields
    if req.name is not None:
        service.name = req.name
    if req.prepayment_price is not None:
        service.prepayment_price = req.prepayment_price
    if req.display_price is not None:
        service.display_price = req.display_price
    if req.index is not None:
        service.index = req.index
    if req.min_booking_ahead_days is not None:
        service.min_booking_ahead_days = req.min_booking_ahead_days
    if req.restricted_branches is not None:
        service.restricted_branches = req.restricted_branches
    if req.tests is not None:
        service.tests = [{"name": test.name, "exclusion": test.exclusion} for test in req.tests] if req.tests else None
    if req.group_id is not None:
        service.group_id = uuid.UUID(req.group_id)

    service.sgimed_inventory_id = req.sgimed_inventory.value if req.sgimed_inventory else None
    # Validate inventory requirement after updates
    if service.prepayment_price > 0 and not service.sgimed_inventory_id:
        raise HTTPJSONException(
            title="Inventory Required",
            message="SGiMed inventory ID is required when prepayment price is greater than 0",
            status_code=400
        )

    db.commit()
    return SuccessResponse(success=True)

@router.delete("/services/{service_id}", response_model=SuccessResponse)
def delete_service(service_id: str, db: Session = Depends(get_db)):
    service = db.query(AppointmentService).filter(
        AppointmentService.id == service_id
    ).first()

    if not service:
        raise HTTPJSONException(
            title="Not Found",
            message="Service not found",
            status_code=404
        )

    db.delete(service)
    db.commit()
    return SuccessResponse(success=True)

# Corporate Code Related Models
class ServiceGroupReference(BaseModel):
    id: str
    name: str

class OnsiteBranchReference(BaseModel):
    id: str
    branch_id: str
    branch_name: str
    header: str | None = None
    start_date: datetime
    end_date: datetime

class OnsiteBranchCreateRequest(BaseModel):
    branch_id: str
    header: str | None = None
    start_date: datetime
    end_date: datetime

# Corporate Code Models
class CorporateCodeBase(BaseModel):
    code: str
    organization: str
    patient_survey: dict[str, Any] = {}
    corporate_survey: dict[str, Any] = {}
    only_primary_user: bool = False
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool = True
    category: AppointmentCategory = AppointmentCategory.GENERAL

class CorporateCodeCreate(CorporateCodeBase):
    service_group_ids: list[str] = []
    onsite_branches: list[OnsiteBranchCreateRequest] = []

class CorporateCodeUpdate(BaseModel):
    code: str | None = None
    organization: str | None = None
    patient_survey: dict[str, Any] | None = None
    corporate_survey: dict[str, Any] | None = None
    only_primary_user: bool | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_active: bool | None = None
    service_group_ids: list[str] | None = None
    onsite_branches: list[OnsiteBranchCreateRequest] | None = None

class CorporateCodeDetails(CorporateCodeBase):
    id: str
    service_groups: list[ServiceGroupReference]
    onsite_branches: list[OnsiteBranchReference]
    created_at: datetime
    updated_at: datetime

# Corporate Code Endpoints
@router.get("/corporate-codes", response_model=list[CorporateCodeDetails])
def get_corporate_codes(
    category: AppointmentCategory = AppointmentCategory.GENERAL,
    db: Session = Depends(get_db)
):
    corporate_codes = db.query(AppointmentCorporateCode) \
        .filter(AppointmentCorporateCode.category == category) \
        .order_by(AppointmentCorporateCode.created_at.desc()).all()

    result = []
    for corp_code in corporate_codes:
        service_groups = [
            ServiceGroupReference(
                id=str(sg.id),
                name=sg.name
            )
            for sg in corp_code.appointment_service_groups
        ]

        onsite_branches = []
        for ob in corp_code.appointment_onsite_branches:
            branch = db.query(Branch).filter(Branch.id == ob.branch_id).first()
            onsite_branches.append(OnsiteBranchReference(
                id=str(ob.id),
                branch_id=str(ob.branch_id),
                branch_name=branch.name if branch else "Unknown",
                header=ob.header,
                start_date=ob.start_date.astimezone(sgtz),
                end_date=ob.end_date.astimezone(sgtz)
            ))

        result.append(CorporateCodeDetails(
            id=str(corp_code.id),
            code=corp_code.code,
            organization=corp_code.organization,
            patient_survey=corp_code.patient_survey,
            corporate_survey=corp_code.corporate_survey,
            only_primary_user=corp_code.only_primary_user,
            valid_from=corp_code.valid_from.astimezone(sgtz) if corp_code.valid_from else None,
            valid_to=corp_code.valid_to.astimezone(sgtz) if corp_code.valid_to else None,
            is_active=corp_code.is_active,
            service_groups=service_groups,
            onsite_branches=onsite_branches,
            created_at=corp_code.created_at.astimezone(sgtz),
            updated_at=corp_code.updated_at.astimezone(sgtz)
        ))

    return result

@router.post("/corporate-codes", response_model=CreateResponse)
def create_corporate_code(req: CorporateCodeCreate, db: Session = Depends(get_db)):
    # Check if code already exists
    existing = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.code == req.code
    ).first()
    if existing:
        raise HTTPJSONException(
            title="Code Already Exists",
            message="Corporate code already exists",
            status_code=400
        )

    corporate_code = AppointmentCorporateCode(
        code=req.code,
        organization=req.organization,
        patient_survey=req.patient_survey,
        corporate_survey=req.corporate_survey,
        only_primary_user=req.only_primary_user,
        valid_from=req.valid_from,
        valid_to=req.valid_to,
        is_active=req.is_active
    )

    db.add(corporate_code)
    db.flush()  # Get the ID

    # Validate and add service groups
    if req.service_group_ids:
        service_groups = db.query(AppointmentServiceGroup).filter(
            AppointmentServiceGroup.id.in_(req.service_group_ids)
        ).all()
        if len(service_groups) != len(req.service_group_ids):
            raise HTTPJSONException(
                title="Invalid Service Groups",
                message="One or more service groups not found",
                status_code=404
            )
        for service_group in service_groups:
            service_group.corporate_code_id = corporate_code.id

    # Add onsite branches
    for onsite_data in req.onsite_branches:
        onsite_branch = AppointmentOnsiteBranch(
            branch_id=uuid.UUID(onsite_data.branch_id),
            corporate_code_id=corporate_code.id,
            header=onsite_data.header,
            start_date=onsite_data.start_date,
            end_date=onsite_data.end_date
        )
        db.add(onsite_branch)

    db.commit()

    return CreateResponse(id=str(corporate_code.id))

@router.get("/corporate-codes/{code_id}", response_model=CorporateCodeDetails)
def get_corporate_code(code_id: str, db: Session = Depends(get_db)):
    corp_code = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.id == code_id
    ).first()

    if not corp_code:
        raise HTTPJSONException(
            title="Not Found",
            message="Corporate code not found",
            status_code=404
        )

    service_groups = [
        ServiceGroupReference(
            id=str(sg.id),
            name=sg.name
        )
        for sg in corp_code.appointment_service_groups
    ]

    onsite_branches = []
    for ob in corp_code.appointment_onsite_branches:
        branch = db.query(Branch).filter(Branch.id == ob.branch_id).first()
        onsite_branches.append({
            "id": str(ob.id),
            "branch_id": str(ob.branch_id),
            "branch_name": branch.name if branch else "Unknown",
            "header": ob.header,
            "start_date": ob.start_date.astimezone(sgtz),
            "end_date": ob.end_date.astimezone(sgtz)
        })

    return CorporateCodeDetails(
        id=str(corp_code.id),
        code=corp_code.code,
        organization=corp_code.organization,
        patient_survey=corp_code.patient_survey,
        corporate_survey=corp_code.corporate_survey,
        only_primary_user=corp_code.only_primary_user,
        valid_from=corp_code.valid_from.astimezone(sgtz) if corp_code.valid_from else None,
        valid_to=corp_code.valid_to.astimezone(sgtz) if corp_code.valid_to else None,
        is_active=corp_code.is_active,
        service_groups=service_groups,
        onsite_branches=onsite_branches,
        created_at=corp_code.created_at.astimezone(sgtz),
        updated_at=corp_code.updated_at.astimezone(sgtz)
    )

@router.put("/corporate-codes/{code_id}", response_model=SuccessResponse)
def update_corporate_code(code_id: str, req: CorporateCodeUpdate, db: Session = Depends(get_db)):
    corp_code = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.id == code_id
    ).first()

    if not corp_code:
        raise HTTPJSONException(
            title="Not Found",
            message="Corporate code not found",
            status_code=404
        )

    # Check if new code already exists (if changing code)
    if req.code and req.code != corp_code.code:
        existing = db.query(AppointmentCorporateCode).filter(
            AppointmentCorporateCode.code == req.code,
            AppointmentCorporateCode.id != code_id
        ).first()
        if existing:
            raise HTTPJSONException(
                title="Code Already Exists",
                message="Corporate code already exists",
                status_code=400
            )

    # Update basic fields - only update fields that were explicitly set in the request
    # This prevents accidentally wiping fields when they're not included in the update
    if "code" in req.model_fields_set:
        corp_code.code = req.code
    if "organization" in req.model_fields_set:
        corp_code.organization = req.organization
    # For survey fields, only update if explicitly set AND not empty
    # This prevents frontend sending empty {} from wiping existing survey data
    if "patient_survey" in req.model_fields_set and req.patient_survey:
        corp_code.patient_survey = req.patient_survey
    if "corporate_survey" in req.model_fields_set and req.corporate_survey:
        corp_code.corporate_survey = req.corporate_survey
    if "only_primary_user" in req.model_fields_set:
        corp_code.only_primary_user = req.only_primary_user
    if "valid_from" in req.model_fields_set:
        corp_code.valid_from = req.valid_from
    if "valid_to" in req.model_fields_set:
        corp_code.valid_to = req.valid_to
    if "is_active" in req.model_fields_set:
        corp_code.is_active = req.is_active

    db.commit()
    return SuccessResponse(success=True)

@router.delete("/corporate-codes/{code_id}", response_model=SuccessResponse)
def delete_corporate_code(code_id: str, db: Session = Depends(get_db)):
    """
    Delete a corporate code. Requires that all associated service groups
    and onsite branches are deleted first.
    """
    corp_code = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.id == code_id
    ).first()

    if not corp_code:
        raise HTTPJSONException(
            title="Not Found",
            message="Corporate code not found",
            status_code=404
        )

    # Check for associated service groups
    associated_service_groups = db.query(AppointmentServiceGroup).filter(
        AppointmentServiceGroup.corporate_code_id == code_id
    ).all()

    # Check for associated onsite branches
    associated_onsite_branches = db.query(AppointmentOnsiteBranch).filter(
        AppointmentOnsiteBranch.corporate_code_id == code_id
    ).all()

    # Build error messages for dependencies
    dependencies = []
    if associated_service_groups:
        group_names = [sg.name for sg in associated_service_groups]
        dependencies.append(f"{len(associated_service_groups)} service group(s): {', '.join(group_names[:3])}")
        if len(group_names) > 3:
            dependencies[-1] += f" and {len(group_names) - 3} more"

    if associated_onsite_branches:
        branch_headers = [ob.header or f"Branch {ob.branch_id}" for ob in associated_onsite_branches]
        dependencies.append(f"{len(associated_onsite_branches)} onsite branch(es): {', '.join(branch_headers[:3])}")
        if len(branch_headers) > 3:
            dependencies[-1] += f" and {len(branch_headers) - 3} more"

    # Raise error if dependencies exist
    if dependencies:
        dependency_list = "; ".join(dependencies)
        raise HTTPJSONException(
            title="Cannot Delete Corporate Code",
            message=f"Corporate code '{corp_code.code}' has associated resources that must be deleted first: {dependency_list}",
            status_code=400
        )

    # If no dependencies, proceed with deletion (soft delete by setting inactive)
    db.delete(corp_code)
    db.commit()
    return SuccessResponse(success=True)

@router.get("/corporate-codes/{code_id}/export-survey-csv")
def export_corporate_survey_csv(
    code_id: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db)
):
    # Get the corporate code
    corp_code = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.id == code_id
    ).first()

    if not corp_code:
        raise HTTPJSONException(
            title="Not Found",
            message="Corporate code not found",
            status_code=404
        )

    # Build query for appointments with this corporate code
    query = db.query(Appointment).filter(
        Appointment.corporate_code == corp_code.code,
        Appointment.corporate_survey.isnot(None)
    ).options(
        joinedload(Appointment.account).load_only(Account.name, Account.mobile_code, Account.mobile_number, Account.secondary_mobile_code, Account.secondary_mobile_number, Account.email),
        joinedload(Appointment.created_by_account).load_only(Account.name)
    )

    # Apply date filters if provided
    if date_from:
        query = query.filter(Appointment.start_datetime >= date_from)
    if date_to:
        query = query.filter(Appointment.start_datetime <= date_to)
    query = query.filter(Appointment.duration > 0)

    # Order by appointment date
    appointments = query.order_by(Appointment.start_datetime.desc()).all()

    if not appointments:
        raise HTTPJSONException(
            title="No Data",
            message="No appointments found with survey responses for this corporate code",
            status_code=404
        )

    # Create CSV output
    output = StringIO()
    writer = csv.writer(output)

    # Build headers dynamically based on corporate survey structure
    headers = [
        "Appointment ID",
        "Appointment Date",
        "Created At",
        "Patient Name",
        "Patient Mobile",
        "Patient Email",
        "Created By",
        "Services",
        "Service Items",
        "Branch",
        "Status",
        "Total Amount",
        "Corp Code",
        "Corp Organization"
    ]

    # Collect all unique keys from patient and corporate surveys
    patient_survey_keys = set()
    corporate_survey_keys = set()

    for appt in appointments:
        if appt.patient_survey:
            patient_survey_keys.update(['Patient Survey'])
        if appt.corporate_survey and isinstance(appt.corporate_survey, dict):
            corporate_survey_keys.update(appt.corporate_survey.keys())

    # Convert sets to sorted lists for consistent column ordering
    patient_survey_keys = sorted(list(patient_survey_keys))
    corporate_survey_keys = sorted(list(corporate_survey_keys))

    # Add patient survey headers
    if 'Patient Survey' in patient_survey_keys:
        headers.append("Patient Survey")

    # Add corporate survey headers
    for key in corporate_survey_keys:
        headers.append(f"Corporate Survey - {key}")

    writer.writerow(headers)

    # Write data rows
    for appt in appointments:
        # Get patient info
        if appt.account:
            patient_name = appt.account.name
            # Use secondary mobile if primary is empty
            if appt.account.mobile_number:
                patient_mobile = f"{appt.account.mobile_code.value}{appt.account.mobile_number}"
            elif appt.account.secondary_mobile_code and appt.account.secondary_mobile_number:
                patient_mobile = f"{appt.account.secondary_mobile_code.value}{appt.account.secondary_mobile_number}"
            else:
                patient_mobile = ''
            patient_email = appt.account.email
        else:
            # Guest appointment
            guest_info = appt.guests[0] if appt.guests else {}
            patient_name = guest_info.get('name', 'Guest')
            patient_mobile = guest_info.get('mobile', '')
            patient_email = ''

        # Get created by info
        created_by_name = appt.created_by_account.name if appt.created_by_account else 'Unknown'

        # Get services
        service_names = ", ".join([svc.get('name', '') for svc in appt.services])

        # Get service items
        all_items = []
        for service_group in appt.services:
            items = service_group.get('items', [])
            for item in items:
                item_name = item.get('name', '')
                if item_name:
                    all_items.append(item_name)
        service_items = ', '.join(all_items)

        # Build row
        row = [
            appt.sgimed_appointment_id or str(appt.id),
            appt.start_datetime.astimezone(sgtz).strftime('%Y-%m-%d %H:%M'),
            appt.created_at.astimezone(sgtz).strftime('%Y-%m-%d %H:%M'),
            patient_name,
            patient_mobile,
            patient_email,
            created_by_name,
            service_names,
            service_items,
            appt.branch.get('name', ''),
            appt.status.value if appt.status else '',
            appt.payment_breakdown.get('total', 0),
            appt.corporate_code or '',
            corp_code.organization
        ]

        # Add patient survey data

        if appt.patient_survey:
            row.append(appt.patient_survey)

        # Add corporate survey data
        for key in corporate_survey_keys:
            if appt.corporate_survey and isinstance(appt.corporate_survey, dict):
                value = appt.corporate_survey.get(key, '')
                # Handle lists/arrays
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                row.append(value)
            else:
                row.append('')

        writer.writerow(row)

    # Prepare for streaming
    output.seek(0)

    # Generate filename with corporate code and date range
    filename = f"corporate_survey_{corp_code.code}_{datetime.now().strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Onsite Branch Models
class OnsiteBranchBase(BaseModel):
    branch_id: str
    corporate_code_id: str
    header: str | None = None
    start_date: datetime
    end_date: datetime
    # Branch fields
    address: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    url: str | None = None
    category: str | None = None  # Branch geographic category
    image_url: str | None = None

class OnsiteBranchUpdate(BaseModel):
    # Branch data
    branch_name: str | None = None
    address: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    url: str | None = None
    category: str | None = None  # Branch geographic category
    image: UploadFile | None = None

    # Onsite branch data
    branch_id: str | None = None
    corporate_code_id: str | None = None
    sgimed_branch_id: str | None = None  # Which SGiMed branch this onsite branch should route to
    header: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

class OnsiteBranchDetails(OnsiteBranchBase):
    id: str
    branch_name: str
    corporate_code: str
    sgimed_branch_id: str  # Which SGiMed branch this onsite branch routes to
    created_at: datetime
    updated_at: datetime

# Onsite Branch Endpoints
@router.get("/onsite-branches", response_model=list[OnsiteBranchDetails])
def get_onsite_branches(
    corporate_code_id: str | None = None,
    branch_id: str | None = None,
    appointment_category: AppointmentCategory = AppointmentCategory.GENERAL,
    db: Session = Depends(get_db)
):
    query = db.query(AppointmentOnsiteBranch)

    if corporate_code_id:
        query = query.filter(AppointmentOnsiteBranch.corporate_code_id == corporate_code_id)

    query = query.filter(AppointmentOnsiteBranch.category == appointment_category)

    if branch_id:
        query = query.filter(AppointmentOnsiteBranch.branch_id == branch_id)

    onsite_branches = query.order_by(AppointmentOnsiteBranch.start_date.desc()).all()

    result = []
    for ob in onsite_branches:
        branch = db.query(Branch).filter(Branch.id == ob.branch_id).first()
        corp_code = db.query(AppointmentCorporateCode).filter(AppointmentCorporateCode.id == ob.corporate_code_id).first()

        result.append(OnsiteBranchDetails(
            id=str(ob.id),
            branch_id=str(ob.branch_id),
            corporate_code_id=str(ob.corporate_code_id),
            header=ob.header,
            start_date=ob.start_date.astimezone(sgtz),
            end_date=ob.end_date.astimezone(sgtz),
            branch_name=branch.name if branch else "Unknown",
            corporate_code=corp_code.code if corp_code else "Unknown",
            sgimed_branch_id=branch.sgimed_branch_id if branch and branch.sgimed_branch_id else "Unknown",
            # Branch fields
            address=branch.address if branch else None,
            phone=branch.phone if branch else None,
            whatsapp=branch.whatsapp if branch else None,
            email=branch.email if branch else None,
            url=branch.url if branch else None,
            category=branch.category if branch else None,
            image_url=branch.image_url if branch else None,
            created_at=ob.created_at.astimezone(sgtz),
            updated_at=ob.updated_at.astimezone(sgtz)
        ))

    return result

@router.get("/onsite-branches/{onsite_id}", response_model=OnsiteBranchDetails)
def get_onsite_branch(onsite_id: int, db: Session = Depends(get_db)):
    onsite_branch = db.query(AppointmentOnsiteBranch).filter(
        AppointmentOnsiteBranch.id == onsite_id
    ).first()

    if not onsite_branch:
        raise HTTPJSONException(
            title="Not Found",
            message="Onsite branch not found",
            status_code=404
        )

    branch = db.query(Branch).filter(Branch.id == onsite_branch.branch_id).first()
    corp_code = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.id == onsite_branch.corporate_code_id
    ).first()

    return OnsiteBranchDetails(
        id=str(onsite_branch.id),
        branch_id=str(onsite_branch.branch_id),
        corporate_code_id=str(onsite_branch.corporate_code_id),
        header=onsite_branch.header,
        start_date=onsite_branch.start_date.astimezone(sgtz),
        end_date=onsite_branch.end_date.astimezone(sgtz),
        branch_name=branch.name if branch else "Unknown",
        corporate_code=corp_code.code if corp_code else "Unknown",
        sgimed_branch_id=branch.sgimed_branch_id if branch and branch.sgimed_branch_id else "Unknown",
        # Branch fields
        address=branch.address if branch else None,
        phone=branch.phone if branch else None,
        whatsapp=branch.whatsapp if branch else None,
        email=branch.email if branch else None,
        url=branch.url if branch else None,
        category=branch.category if branch else None,
        image_url=branch.image_url if branch else None,
        created_at=onsite_branch.created_at.astimezone(sgtz),
        updated_at=onsite_branch.updated_at.astimezone(sgtz)
    )

@router.put("/onsite-branches/{onsite_id}", response_model=SuccessResponse)
async def update_onsite_branch(onsite_id: int, req: OnsiteBranchUpdate = FormDepends(OnsiteBranchUpdate), db: Session = Depends(get_db)):
    onsite_branch = db.query(AppointmentOnsiteBranch).filter(
        AppointmentOnsiteBranch.id == onsite_id
    ).first()

    if not onsite_branch:
        raise HTTPJSONException(
            title="Not Found",
            message="Onsite branch not found",
            status_code=404
        )

    # Validate branch if provided
    if req.branch_id:
        branch = db.query(Branch).filter(Branch.id == req.branch_id).first()
        if not branch:
            raise HTTPJSONException(
                title="Invalid Branch",
                message="Branch not found",
                status_code=404
            )

    # Validate corporate code if provided
    if req.corporate_code_id:
        corp_code = db.query(AppointmentCorporateCode).filter(
            AppointmentCorporateCode.id == req.corporate_code_id
        ).first()
        if not corp_code:
            raise HTTPJSONException(
                title="Invalid Corporate Code",
                message="Corporate code not found",
                status_code=404
            )

    # Get the associated branch for updating branch fields
    branch = db.query(Branch).filter(Branch.id == onsite_branch.branch_id).first()
    if not branch:
        raise HTTPJSONException(
            title="Invalid Branch",
            message="Branch not found",
            status_code=404
        )

    # Update branch fields if provided
    if req.branch_name is not None:
        branch.name = req.branch_name
    if req.address is not None:
        branch.address = req.address
    if req.phone is not None:
        branch.phone = req.phone
    if req.whatsapp is not None:
        branch.whatsapp = req.whatsapp
    if req.email is not None:
        branch.email = req.email
    if req.url is not None:
        branch.url = req.url
    if req.category is not None:
        branch.category = req.category
    if req.sgimed_branch_id is not None:
        branch.sgimed_branch_id = req.sgimed_branch_id

    # Handle image upload if provided
    if req.image and req.image.filename:
        image_filename = f'branches/{branch.name}{osp.splitext(req.image.filename)[-1]}'
        image_bytes = await req.image.read()
        content_type = req.image.content_type if req.image.content_type else 'image/jpeg'
        resp = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
            file=image_bytes,
            path=image_filename,
            file_options={"content-type": content_type, "upsert": 'true'}
        )
        branch.image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(image_filename)

    # Update onsite branch fields
    if req.branch_id is not None:
        onsite_branch.branch_id = uuid.UUID(req.branch_id)
    if req.corporate_code_id is not None:
        onsite_branch.corporate_code_id = uuid.UUID(req.corporate_code_id)
    if req.header is not None:
        onsite_branch.header = req.header
    if req.start_date is not None:
        onsite_branch.start_date = req.start_date.astimezone(sgtz) if req.start_date.tzinfo else sgtz.localize(req.start_date)
    if req.end_date is not None:
        onsite_branch.end_date = req.end_date.astimezone(sgtz) if req.end_date.tzinfo else sgtz.localize(req.end_date)

    # Validate date range after updates
    if onsite_branch.start_date >= onsite_branch.end_date:
        raise HTTPJSONException(
            title="Invalid Date Range",
            message="Start date must be before end date",
            status_code=400
        )

    db.commit()
    return SuccessResponse(success=True)

@router.delete("/onsite-branches/{onsite_id}", response_model=SuccessResponse)
def delete_onsite_branch(onsite_id: int, db: Session = Depends(get_db)):
    """
    Delete an onsite branch and its associated calendar and branch.
    This performs cascading deletion to ensure all related resources are cleaned up.
    """
    onsite_branch = db.query(AppointmentOnsiteBranch).filter(
        AppointmentOnsiteBranch.id == onsite_id
    ).first()

    if not onsite_branch:
        raise HTTPJSONException(
            title="Not Found",
            message="Onsite branch not found",
            status_code=404
        )

    try:
        # Get the associated branch to find calendar information
        branch = db.query(Branch).filter(Branch.id == onsite_branch.branch_id).first()
        calendar_id = None
        if branch and branch.sgimed_calendar_id:
            calendar_id = branch.sgimed_calendar_id

        # Step 1: Delete the onsite branch first
        db.delete(onsite_branch)
        db.flush()  # Ensure onsite branch is deleted before proceeding

        # Step 2: Delete associated calendar if it exists
        if calendar_id:
            try:
                from utils.integrations.sgimed import delete_calendar
                delete_calendar(calendar_id)
            except Exception as e:
                # Log calendar deletion error but don't fail the entire operation
                logging.error(f"Failed to delete SGiMed calendar {calendar_id}: {e}", exc_info=True)

        # Step 3: Delete the associated branch
        if branch:
            db.delete(branch)

        db.commit()
        return SuccessResponse(success=True)

    except Exception as e:
        db.rollback()
        raise HTTPJSONException(
            title="Deletion Failed",
            message=f"Failed to delete onsite branch and associated resources: {str(e)}",
            status_code=500
        )

# onsite branch Creation Models
class OnsiteBranchCreate(BaseModel):
    # Branch data
    branch_name: str
    address: str
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    url: str | None = None
    category: str = "Central"  # Branch geographic category
    image: UploadFile | None = None

    # Onsite branch data
    corporate_code_id: str
    sgimed_branch_id: str | None = None  # Which SGiMed branch this onsite branch should route to
    sgimed_calendar_id: str | None = None  # Existing calendar ID to use, if None a new calendar will be created
    header: str | None = None
    start_date: datetime
    end_date: datetime
    appointment_category: AppointmentCategory = AppointmentCategory.GENERAL

class OnsiteBranchResponse(BaseModel):
    branch_id: str
    sgimed_calendar_id: str | None = None
    onsite_branch_id: str
    sgimed_branch_id: str  # Which SGiMed branch this onsite branch routes to

class AppointmentConstants(BaseModel):
    DEFAULT_ONSITE_BRANCH_ID: str
    DEFAULT_DOCTOR_ID: str

class SGiMedBranchOption(BaseModel):
    value: str
    label: str

# Helper Endpoint for SGiMed Branches
@router.get("/sgimed-branches", response_model=list[SGiMedBranchOption])
def get_sgimed_branches(db: Session = Depends(get_db)):
    """
    Get available SGiMed branches for onsite branch routing selection.
    Returns branches from database that have sgimed_appointment_type_id configured.
    """
    # Query branches with both sgimed_branch_id and sgimed_appointment_type_id
    branches = db.query(Branch).filter(
        Branch.branch_type == BranchType.MAIN,
        Branch.deleted == False
    ).all()

    # Convert to dropdown options using sgimed_branch_id as value and name as label
    options = [
        SGiMedBranchOption(value=branch.sgimed_branch_id, label=f"{branch.name} ({branch.sgimed_branch_id})")
        for branch in branches
        if branch.sgimed_branch_id
    ]

    return options

# onsite branch Creation Endpoint
@router.post("/onsite-branch", response_model=OnsiteBranchResponse)
async def create_onsite_branch(req: OnsiteBranchCreate = FormDepends(OnsiteBranchCreate), db: Session = Depends(get_db)):
    """
    Creates a new branch with calendar and associated onsite branch in one operation.
    This endpoint combines branch creation, calendar creation via SGiMed API,
    and onsite branch creation for streamlined testing and administration.
    """

    # Validate corporate code exists
    corp_code = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.id == req.corporate_code_id
    ).first()
    if not corp_code:
        raise HTTPJSONException(
            title="Invalid Corporate Code",
            message="Corporate code not found",
            status_code=404
        )

    # Validate date range
    if req.start_date >= req.end_date:
        raise HTTPJSONException(
            title="Invalid Date Range",
            message="Start date must be before end date",
            status_code=400
        )

    try:
        appointment_constants = AppointmentConstants.model_validate(get_config_value(db, 'APPOINTMENT_CONSTANTS', {}))

        # Determine which SGiMed branch to use for routing
        sgimed_branch_id = req.sgimed_branch_id if req.sgimed_branch_id else appointment_constants.DEFAULT_ONSITE_BRANCH_ID

        # Step 1: Create the branch
        branch = Branch(
            name=req.branch_name,
            address=req.address,
            phone=req.phone,
            whatsapp=req.whatsapp,
            email=req.email,
            url=req.url,
            sgimed_branch_id=sgimed_branch_id,  # Use selected branch or default
            category=req.category,
            branch_type=BranchType.ONSITE,
            hidden=True,
            deleted=False,
        )

        db.add(branch)
        db.flush()  # Get the branch ID without committing

        # Handle image upload if provided
        if req.image and req.image.filename:
            image_filename = f'branches/{req.branch_name}{osp.splitext(req.image.filename)[-1]}'
            image_bytes = await req.image.read()
            content_type = req.image.content_type if req.image.content_type else 'image/jpeg'
            resp = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).upload(
                file=image_bytes,
                path=image_filename,
                file_options={"content-type": content_type, "upsert": 'true'}
            )
            branch.image_url = supabase.storage.from_(SUPABASE_UPLOAD_BUCKET).get_public_url(image_filename)

        # Step 2: Handle calendar - use existing or create new
        calendar_id = None
        if req.sgimed_calendar_id:
            # Use existing calendar
            calendar_id = req.sgimed_calendar_id
            branch.sgimed_calendar_id = calendar_id
            logging.info(f"Using existing calendar {calendar_id} for branch {req.branch_name}")
        else:
            # Create new calendar via SGiMed API
            try:
                from utils.integrations.sgimed import create_calendar, CreateCalendarRequest

                calendar_data = CreateCalendarRequest(
                    branch_id=sgimed_branch_id,
                    name=req.branch_name,
                    remark=f"Onsite branch calendar: {req.branch_name}",
                    is_enabled=True
                )

                response = create_calendar(calendar_data)

                if response and "id" in response:
                    calendar_id = response["id"]
                    # Update the branch with the calendar ID
                    branch.sgimed_calendar_id = calendar_id
                    logging.info(f"Created new calendar {calendar_id} for branch {req.branch_name}")

            except Exception as e:
                # Log the error but don't fail the entire operation
                # The branch can still be created without a calendar
                logging.error(f"Calendar creation failed for branch {req.branch_name}: {e}")

        # Step 3: Create the onsite branch
        # Convert dates to Singapore timezone if needed
        start_date_sg = req.start_date.astimezone(sgtz) if req.start_date.tzinfo else sgtz.localize(req.start_date)
        end_date_sg = req.end_date.astimezone(sgtz) if req.end_date.tzinfo else sgtz.localize(req.end_date)

        onsite_branch = AppointmentOnsiteBranch(
            branch_id=branch.id,
            corporate_code_id=uuid.UUID(req.corporate_code_id),
            header=req.header,
            start_date=start_date_sg,
            end_date=end_date_sg
        )

        db.add(onsite_branch)
        db.commit()

        return OnsiteBranchResponse(
            branch_id=str(branch.id),
            sgimed_calendar_id=calendar_id,
            onsite_branch_id=str(onsite_branch.id),
            sgimed_branch_id=sgimed_branch_id
        )

    except Exception as e:
        db.rollback()
        raise HTTPJSONException(
            title="Creation Failed",
            message=f"Failed to create onsite branch: {str(e)}",
            status_code=500
        )

# Operating Hours Models
class OperatingHourBase(BaseModel):
    day: DayOfWeek
    start_time: time
    end_time: time
    cutoff_time: int = 0
    max_bookings: int = 1
    branch_id: str

class OperatingHourCreate(OperatingHourBase):
    pass

class OperatingHourUpdate(BaseModel):
    day: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    cutoff_time: int | None = None
    max_bookings: int | None = None

class OperatingHourDetails(OperatingHourBase):
    id: str
    branch_name: str
    created_at: datetime
    updated_at: datetime

class BranchOperatingHoursResponse(BaseModel):
    branch_id: str
    branch_name: str
    operating_hours: dict[str, list[dict[str, Any]]]

# Operating Hours Endpoints
@router.get("/operating-hours/{branch_id}", response_model=BranchOperatingHoursResponse)
def get_branch_operating_hours(branch_id: str, db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPJSONException(
            title="Not Found",
            message="Branch not found",
            status_code=404
        )

    operating_hours = db.query(AppointmentBranchOperatingHours).filter(
        AppointmentBranchOperatingHours.branch_id == branch_id
    ).all()

    # Group by day
    hours_by_day = {}
    for day in DayOfWeek:
        hours_by_day[day.value] = []

    for hour in operating_hours:
        hours_by_day[hour.day.value].append({
            "id": str(hour.id),
            "start_time": hour.start_time.strftime("%H:%M"),
            "end_time": hour.end_time.strftime("%H:%M"),
            "cutoff_time": hour.cutoff_time,
            "max_bookings": hour.max_bookings
        })

    return BranchOperatingHoursResponse(
        branch_id=str(branch.id),
        branch_name=branch.name,
        operating_hours=hours_by_day
    )

def _update_operating_hours(branch_id: str, req: dict, model_class, db: Session):
    """Helper function to update operating hours for any model class."""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPJSONException(
            title="Not Found",
            message="Branch not found",
            status_code=404
        )

    # Delete existing operating hours for this branch
    db.query(model_class).filter(
        model_class.branch_id == branch_id
    ).delete()

    # Add new operating hours
    for day_str, hours_list in req.items():
        try:
            day = DayOfWeek(day_str)
        except ValueError:
            logging.error(f"Invalid day value: {day_str}")
            continue

        for hour_data in hours_list:
            try:
                start_time = datetime.strptime(hour_data['start_time'], "%H:%M").time()
                end_time = datetime.strptime(hour_data['end_time'], "%H:%M").time()
                if model_class == AppointmentBranchOperatingHours and start_time >= end_time:
                    raise HTTPJSONException(
                        title="Invalid Time Range",
                        message=f"Start time must be before end time for {day_str}",
                        status_code=400
                    )
            except ValueError:
                raise HTTPJSONException(
                    title="Invalid Time Format",
                    message="Time must be in HH:MM format",
                    status_code=400
                )

            # Create operating hour with appropriate parameters based on model
            if model_class == AppointmentBranchOperatingHours:
                operating_hour = AppointmentBranchOperatingHours(
                    day=day,
                    start_time=start_time,
                    end_time=end_time,
                    cutoff_time=hour_data.get('cutoff_time', 0),
                    max_bookings=hour_data.get('max_bookings', 1),
                    branch_id=uuid.UUID(branch_id)
                )
            else:  # OperatingHour
                operating_hour = OperatingHour(
                    day=day,
                    start_time=start_time,
                    end_time=end_time,
                    cutoff_time=hour_data.get('cutoff_time', 0),
                    branch_id=branch_id
                )
            db.add(operating_hour)

    db.commit()

@router.put("/operating-hours/{branch_id}", response_model=SuccessResponse)
def update_branch_operating_hours(
    branch_id: str,
    req: dict,
    db: Session = Depends(get_db)
):
    _update_operating_hours(branch_id, req, AppointmentBranchOperatingHours, db)
    return SuccessResponse(success=True)

@router.post("/operating-hours", response_model=CreateResponse)
def create_operating_hour(req: OperatingHourCreate, db: Session = Depends(get_db)):
    # Validate branch exists
    branch = db.query(Branch).filter(Branch.id == req.branch_id).first()
    if not branch:
        raise HTTPJSONException(
            title="Not Found",
            message="Branch not found",
            status_code=404
        )

    operating_hour = AppointmentBranchOperatingHours(
        day=req.day,
        start_time=req.start_time,
        end_time=req.end_time,
        cutoff_time=req.cutoff_time,
        max_bookings=req.max_bookings,
        branch_id=uuid.UUID(req.branch_id)
    )

    db.add(operating_hour)
    db.commit()

    return CreateResponse(id=str(operating_hour.id))

@router.delete("/operating-hours/{hour_id}", response_model=SuccessResponse)
def delete_operating_hour(hour_id: str, db: Session = Depends(get_db)):
    operating_hour = db.query(AppointmentBranchOperatingHours).filter(
        AppointmentBranchOperatingHours.id == hour_id
    ).first()

    if not operating_hour:
        raise HTTPJSONException(
            title="Not Found",
            message="Operating hour not found",
            status_code=404
        )

    db.delete(operating_hour)
    db.commit()
    return SuccessResponse(success=True)

# Branch Operating Hours Models (for pinnacle_branches_operating_hours)
class BranchOperatingHourBase(BaseModel):
    day: DayOfWeek
    start_time: time
    end_time: time
    cutoff_time: int = 0
    branch_id: str

class BranchOperatingHourCreate(BranchOperatingHourBase):
    pass

class BranchOperatingHourUpdate(BaseModel):
    day: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    cutoff_time: int | None = None

class BranchOperatingHourDetails(BranchOperatingHourBase):
    id: str
    branch_name: str
    created_at: datetime
    updated_at: datetime

# Branch Operating Hours Endpoints (for pinnacle_branches_operating_hours)
@router.get("/branch-operating-hours/{branch_id}", response_model=BranchOperatingHoursResponse)
def get_branch_basic_operating_hours(branch_id: str, db: Session = Depends(get_db)):
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if not branch:
        raise HTTPJSONException(
            title="Not Found",
            message="Branch not found",
            status_code=404
        )

    operating_hours = db.query(OperatingHour).filter(
        OperatingHour.branch_id == branch_id
    ).all()

    # Group by day
    hours_by_day = {}
    for day in DayOfWeek:
        hours_by_day[day.value] = []

    for hour in operating_hours:
        hours_by_day[hour.day.value].append({
            "id": str(hour.id),
            "start_time": hour.start_time.strftime("%H:%M"),
            "end_time": hour.end_time.strftime("%H:%M"),
            "cutoff_time": hour.cutoff_time
        })

    return BranchOperatingHoursResponse(
        branch_id=str(branch.id),
        branch_name=branch.name,
        operating_hours=hours_by_day
    )

@router.put("/branch-operating-hours/{branch_id}", response_model=SuccessResponse)
def update_branch_basic_operating_hours(
    branch_id: str,
    req: dict,
    db: Session = Depends(get_db)
):
    _update_operating_hours(branch_id, req, OperatingHour, db)
    return SuccessResponse(success=True)

# Appointment Management Models
class AppointmentListItem(BaseModel):
    id: str
    sgimed_appointment_id: str | None
    patient_name: str
    patient_mobile: str
    services: list[str]
    branch_name: str
    start_datetime: datetime
    duration: int
    status: AppointmentStatus
    total_amount: float
    corporate_code: str | None
    patient_survey: str | None
    group_id: str | None
    is_guest: bool
    created_at: datetime

# Using utils.pagination.Page[AppointmentListItem] for response

class AppointmentStatusUpdate(BaseModel):
    status: AppointmentStatus
    reason: str | None = None
    notes: str | None = None


# Appointment Management Endpoints
@router.get("/appointments", response_model=Page[AppointmentListItem])
def get_appointments(
    pagination: PaginationInput = Depends(),
    search: str | None = None,
    status: AppointmentStatus | None = None,
    branch_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    service_group_id: str | None = None,
    corporate_code: str | None = None,
    sort_by: str | None = None,
    sort_order: str | None = None,
    export_csv: bool = False,
    db: Session = Depends(get_db)
):
    # Build base query with Singapore timezone considerations
    query = db.query(Appointment) \
        .options(
            joinedload(Appointment.account).load_only(Account.name),
        ) \
        .filter(
            Appointment.status.not_in([AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED])
        )

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Appointment.account.has(Account.name.ilike(search_term)),
                cast(Appointment.guests, String).ilike(search_term)
            )
        )
    if status:
        query = query.filter(Appointment.status == status)
    if branch_id:
        query = query.filter(Appointment.branch.op('->>')('id') == branch_id)
    if date_from:
        # Convert to Singapore timezone if needed
        date_from_sg = date_from.astimezone(sgtz) if date_from.tzinfo else sgtz.localize(date_from)
        query = query.filter(Appointment.start_datetime >= date_from_sg)

    if date_to:
        # Convert to Singapore timezone if needed
        date_to_sg = date_to.astimezone(sgtz) if date_to.tzinfo else sgtz.localize(date_to)
        query = query.filter(Appointment.start_datetime <= date_to_sg)

    if corporate_code:
        query = query.filter(Appointment.corporate_code == corporate_code)

    # Filter by service group if provided
    if service_group_id:
        # Services are stored as JSON array with structure: [{"id": "<service_group_id>", ...}]
        # Use JSON functions that work with json type (not jsonb)
        # This checks if any element in the services array has the matching id
        query = query.filter(
            text("services::jsonb @> :services").params(services=f'[{{"id": "{service_group_id}"}}]')
        )

    # Apply ordering before pagination
    # Determine the sort column
    sort_column = Appointment.start_datetime
    if sort_by == "created_at":
        sort_column = Appointment.created_at
    elif sort_by == "start_datetime":
        sort_column = Appointment.start_datetime

    # Apply sort order with null handling
    # SQLAlchemy's nullslast() and nullsfirst() ensure consistent ordering
    if sort_order == "asc":
        query = query.order_by(sort_column.asc().nullslast())
    else:
        query = query.order_by(sort_column.desc().nullsfirst())

    # Use pagination utility
    page_result = paginate(query, db, pagination)

    # Transform the raw appointment data to AppointmentListItem
    appointment_items = []
    for appt in page_result.data:
        # Extract patient name and mobile (adjusted for actual data structure)
        patient_name = "Guest"
        patient_mobile = ""

        if appt.account:
            patient_name = getattr(appt.account, 'name', 'Unknown')
            patient_mobile = getattr(appt.account, 'mobile', '')
        elif appt.guests and len(appt.guests) > 0:
            patient_name = appt.guests[0].get('name', 'Guest')
            patient_mobile = appt.guests[0].get('mobile', '')

        service_names = [svc['name'] for svc in appt.services]

        # Convert timestamps to Singapore timezone
        start_datetime_sg = appt.start_datetime.astimezone(sgtz)
        created_at_sg = appt.created_at.astimezone(sgtz)

        appointment_items.append(AppointmentListItem(
            id=str(appt.id),
            sgimed_appointment_id=appt.sgimed_appointment_id,
            patient_name=patient_name,
            patient_mobile=patient_mobile,
            services=service_names,
            branch_name=appt.branch['name'],
            start_datetime=start_datetime_sg,
            duration=appt.duration,
            status=appt.status,
            total_amount=appt.payment_breakdown.get('total', 0),
            corporate_code=appt.corporate_code,
            group_id=appt.group_id,
            is_guest=appt.account_id is None,
            patient_survey=appt.patient_survey,
            created_at=created_at_sg
        ))

    # Return paginated result with transformed data
    return Page[AppointmentListItem](
        pager=page_result.pager,
        data=appointment_items
    )

class AppointmentFiltersResponse(BaseModel):
    statuses: list[dict[str, str]]
    branches: list[dict[str, str]]
    service_groups: list[dict[str, str]]
    corporate_codes: list[dict[str, str]]

@router.get("/appointments/filters", response_model=AppointmentFiltersResponse)
def get_appointment_filters(db: Session = Depends(get_db)):
    """
    Get available filter values for the appointments list.
    Returns dropdown options for status, branches, service groups, and corporate codes.
    """
    # Get all appointment statuses except internal ones
    statuses = [
        {"value": status.value, "label": status.value.replace("_", " ").title()}
        for status in AppointmentStatus
        if status not in [AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED]
    ]

    # Get all branches that are not deleted
    branches_query = db.query(Branch).filter(
        Branch.deleted == False
    ).order_by(Branch.name).all()

    branches = [
        {"value": str(branch.id), "label": branch.name}
        for branch in branches_query
    ]

    # Get all service groups ordered by index
    service_groups_query = db.query(AppointmentServiceGroup).order_by(
        AppointmentServiceGroup.corporate_code_id.desc(),
        AppointmentServiceGroup.index
    ).all()

    service_groups = [
        {"value": str(sg.id), "label": sg.name}
        for sg in service_groups_query
    ]

    # Get all active corporate codes
    corporate_codes_query = db.query(AppointmentCorporateCode).filter(
        AppointmentCorporateCode.is_active == True
    ).order_by(AppointmentCorporateCode.code).all()

    corporate_codes = [
        {"value": cc.code, "label": f"{cc.code} - {cc.organization}"}
        for cc in corporate_codes_query
    ]

    return AppointmentFiltersResponse(
        statuses=statuses,
        branches=branches,
        service_groups=service_groups,
        corporate_codes=corporate_codes
    )

@router.get('/export')
def export_appointments(
    search: str | None = None,
    status: AppointmentStatus | None = None,
    branch_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    service_group_id: str | None = None,
    corporate_code: str | None = None,
    db: Session = Depends(get_db)
) -> StreamingResponse:
    filters = {
        "search": search,
        "status": status,
        "branch_id": branch_id,
        "date_from": date_from,
        "date_to": date_to,
        "service_group_id": service_group_id,
        "corporate_code": corporate_code
    }
    filters = {k: v for k, v in filters.items() if v is not None}

    return get_csv_response(
        db,
        params=AdminQueryApiParams(
            page=1,
            rows=None,
            filters=filters,
            order_by=[]
        )
    )

@router.put("/{appointment_id}/status", response_model=SuccessResponse)
def update_appointment_status(
    appointment_id: str,
    req: AppointmentStatusUpdate,
    db: Session = Depends(get_db)
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id
    ).first()

    if not appointment:
        raise HTTPJSONException(
            title="Not Found",
            message="Appointment not found",
            status_code=404
        )

    appointment.status = req.status
    # Update timestamp is handled automatically by SQLAlchemy
    db.commit()

    return SuccessResponse(success=True)
