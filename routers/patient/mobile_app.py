from fastapi import APIRouter
from pydantic import BaseModel
from config import CURRENT_APP_VERSION, MIN_SUPPORTED_APP_VERSION

router = APIRouter()

class UpdateResp(BaseModel):
    update: bool
    force: bool = False

@router.get("/update_check")
def check_update(version: str):
    curr_version = int(version)
    return UpdateResp(
        update=curr_version < CURRENT_APP_VERSION,
        force=curr_version < MIN_SUPPORTED_APP_VERSION
    )