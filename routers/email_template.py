"""
Email Template Router
─────────────────────
Admins can create / read / update email templates stored in the database.
Templates support {{variable}} placeholders that are substituted at send time.

Available placeholders
──────────────────────
Both templates:
  {{clinic_name}}         – e.g. "Pinnacle SG"

Both templates:
  {{clinic_name}}         – e.g. "Pinnacle SG"
  {{patient_name}}
  {{contact_number}}
  {{email}}
  {{contact_email}}       – Alias for email
  {{date}}                – Normalized preferred day/date
  {{time_slot}}           – Normalized preferred time
  {{preferred_days}}      – Raw preferred day input
  {{preferred_time}}      – Raw preferred time input
  {{reason}}
  {{specialisation}}
  {{doctor_name}}
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
            "{{contact_number}}, {{email}}, {{contact_email}}, {{date}}, {{time_slot}}, "
            "{{preferred_days}}, {{preferred_time}}, {{reason}}"
        ),
        "body_html": """<html>
  <body style="font-family: Arial, sans-serif; background-color:#f7fbff; color:#333; margin:0; padding:0;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:auto; background:#ffffff; border:1px solid #e5e5e5;">
      <tr>
        <td style="background:#003e69; padding:20px; text-align:center;">
          <h2 style="color:#ffffff; margin:0;">New Appointment Request via PinnacleSG+</h2>
        </td>
      </tr>
      <tr>
        <td style="padding:25px;">
          <p>A new specialist appointment request has been submitted through <strong>PinnacleSG+</strong>.</p>
          <h3 style="color:#0874bd; margin-top:25px;">Patient Details</h3>
          <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse; margin-top:10px;">
            <tr style="background:#f0f7fd;"><td><strong>Name</strong></td><td>{{patient_name}}</td></tr>
            <tr style="background:#f0f7fd;"><td><strong>Contact Number</strong></td><td>{{contact_number}}</td></tr>
            <tr><td><strong>Email</strong></td><td>{{email}}</td></tr>
          </table>
          <h3 style="color:#0874bd; margin-top:25px;">Request Preferences</h3>
          <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse; margin-top:10px;">
            <tr style="background:#f0f7fd;"><td><strong>Date</strong></td><td>{{date}}</td></tr>
            <tr><td><strong>Time Slot</strong></td><td>{{time_slot}}</td></tr>
          </table>
          <div style="margin-top:25px; padding:12px; background:#58a2da; color:white; border-left:5px solid #003e69;">
            <strong>Action Required:</strong><br>Please contact the patient to finalise the appointment booking.
          </div>
        </td>
      </tr>
      <tr>
        <td style="background:#f0f7fd; padding:15px; text-align:center; font-size:12px; color:#666;">
          Automated notification from <strong>PinnacleSG+</strong>.
        </td>
      </tr>
    </table>
  </body>
</html>""",
        "body_text": (
            "New appointment request from {{patient_name}}.\n"
            "Contact: {{contact_number}} | {{email}}\n"
            "Date: {{date}}\n"
            "Time Slot: {{time_slot}}\n"
            "Reason: {{reason}}"
        ),
    },
    {
        "template_key": "patient_confirmation",
        "label": "Patient – Request Received Confirmation",
        "subject": "Appointment Request via PinnacleSG+",
        "description": (
            "Sent to the patient after they submit an appointment request.\n"
            "Placeholders: {{clinic_name}}, {{patient_name}}, {{specialisation}}, "
            "{{doctor_name}}, {{date}}, {{time_slot}}, {{preferred_days}}, "
            "{{preferred_time}}, {{contact_number}}, {{contact_email}}, {{email}}"
        ),
        "body_html": """<html>
  <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h2 style="color: #003e69; margin-bottom: 20px;">Appointment Request</h2>
    <p>Dear <strong>{{patient_name}}</strong>,</p>
    <p>Thank you for using <strong>PinnacleSG+</strong> to request your specialist appointment. Your appointment request details are as follows:</p>
    
    <ul style="list-style: none; padding: 0; margin: 20px 0;">
      <li style="margin-bottom: 8px;"><strong>- Specialization:</strong> {{specialisation}}</li>
      <li style="margin-bottom: 8px;"><strong>- Doctor:</strong> {{doctor_name}}</li>
      <li style="margin-bottom: 8px;"><strong>- Clinic:</strong> {{clinic_name}}</li>
      <li style="margin-bottom: 8px;"><strong>- Date:</strong> {{date}}</li>
      <li style="margin-bottom: 8px;"><strong>- Time Slot:</strong> {{time_slot}}</li>
    </ul>

    <p style="background: #f9f9f9; padding: 15px; border-left: 4px solid #58a2da; margin-top: 20px;">
      Please note that this is not an appointment confirmation, and the specialist team will review and reach out to you at <strong>{{contact_number}}</strong> or <strong>{{contact_email}}</strong> to arrange a suitable time slot.
    </p>
    
    <p style="margin-top: 20px;">
      For any further queries, you may reach out to<br>
      <a href="mailto:connect@pinnaclefamilyclinic.com.sg" style="color: #0874bd; text-decoration: none;">connect@pinnaclefamilyclinic.com.sg</a>.
    </p>
    
    <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
    <p style="font-size: 13px; color: #7f8c8d;">
      This is an automated email from <strong>PinnacleSG+</strong>. Please do not reply directly to this message.<br>
      <strong>Pinnacle Family Clinic Service Team</strong>
    </p>
  </body>
</html>""",
        "body_text": (
            "Appointment Request\n\n"
            "Dear {{patient_name}},\n\n"
            "Thank you for using PinnacleSG+ to request your specialist appointment. Your request details:\n"
            "- Specialization: {{specialisation}}\n"
            "- Doctor: {{doctor_name}}\n"
            "- Clinic: {{clinic_name}}\n"
            "- Date: {{date}}\n"
            "- Time Slot: {{time_slot}}\n\n"
            "Please note that this is not an appointment confirmation. Our team will contact you at {{contact_number}} or {{contact_email}}.\n\n"
            "For queries: connect@pinnaclefamilyclinic.com.sg\n\n"
            "Pinnacle Family Clinic Service Team"
        ),
    },
    {
        "template_key": "appointment_rescheduled",
        "label": "Patient – Appointment Rescheduled",
        "subject": "RESCHEDULED: Appointment Request via PinnacleSG+",
        "description": "Sent to the patient when their appointment request is rescheduled.",
        "body_html": """<html>
  <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h2 style="color: #003e69; margin-bottom: 20px;">Rescheduled Appointment Request</h2>
    <p>Dear <strong>{{patient_name}}</strong>,</p>
    <p>Your appointment request with <strong>PinnacleSG+</strong> has been rescheduled. Your updated request details are as follows:</p>
    
    <ul style="list-style: none; padding: 0; margin: 20px 0;">
      <li style="margin-bottom: 8px;"><strong>- Specialization:</strong> {{specialisation}}</li>
      <li style="margin-bottom: 8px;"><strong>- Doctor:</strong> {{doctor_name}}</li>
      <li style="margin-bottom: 8px;"><strong>- Clinic:</strong> {{clinic_name}}</li>
      <li style="margin-bottom: 8px;"><strong>- New Preferred Days:</strong> {{preferred_days}}</li>
      <li style="margin-bottom: 8px;"><strong>- New Preferred Time:</strong> {{preferred_time}}</li>
    </ul>

    <p style="background: #f9f9f9; padding: 15px; border-left: 4px solid #58a2da; margin-top: 20px;">
      Please note that this is still a request and our team will contact you at <strong>{{contact_number}}</strong> or <strong>{{contact_email}}</strong> to finalise the timing.
    </p>
    
    <p style="margin-top: 20px;">
      For any further queries, you may reach out to<br>
      <a href="mailto:connect@pinnaclefamilyclinic.com.sg" style="color: #0874bd; text-decoration: none;">connect@pinnaclefamilyclinic.com.sg</a>.
    </p>
    
    <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
    <p style="font-size: 13px; color: #7f8c8d;">
      This is an automated email from <strong>PinnacleSG+</strong>. Please do not reply directly to this message.<br>
      <strong>Pinnacle Family Clinic Service Team</strong>
    </p>
  </body>
</html>""",
        "body_text": "Your appointment request has been rescheduled to {{preferred_days}} {{preferred_time}}.",
    },
    {
        "template_key": "appointment_cancelled",
        "label": "Patient – Appointment Cancelled",
        "subject": "CANCELLED: Appointment Request via PinnacleSG+",
        "description": "Sent to the patient when their appointment request is cancelled.",
        "body_html": """<html>
  <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h2 style="color: #c0392b; margin-bottom: 20px;">Appointment Cancellation</h2>
    <p>Dear <strong>{{patient_name}}</strong>,</p>
    <p>We regret to inform you that your appointment request with <strong>{{doctor_name}}</strong> at <strong>{{clinic_name}}</strong> has been cancelled.</p>
    
    <p style="background: #fdf2f2; padding: 15px; border-left: 4px solid #e74c3c; margin-top: 20px; color: #c0392b;">
      <strong>Reason for Cancellation:</strong><br>
      {{reason}}
    </p>
    
    <p style="margin-top: 20px;">
      If you would like to book a new appointment, please visit our app or contact us directly.
    </p>
    
    <p style="margin-top: 20px;">
      For any further queries, you may reach out to<br>
      <a href="mailto:connect@pinnaclefamilyclinic.com.sg" style="color: #0874bd; text-decoration: none;">connect@pinnaclefamilyclinic.com.sg</a>.
    </p>
    
    <hr style="border: 0; border-top: 1px solid #eee; margin: 30px 0;" />
    <p style="font-size: 13px; color: #7f8c8d;">
      This is an automated email from <strong>PinnacleSG+</strong>. Please do not reply directly to this message.<br>
      <strong>Pinnacle Family Clinic Service Team</strong>
    </p>
  </body>
</html>""",
        "body_text": "Your appointment request with {{doctor_name}} has been cancelled. Reason: {{reason}}",
    },
    {
        "template_key": "specialist_reschedule_notification",
        "label": "Specialist – Booking Rescheduled",
        "subject": "RESCHEDULED: New Booking Request - {{patient_name}}",
        "description": "Sent to the specialist when a booking request is rescheduled.",
        "body_html": """<html>
  <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h2 style="color: #003e69; margin-bottom: 20px;">Booking Request Rescheduled</h2>
    <p>The following appointment request has been updated with new preferred timing:</p>
    <h3 style="color: #0874bd;">Patient Details</h3>
    <ul>
      <li><strong>Name:</strong> {{patient_name}}</li>
      <li><strong>Contact:</strong> {{contact_number}}</li>
      <li><strong>Email:</strong> {{email}}</li>
    </ul>
    <h3 style="color: #0874bd;">Updated Preferences</h3>
    <ul>
      <li><strong>New Date:</strong> {{date}}</li>
      <li><strong>New Time Slot:</strong> {{time_slot}}</li>
      <li><strong>Reason for Request:</strong> {{request_reason}}</li>
    </ul>
    <p style="background: #f9f9f9; padding: 10px; border-left: 4px solid #58a2da;">
      <strong>Action:</strong> Please contact the patient to finalise the booking.
    </p>
  </body>
</html>""",
        "body_text": "Booking request from {{patient_name}} has been rescheduled to {{date}} {{time_slot}}.",
    },
    {
        "template_key": "specialist_cancel_notification",
        "label": "Specialist – Booking Cancelled",
        "subject": "CANCELLED: Booking Request - {{patient_name}}",
        "description": "Sent to the specialist when a booking request is cancelled.",
        "body_html": """<html>
  <body style="font-family: sans-serif; color: #333; line-height: 1.6;">
    <h2 style="color: #c0392b; margin-bottom: 20px;">Booking Request Cancelled</h2>
    <p>The appointment request for <strong>{{patient_name}}</strong> has been cancelled.</p>
    <p style="background: #fdf2f2; padding: 15px; border-left: 4px solid #e74c3c; color: #c0392b;">
      <strong>Reason for Cancellation:</strong><br>
      {{reason}}
    </p>
  </body>
</html>""",
        "body_text": "Booking request from {{patient_name}} has been cancelled. Reason: {{reason}}",
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
