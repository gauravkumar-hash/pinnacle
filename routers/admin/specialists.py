"""
Specialists Router - Reuses appointment logic with SPECIALIST category filter.

This router provides the same endpoints as appointment.py but hardcodes
AppointmentCategory.SPECIALIST for all operations by calling the appointment
functions directly.
"""
# TODOs
# - [ ] Test current appointment module
# - [ ] Review specialists.py
# - [ ] Develop specialists module frontend
# - [ ] Test & Deploy Specialist module frontend
# - [ ] Design patient app specialists API
# - [ ] Develop patient app specialists
# - [ ] Test & Deploy patient app specialists

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models import get_db
from models.model_enums import AppointmentCategory
from .utils import get_current_user

# Import schemas from appointment.py
from .appointment import (
    SuccessResponse,
    CreateResponse,
    ServiceGroupCreate,
    ServiceGroupUpdate,
    ServiceGroupDetails,
    CorporateCodeCreate,
    CorporateCodeUpdate,
    CorporateCodeDetails,
    OnsiteBranchDetails,
    # Import the actual endpoint functions
    get_service_groups,
    create_service_group,
    get_service_group,
    update_service_group,
    delete_service_group,
    get_corporate_codes,
    create_corporate_code,
    get_corporate_code,
    update_corporate_code,
    delete_corporate_code,
    get_onsite_branches,
    get_onsite_branch,
    delete_onsite_branch,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

# =============================================================================
# Service Group Endpoints (SPECIALIST category)
# =============================================================================

@router.get("/service-groups", response_model=list[ServiceGroupDetails])
def get_specialist_service_groups(db: Session = Depends(get_db)):
    """Get all service groups with SPECIALIST category."""
    return get_service_groups(category=AppointmentCategory.SPECIALIST)


@router.post("/service-groups", response_model=CreateResponse)
def create_specialist_service_group(req: ServiceGroupCreate):
    """Create a service group with SPECIALIST category."""
    # Override the category to SPECIALIST
    req.category = AppointmentCategory.SPECIALIST
    return create_service_group(req=req)


@router.get("/service-groups/{group_id}", response_model=ServiceGroupDetails)
def get_specialist_service_group(group_id: str):
    """Get a specific service group."""
    return get_service_group(group_id=group_id)


@router.put("/service-groups/{group_id}", response_model=SuccessResponse)
def update_specialist_service_group(group_id: str, req: ServiceGroupUpdate):
    """Update a service group."""
    # Prevent category change - keep it as SPECIALIST
    req.category = None
    return update_service_group(group_id=group_id, req=req)


@router.delete("/service-groups/{group_id}", response_model=SuccessResponse)
def delete_specialist_service_group(group_id: str):
    """Delete a service group."""
    return delete_service_group(group_id=group_id)


# =============================================================================
# Corporate Code Endpoints (SPECIALIST category)
# =============================================================================

@router.get("/corporate-codes", response_model=list[CorporateCodeDetails])
def get_specialist_corporate_codes(db: Session = Depends(get_db)):
    """Get all corporate codes with SPECIALIST category."""
    return get_corporate_codes(category=AppointmentCategory.SPECIALIST)


@router.post("/corporate-codes", response_model=CreateResponse)
def create_specialist_corporate_code(req: CorporateCodeCreate):
    """Create a corporate code with SPECIALIST category."""
    # Override the category to SPECIALIST
    req.category = AppointmentCategory.SPECIALIST
    return create_corporate_code(req=req)


@router.get("/corporate-codes/{code_id}", response_model=CorporateCodeDetails)
def get_specialist_corporate_code(code_id: str):
    """Get a specific corporate code."""
    return get_corporate_code(code_id=code_id)


@router.put("/corporate-codes/{code_id}", response_model=SuccessResponse)
def update_specialist_corporate_code(code_id: str, req: CorporateCodeUpdate):
    """Update a corporate code."""
    # Prevent category change - keep it as SPECIALIST
    req.category = None
    return update_corporate_code(code_id=code_id, req=req)


@router.delete("/corporate-codes/{code_id}", response_model=SuccessResponse)
def delete_specialist_corporate_code(code_id: str):
    """Delete a corporate code."""
    return delete_corporate_code(code_id=code_id)


# =============================================================================
# Onsite Branch Endpoints (SPECIALIST category)
# =============================================================================

@router.get("/onsite-branches", response_model=list[OnsiteBranchDetails])
def get_specialist_onsite_branches(
    corporate_code_id: str | None = None,
    branch_id: str | None = None,
    db: Session = Depends(get_db)
):
    """Get all onsite branches with SPECIALIST category."""
    return get_onsite_branches(
        corporate_code_id=corporate_code_id,
        branch_id=branch_id,
        appointment_category=AppointmentCategory.SPECIALIST,
        db=db
    )


@router.get("/onsite-branches/{onsite_id}", response_model=OnsiteBranchDetails)
def get_specialist_onsite_branch(onsite_id: int):
    """Get a specific onsite branch."""
    return get_onsite_branch(onsite_id=onsite_id)


@router.delete("/onsite-branches/{onsite_id}", response_model=SuccessResponse)
def delete_specialist_onsite_branch(onsite_id: int):
    """Delete an onsite branch."""
    return delete_onsite_branch(onsite_id=onsite_id)
