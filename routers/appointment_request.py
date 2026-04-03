from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from models.appointment_request import AppointmentRequest, RequestStatus
from models.specialist import Specialist
from models.patient import AccountFirebase
from models.email_template import EmailTemplate
from schemas.appointment_request import (
    AppointmentRequestCreate,
    AppointmentRequestStatusUpdate,
    AppointmentRequestResponse,
)

from fastapi import BackgroundTasks
from models import get_db
from routers.patient.utils import validate_firebase_token
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import os

router = APIRouter(prefix="/appointment-requests", tags=["Appointment Requests"])

CLINIC_NAME = os.getenv("CLINIC_NAME", "Pinnacle SG")
MAIL_USER   = os.getenv("MAIL_USER", "gk2792523@gmail.com")
MAIL_PASS   = os.getenv("MAIL_PASS", "ohnsabajcfjzmycg")
MAIL_FROM   = os.getenv("MAIL_FROM", MAIL_USER)


# ── Email sending ──────────────────────────────────────────────────────────────

def send_email(to: str, subject: str, body_text: str, body_html: str | None = None):
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{CLINIC_NAME} <{MAIL_FROM}>"
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(MAIL_USER, MAIL_PASS)
            server.send_message(msg)
        print(f"[EMAIL SENT] To: {to} | Subject: {subject}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


# 1. Keep this for fetching the template object from DB
def _get_template(db: Session, key: str) -> EmailTemplate | None:
    return db.query(EmailTemplate).filter(EmailTemplate.template_key == key).first()

# 2. Add this helper to handle the string replacement
def _render_string(template_str: str | None, variables: dict) -> str:
    if not template_str:
        return ""
    for k, v in variables.items():
        template_str = template_str.replace("{{" + k + "}}", str(v) if v else "")
    return template_str

def _build_and_send(
    db: Session,
    background_tasks: BackgroundTasks,
    specialist: Specialist,
    payload: AppointmentRequestCreate,
):
    base_vars = {"clinic_name": CLINIC_NAME}

    # -- Specialist notification variables --
    spec_vars = {
        **base_vars,
        "patient_name":   payload.patient_name,
        "patient_dob":    payload.patient_dob or "Not provided",
        "contact_number": payload.contact_number,
        "email":          payload.email,
        "preferred_days": payload.preferred_days or "Flexible",
        "preferred_time": payload.preferred_time or "Flexible",
        "reason":          payload.reason or "General Consultation",
    }

    spec_tpl = _get_template(db, "specialist_notification")
    
    if spec_tpl:
        # FIX: Use the new render helper, NOT _get_template
        spec_subject   = _render_string(spec_tpl.subject, spec_vars)
        spec_body_text = _render_string(spec_tpl.body_text, spec_vars)
        spec_body_html = _render_string(spec_tpl.body_html, spec_vars)
    else:
        # Fallback (Hardcoded)
        spec_subject   = f"[{CLINIC_NAME}] New Booking Request: {payload.patient_name}"
        spec_body_text = "New Request received."
        spec_body_html = f"<html>...</html>" # (Your existing fallback HTML)

    # -- Patient confirmation variables --
    pat_vars = {
        **base_vars,
        "patient_name":      payload.patient_name,
        "specialist_title":  specialist.title or "",
        "specialist_name":   specialist.name,
        "contact_number":    payload.contact_number,
    }

    pat_tpl = _get_template(db, "patient_confirmation")
    
    if pat_tpl:
        # FIX: Use the new render helper here too
        pat_subject   = _render_string(pat_tpl.subject, pat_vars)
        pat_body_text = _render_string(pat_tpl.body_text, pat_vars)
        pat_body_html = _render_string(pat_tpl.body_html, pat_vars)
    else:
        # Fallback (Hardcoded)
        pat_subject   = f"Your Request with {CLINIC_NAME} is Received"
        pat_body_text = "Request received."
        pat_body_html = f"<html>...</html>" # (Your existing fallback HTML)

    background_tasks.add_task(send_email, specialist.appointment_email, spec_subject, spec_body_text, spec_body_html)
    background_tasks.add_task(send_email, payload.email, pat_subject, pat_body_text, pat_body_html)

# ── Admin routes FIRST (before wildcard /{request_id}) ────────────────────────

@router.get("/admin/all", response_model=List[AppointmentRequestResponse])
def get_all_admin(
    status: Optional[RequestStatus] = None,
    specialist_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(AppointmentRequest).options(joinedload(AppointmentRequest.specialist))
    if status:
        query = query.filter(AppointmentRequest.status == status)
    if specialist_id:
        query = query.filter(AppointmentRequest.specialist_id == specialist_id)
    return query.order_by(AppointmentRequest.submitted_at.desc()).all()


@router.get("/admin/by-status/{status}", response_model=List[AppointmentRequestResponse])
def get_by_status_admin(status: RequestStatus, db: Session = Depends(get_db)):
    return (
        db.query(AppointmentRequest)
        .options(joinedload(AppointmentRequest.specialist))
        .filter(AppointmentRequest.status == status)
        .order_by(AppointmentRequest.submitted_at.desc())
        .all()
    )


@router.patch("/admin/{request_id}/status", response_model=AppointmentRequestResponse)
def update_status_admin(
    request_id: int,
    payload: AppointmentRequestStatusUpdate,
    db: Session = Depends(get_db),
):
    record = db.query(AppointmentRequest).filter(AppointmentRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    record.status = payload.status
    record.status_message = payload.status_message
    db.commit()
    db.refresh(record)
    return record


@router.get("/admin/{request_id}", response_model=AppointmentRequestResponse)
def get_one_admin(request_id: int, db: Session = Depends(get_db)):
    record = (
        db.query(AppointmentRequest)
        .options(joinedload(AppointmentRequest.specialist))
        .filter(AppointmentRequest.id == request_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    return record


# ── Patient routes (token protected) ──────────────────────────────────────────

@router.get("/my-requests", response_model=List[AppointmentRequestResponse])
def get_my_requests(
    firebase_uid: str = Depends(validate_firebase_token),
    db: Session = Depends(get_db),
):
    firebase_auth = db.query(AccountFirebase).filter(
        AccountFirebase.firebase_uid == firebase_uid
    ).first()
    if not firebase_auth:
        raise HTTPException(status_code=401, detail="Unauthorised")
    return (
        db.query(AppointmentRequest)
        .options(joinedload(AppointmentRequest.specialist))
        .filter(AppointmentRequest.email == firebase_auth.account.email)
        .order_by(AppointmentRequest.submitted_at.desc())
        .all()
    )


@router.get("/my-requests/{request_id}", response_model=AppointmentRequestResponse)
def get_my_request_detail(
    request_id: int,
    firebase_uid: str = Depends(validate_firebase_token),
    db: Session = Depends(get_db),
):
    firebase_auth = db.query(AccountFirebase).filter(
        AccountFirebase.firebase_uid == firebase_uid
    ).first()
    if not firebase_auth:
        raise HTTPException(status_code=401, detail="Unauthorised")
    record = (
        db.query(AppointmentRequest)
        .options(joinedload(AppointmentRequest.specialist))
        .filter(
            AppointmentRequest.id == request_id,
            AppointmentRequest.email == firebase_auth.account.email,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    return record


# ── General routes ─────────────────────────────────────────────────────────────

@router.get("/", response_model=List[AppointmentRequestResponse])
def get_all(db: Session = Depends(get_db)):
    return db.query(AppointmentRequest).order_by(AppointmentRequest.submitted_at.desc()).all()


@router.post("/", response_model=AppointmentRequestResponse)
def create(
    payload: AppointmentRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    specialist = db.query(Specialist).filter(Specialist.id == payload.specialist_id).first()
    if not specialist:
        raise HTTPException(status_code=404, detail="Specialist not found")

    record = AppointmentRequest(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    _build_and_send(db, background_tasks, specialist, payload)

    return record


# ── Wildcard routes LAST ───────────────────────────────────────────────────────

@router.get("/by-status/{status}", response_model=List[AppointmentRequestResponse])
def get_by_status(status: RequestStatus, db: Session = Depends(get_db)):
    return (
        db.query(AppointmentRequest)
        .filter(AppointmentRequest.status == status)
        .order_by(AppointmentRequest.submitted_at.desc())
        .all()
    )


@router.patch("/{request_id}/status", response_model=AppointmentRequestResponse)
def update_status(
    request_id: int,
    payload: AppointmentRequestStatusUpdate,
    db: Session = Depends(get_db),
):
    record = db.query(AppointmentRequest).filter(AppointmentRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    record.status = payload.status
    record.status_message = payload.status_message
    db.commit()
    db.refresh(record)
    return record


@router.get("/{request_id}", response_model=AppointmentRequestResponse)
def get_one(request_id: int, db: Session = Depends(get_db)):
    record = db.query(AppointmentRequest).filter(AppointmentRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    return record
