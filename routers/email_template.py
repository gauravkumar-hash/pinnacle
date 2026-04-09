"""
Email Template Router
─────────────────────
Admins can create / read / update email templates stored in the database.
Templates support {{variable}} placeholders that are substituted at send time.

Available placeholders
──────────────────────
Both templates:
  {{clinic_name}}         – e.g. "Pinnacle SG"

Patient confirmation template  (key: patient_confirmation)
  {{patient_name}}
  {{specialist_title}}    – e.g. "Dr."
  {{specialist_name}}
  {{contact_number}}

Specialist notification template  (key: specialist_notification)
  {{patient_name}}
  {{patient_dob}}
  {{contact_number}}
  {{email}}
  {{preferred_days}}
  {{preferred_time}}
  {{reason}}
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from models import get_db
from models.email_template import EmailTemplate
from schemas.email_template import (
    EmailTemplateCreate,
    EmailTemplateUpdate,
    EmailTemplateResponse,
)

router = APIRouter(prefix="/email-templates", tags=["Email Templates"])

# ── Default templates (used by /seed) ─────────────────────────────────────────

DEFAULT_TEMPLATES = [
    {
        "template_key": "specialist_notification",
        "label": "Specialist – New Booking Notification",
        "subject": "[{{clinic_name}}] New Booking Request: {{patient_name}}",
        "description": (
            "Sent to the specialist when a patient submits an appointment request.\n"
            "Placeholders: {{clinic_name}}, {{patient_name}}, {{patient_dob}}, "
            "{{contact_number}}, {{email}}, {{preferred_days}}, {{preferred_time}}, {{reason}}"
        ),
        "body_html": """<html>
  <body style="font-family: sans-serif; color: #333;">
    <h2 style="color: #2c3e50;">New Appointment Notification</h2>
    <p>You have received a new request through the <strong>{{clinic_name}}</strong> portal.</p>
    <hr />
    <h3>Patient Details</h3>
    <ul>
      <li><strong>Name:</strong> {{patient_name}}</li>
      <li><strong>DOB:</strong> {{patient_dob}}</li>
      <li><strong>Contact:</strong> {{contact_number}}</li>
      <li><strong>Email:</strong> {{email}}</li>
    </ul>
    <h3>Request Preferences</h3>
    <ul>
      <li><strong>Preferred Days:</strong> {{preferred_days}}</li>
      <li><strong>Preferred Time:</strong> {{preferred_time}}</li>
      <li><strong>Reason:</strong> {{reason}}</li>
    </ul>
    <p style="background:#f8f9fa;padding:10px;border-left:4px solid #2c3e50;">
      <strong>Action:</strong> Please contact the patient to finalise the booking.
    </p>
  </body>
</html>""",
        "body_text": (
            "New appointment request from {{patient_name}}.\n"
            "Contact: {{contact_number}} | {{email}}\n"
            "Preferred: {{preferred_days}} {{preferred_time}}\n"
            "Reason: {{reason}}"
        ),
    },
    {
        "template_key": "patient_confirmation",
        "label": "Patient – Request Received Confirmation",
        "subject": "Your Request with {{clinic_name}} is Received",
        "description": (
            "Sent to the patient after they submit an appointment request.\n"
            "Placeholders: {{clinic_name}}, {{patient_name}}, {{specialist_title}}, "
            "{{specialist_name}}, {{contact_number}}"
        ),
        "body_html": """<html>
  <body style="font-family: sans-serif; color: #333;">
    <h2 style="color: #27ae60;">Request Received</h2>
    <p>Dear {{patient_name}},</p>
    <p>Thank you for choosing <strong>{{clinic_name}}</strong>. Your appointment request with
       <strong>{{specialist_title}} {{specialist_name}}</strong> has been successfully received.</p>
    <p>Our team will review your details and contact you shortly at
       <strong>{{contact_number}}</strong> to arrange a suitable time.</p>
    <hr />
    <p style="font-size:12px;color:#7f8c8d;">
      This is an automated confirmation. You don't need to reply to this email.<br />
      <strong>{{clinic_name}} Health Team</strong>
    </p>
  </body>
</html>""",
        "body_text": (
            "Dear {{patient_name}},\n\n"
            "Your appointment request with {{specialist_title}} {{specialist_name}} "
            "at {{clinic_name}} has been received.\n"
            "We will contact you at {{contact_number}} shortly."
        ),
    },
]


# ── Helper ─────────────────────────────────────────────────────────────────────

def render_template(template: str, variables: dict) -> str:
    """Replace {{key}} placeholders with values from the variables dict."""
    for key, value in variables.items():
        template = template.replace("{{" + key + "}}", str(value) if value else "")
    return template


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[EmailTemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    return db.query(EmailTemplate).order_by(EmailTemplate.id).all()


@router.get("/{template_key}", response_model=EmailTemplateResponse)
def get_template(template_key: str, db: Session = Depends(get_db)):
    record = db.query(EmailTemplate).filter(
        EmailTemplate.template_key == template_key
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Template not found")
    return record


@router.post("/", response_model=EmailTemplateResponse, status_code=201)
def create_template(payload: EmailTemplateCreate, db: Session = Depends(get_db)):
    existing = db.query(EmailTemplate).filter(
        EmailTemplate.template_key == payload.template_key
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Template key already exists")
    record = EmailTemplate(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/{template_key}", response_model=EmailTemplateResponse)
def update_template(
    template_key: str,
    payload: EmailTemplateUpdate,
    db: Session = Depends(get_db),
):
    record = db.query(EmailTemplate).filter(
        EmailTemplate.template_key == template_key
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Template not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


@router.delete("/{template_key}", status_code=204)
def delete_template(template_key: str, db: Session = Depends(get_db)):
    record = db.query(EmailTemplate).filter(
        EmailTemplate.template_key == template_key
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(record)
    db.commit()


@router.post("/seed", status_code=201, summary="Seed default templates (safe – skips existing keys)")
def seed_default_templates(db: Session = Depends(get_db)):
    """
    Inserts the built-in default templates for 'specialist_notification' and
    'patient_confirmation' if they don't already exist.  Safe to call multiple times.
    """
    created = []
    for tpl in DEFAULT_TEMPLATES:
        exists = db.query(EmailTemplate).filter(
            EmailTemplate.template_key == tpl["template_key"]
        ).first()
        if not exists:
            db.add(EmailTemplate(**tpl))
            created.append(tpl["template_key"])
    db.commit()
    return {"seeded": created, "skipped": [t["template_key"] for t in DEFAULT_TEMPLATES if t["template_key"] not in created]}
