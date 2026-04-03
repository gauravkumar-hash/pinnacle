from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class EmailTemplateBase(BaseModel):
    label: str
    subject: str
    body_html: str
    body_text: str
    description: Optional[str] = None


class EmailTemplateCreate(EmailTemplateBase):
    template_key: str


class EmailTemplateUpdate(BaseModel):
    label: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    description: Optional[str] = None


class EmailTemplateResponse(EmailTemplateBase):
    id: int
    template_key: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
