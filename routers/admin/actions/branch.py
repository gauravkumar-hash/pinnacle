from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from models.model_enums import BranchType, CollectionMethod
from models.pinnacle import Blockoff, Branch
from utils import sg_datetime

class BranchDetails(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    services: list[str] = []
    is_open: bool
    is_toggleable: bool
    branch_type: BranchType

def get_branch_details(db: Session, branch: Branch):
    is_open=False
    is_toggleable=False

    curr_dt = sg_datetime.now()
    operating = branch.is_operating(db, curr_dt, CollectionMethod.WALKIN)
    if operating:
        is_open = True
        is_toggleable = True
    # When it is closed
    else:
        curr_date = curr_dt.date()
        curr_time = curr_dt.time()
        blockoff = db.query(Blockoff).join(Blockoff.branches).filter(
                Branch.id == branch.id,
                Blockoff.date == curr_date,
                Blockoff.start_time <= curr_time,
                Blockoff.end_time > curr_time,
                Blockoff.enabled == True,
                Blockoff.allow_toggle == True,
                Blockoff.deleted == False
            ).first()
        if blockoff:
            is_open = False
            is_toggleable = True

    return BranchDetails(
        id=str(branch.id),
        name=branch.name,
        address=branch.address,
        url=branch.url,
        image_url=branch.image_url,
        is_open=is_open,
        is_toggleable=is_toggleable,
        branch_type=branch.branch_type,
    )
