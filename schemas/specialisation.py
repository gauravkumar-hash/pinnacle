from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SpecialisationBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    display_order: int = 0
    active: bool = True


class SpecialisationCreate(SpecialisationBase):
    pass


class SpecialisationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    icon_url: Optional[str] = None
    banner_url: Optional[str] = None
    display_order: Optional[int] = None
    active: Optional[bool] = None


class SpecialisationResponse(SpecialisationBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}