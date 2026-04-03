from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from models import Base  # adjust import to match your project's Base


class EmailTemplate(Base):
    __tablename__ = "email_templates"

    id = Column(Integer, primary_key=True, index=True)

    # Unique key used to look up the template in code, e.g. "patient_confirmation", "specialist_notification"
    template_key = Column(String(100), unique=True, nullable=False, index=True)

    # Human-readable label shown in the admin UI
    label = Column(String(200), nullable=False)

    subject = Column(String(300), nullable=False)

    # HTML body — supports {{variable}} placeholders (see docs below)
    body_html = Column(Text, nullable=False)

    # Fallback plain-text body
    body_text = Column(Text, nullable=False)

    # Optional description / placeholder reference shown in the admin UI
    description = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
