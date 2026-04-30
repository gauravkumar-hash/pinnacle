from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from models.appointment_request import AppointmentRequest, RequestStatus
from models.specialist import Specialist
from models.service import ClinicService
from models.patient import AccountFirebase
from models.email_template import EmailTemplate
from schemas.appointment_request import (
    AppointmentRequestCreate,
    AppointmentRequestStatusUpdate,
    AppointmentRequestResponse,
    AppointmentRescheduleRequest,
    AppointmentCancelRequest,
)

from models import get_db
from routers.patient.utils import validate_firebase_token
from utils.email import send_email as resend_send_email
import html
import logging
import os

router = APIRouter(prefix="/appointment-requests", tags=["Appointment Requests"])

CLINIC_NAME = os.getenv("CLINIC_NAME", "Pinnacle SG")
MAIL_USER   = os.getenv("MAIL_USER", "gk2792523@gmail.com")
MAIL_PASS   = os.getenv("MAIL_PASS", "ohnsabajcfjzmycg")
MAIL_FROM   = os.getenv("MAIL_FROM", MAIL_USER)


# ── Email sending ──────────────────────────────────────────────────────────────

def send_email(
    to: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    cc_emails: list[str] | None = None,
):
    if not to:
        logging.error(f"[EMAIL ERROR] missing recipient, subject={subject}")
        return

    logging.info(f"[EMAIL SEND ATTEMPT] to={to} cc={cc_emails} subject={subject}")
    html_body = body_html if body_html else f"<pre>{html.escape(body_text)}</pre>"
    success = resend_send_email(MAIL_FROM, to, subject, html_body, cc_emails=cc_emails)
    if success:
        logging.info(f"[EMAIL SENT] To: {to} cc={cc_emails} | Subject: {subject}")
    else:
        logging.error(f"[EMAIL FAILED] To: {to} cc={cc_emails} | Subject: {subject}")


# 1. Keep this for fetching the template object from DB
def _get_template(db: Session, key: str) -> EmailTemplate | None:
    return db.query(EmailTemplate).filter(EmailTemplate.template_key == key).first()

# 2. Add this helper to handle the string replacement
import re

PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")

def _render_string(template_str: str | None, variables: dict) -> str:
    if not template_str:
        return ""

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        value = variables.get(key)
        if value is None:
            return ""
        return str(value)

    return PLACEHOLDER_RE.sub(_replace, template_str)

def _sanitize_clinic_name(value: str | None) -> str:
    if not value:
        return CLINIC_NAME
    if "def _get_template" in value or "EmailTemplate" in value or "{{" in value:
        return CLINIC_NAME
    return value.strip()


def _looks_like_date(value: str | None) -> bool:
    if not value:
        return False
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", value):
        return True
    if re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", value):
        return True
    if re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", value, re.I):
        return True
    return False


def _looks_like_time(value: str | None) -> bool:
    if not value:
        return False
    if re.search(r"\b\d{1,2}:\d{2}\b", value):
        return True
    if re.search(r"\b(?:am|pm)\b", value, re.I):
        return True
    if re.search(r"\b(?:morning|afternoon|evening|noon|night|midday|midnight)\b", value, re.I):
        return True
    return False


def _normalize_preferred_date_time(preferred_days: str | None, preferred_time: str | None) -> tuple[str, str]:
    days = (preferred_days or "").strip()
    time = (preferred_time or "").strip()

    # 1. If we have a clear date and a clear time, match them regardless of order
    if _looks_like_date(time) and _looks_like_time(days):
        return time, days
    if _looks_like_date(days) and _looks_like_time(time):
        return days, time
    
    # 2. If only one is clearly identifiable, treat the other as the counterpart if it exists
    if _looks_like_time(time) and days:
        return days, time
    if _looks_like_time(days) and time:
        return time, days
    if _looks_like_date(days) and time:
        return days, time
    if _looks_like_date(time) and days:
        return time, days

    # 3. Fallback to what we have, using "Flexible" instead of "TBA" for better UX
    return days or "Flexible", time or "Flexible"


def _get_common_vars(
    patient_name: str,
    patient_dob: Optional[str],
    contact_number: str,
    email: str,
    preferred_days: Optional[str],
    preferred_time: Optional[str],
    reason: Optional[str],
    clinic_name_val: str,
    specialisation_val: str,
    doctor_name_str: str,
) -> dict:
    norm_date, norm_time = _normalize_preferred_date_time(preferred_days, preferred_time)
    
    common = {
        "clinic_name":       clinic_name_val,
        "patient_name":      patient_name,
        "patient_dob":       patient_dob or "Not provided",
        "contact_number":    contact_number,
        "email":             email,
        "contact_email":     email,  # Alias
        "preferred_days":    norm_date,  # Use normalized values for consistency
        "preferred_time":    norm_time,
        "date":              norm_date,
        "time_slot":         norm_time,
        "reason":            reason or "General Consultation",
        "request_reason":    reason or "General Consultation", # Alias
        "specialisation":    specialisation_val,
        "doctor_name":       doctor_name_str,
    }
    return common


def _build_and_send(
    db: Session,
    background_tasks: BackgroundTasks,
    payload: AppointmentRequestCreate,
    specialist: Optional[Specialist] = None,
    service: Optional[ClinicService] = None,
):
    base_vars = {"clinic_name": CLINIC_NAME}

    # -- Notification logic based on what was booked --
    if specialist:
        doctor_name_str = f"{specialist.title} {specialist.name}" if specialist.title else specialist.name
        spec_email = specialist.appointment_email
        clinic_name_val = CLINIC_NAME
        specialisation_val = specialist.specialisation.name if specialist.specialisation else "Specialist Care"
    elif service:
        doctor_name_str = service.service_name # For service-based booking, use service name as "Doctor/Service"
        spec_email = service.contact_email or MAIL_FROM
        clinic_name_val = _sanitize_clinic_name(service.clinic_name)
        specialisation_val = service.specialisation.name if service.specialisation else "Clinic Service"
    else:
        # Fallback if both missing (shouldn't happen with valid payload)
        doctor_name_str = "TBA"
        spec_email = MAIL_FROM
        clinic_name_val = CLINIC_NAME
        specialisation_val = "Specialist Care"

    # -- Context construction --
    all_vars = _get_common_vars(
        patient_name=payload.patient_name,
        patient_dob=payload.patient_dob,
        contact_number=payload.contact_number,
        email=payload.email,
        preferred_days=payload.preferred_days,
        preferred_time=payload.preferred_time,
        reason=payload.reason,
        clinic_name_val=clinic_name_val,
        specialisation_val=specialisation_val,
        doctor_name_str=doctor_name_str,
    )

    spec_vars = all_vars
    pat_vars = all_vars

    spec_tpl = _get_template(db, "specialist_notification")
    pat_tpl = _get_template(db, "patient_confirmation")
    
    if spec_tpl:
        spec_subject   = _render_string(spec_tpl.subject, spec_vars)
        spec_body_text = _render_string(spec_tpl.body_text, spec_vars)
        spec_body_html = _render_string(spec_tpl.body_html, spec_vars)
    else:
        spec_subject   = f"[{clinic_name_val}] New Booking Request: {payload.patient_name}"
        spec_body_text = f"New Request received for {doctor_name_str}."
        spec_body_html = f"<html><body><h2>New Request</h2><p>Patient: {payload.patient_name}</p></body></html>"

    if pat_tpl:
        pat_subject   = _render_string(pat_tpl.subject, pat_vars)
        pat_body_text = _render_string(pat_tpl.body_text, pat_vars)
        pat_body_html = _render_string(pat_tpl.body_html, pat_vars)
    else:
        pat_subject   = f"Appointment Request via {clinic_name_val}"
        pat_body_text = f"Dear {payload.patient_name}, request received for {doctor_name_str}."
        pat_body_html = f"<html><body><h2>Request Received</h2><p>Dear {payload.patient_name}, thank you for choosing {clinic_name_val}.</p></body></html>"

    background_tasks.add_task(send_email, spec_email, spec_subject, spec_body_text, spec_body_html)
    patient_cc = [spec_email] if spec_email and spec_email != MAIL_FROM else None
    background_tasks.add_task(send_email, payload.email, pat_subject, pat_body_text, pat_body_html, patient_cc)


# ── Admin routes FIRST (before wildcard /{request_id}) ────────────────────────

@router.get("/admin/all", response_model=List[AppointmentRequestResponse])
def get_all_admin(
    status: Optional[RequestStatus] = None,
    specialist_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    query = db.query(AppointmentRequest).options(
        joinedload(AppointmentRequest.specialist),
        joinedload(AppointmentRequest.service)
    )
    if status:
        query = query.filter(AppointmentRequest.status == status)
    if specialist_id:
        query = query.filter(AppointmentRequest.specialist_id == specialist_id)
    return query.order_by(AppointmentRequest.submitted_at.desc()).all()


@router.get("/admin/by-status/{status}", response_model=List[AppointmentRequestResponse])
def get_by_status_admin(status: RequestStatus, db: Session = Depends(get_db)):
    return (
        db.query(AppointmentRequest)
        .options(
            joinedload(AppointmentRequest.specialist),
            joinedload(AppointmentRequest.service)
        )
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
        .options(
            joinedload(AppointmentRequest.specialist),
            joinedload(AppointmentRequest.service)
        )
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
        .options(
            joinedload(AppointmentRequest.specialist),
            joinedload(AppointmentRequest.service)
        )
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
        .options(
            joinedload(AppointmentRequest.specialist),
            joinedload(AppointmentRequest.service)
        )
        .filter(
            AppointmentRequest.id == request_id,
            AppointmentRequest.email == firebase_auth.account.email,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")
    return record


@router.post("/my-requests/{request_id}/reschedule", response_model=AppointmentRequestResponse)
def reschedule_my_request(
    request_id: int,
    payload: AppointmentRescheduleRequest,
    background_tasks: BackgroundTasks,
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
        .options(
            joinedload(AppointmentRequest.specialist),
            joinedload(AppointmentRequest.service)
        )
        .filter(
            AppointmentRequest.id == request_id,
            AppointmentRequest.email == firebase_auth.account.email,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")

    record.preferred_days = payload.preferred_days
    record.preferred_time = payload.preferred_time
    record.status = RequestStatus.RESCHEDULED
    db.commit()
    db.refresh(record)

    # Trigger notifications (reuse logic)
    _build_and_send_notification(db, background_tasks, record, is_reschedule=True)

    return record


@router.post("/my-requests/{request_id}/cancel", response_model=AppointmentRequestResponse)
def cancel_my_request(
    request_id: int,
    payload: AppointmentCancelRequest,
    background_tasks: BackgroundTasks,
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
        .options(
            joinedload(AppointmentRequest.specialist),
            joinedload(AppointmentRequest.service)
        )
        .filter(
            AppointmentRequest.id == request_id,
            AppointmentRequest.email == firebase_auth.account.email,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Request not found")

    record.status = RequestStatus.CANCELLED
    record.status_message = payload.reason
    db.commit()
    db.refresh(record)

    # Trigger notifications
    _build_and_send_notification(db, background_tasks, record, is_cancel=True)

    return record


def _build_and_send_notification(
    db: Session,
    background_tasks: BackgroundTasks,
    record: AppointmentRequest,
    is_reschedule: bool = False,
    is_cancel: bool = False,
):
    spec = record.specialist
    serv = record.service
    
    if spec:
        doctor_name_str = f"{spec.title} {spec.name}" if spec.title else spec.name
        spec_email = spec.appointment_email
        clinic_name_val = CLINIC_NAME
        specialisation_val = spec.specialisation.name if spec.specialisation else "Specialist Care"
    elif serv:
        doctor_name_str = serv.service_name
        spec_email = serv.contact_email or MAIL_FROM
        clinic_name_val = _sanitize_clinic_name(serv.clinic_name)
        specialisation_val = serv.specialisation.name if serv.specialisation else "Clinic Service"
    else:
        doctor_name_str = "TBA"
        spec_email = MAIL_FROM
        clinic_name_val = CLINIC_NAME
        specialisation_val = "Specialist Care"

    vars = _get_common_vars(
        patient_name=record.patient_name,
        patient_dob=record.patient_dob,
        contact_number=record.contact_number,
        email=record.email,
        preferred_days=record.preferred_days,
        preferred_time=record.preferred_time,
        reason=record.status_message or record.reason,
        clinic_name_val=clinic_name_val,
        specialisation_val=specialisation_val,
        doctor_name_str=doctor_name_str,
    )

    if is_reschedule:
        pat_tpl = _get_template(db, "appointment_rescheduled")
        spec_tpl = _get_template(db, "specialist_reschedule_notification")
    elif is_cancel:
        pat_tpl = _get_template(db, "appointment_cancelled")
        spec_tpl = _get_template(db, "specialist_cancel_notification")
    else:
        # Default/Confirmation
        pat_tpl = _get_template(db, "patient_confirmation")
        spec_tpl = _get_template(db, "specialist_notification")

    if pat_tpl:
        print(f"[EMAIL TASK] queue patient email to={record.email} template={pat_tpl.template_key}")
        patient_cc = [spec_email] if spec_email and spec_email != MAIL_FROM else None
        background_tasks.add_task(
            send_email,
            record.email,
            _render_string(pat_tpl.subject, vars),
            _render_string(pat_tpl.body_text, vars),
            _render_string(pat_tpl.body_html, vars),
            patient_cc,
        )
    else:
        print(f"[EMAIL TASK] no patient template found for {'reschedule' if is_reschedule else 'cancel' if is_cancel else 'confirmation'}")

    if spec_tpl:
        print(f"[EMAIL TASK] queue specialist email to={spec_email} template={spec_tpl.template_key}")
        background_tasks.add_task(send_email, spec_email, _render_string(spec_tpl.subject, vars), _render_string(spec_tpl.body_text, vars), _render_string(spec_tpl.body_html, vars))
    else:
        print(f"[EMAIL TASK] no specialist template found for {'reschedule' if is_reschedule else 'cancel' if is_cancel else 'confirmation'}")


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
    specialist = None
    service = None
    
    if payload.specialist_id:
        specialist = db.query(Specialist).filter(Specialist.id == payload.specialist_id).first()
        if not specialist:
            raise HTTPException(status_code=404, detail="Specialist not found")
    elif payload.service_id:
        service = db.query(ClinicService).filter(ClinicService.id == payload.service_id).first()
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")
    else:
        # If neither provided, check if specialisation_id is enough or throw error
        pass

    record = AppointmentRequest(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    _build_and_send(db, background_tasks, payload, specialist=specialist, service=service)

    return record


@router.post("/{request_id}/reschedule", response_model=AppointmentRequestResponse)
def reschedule(
    request_id: int,
    payload: AppointmentRescheduleRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    record = db.query(AppointmentRequest).options(joinedload(AppointmentRequest.specialist)).filter(AppointmentRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    
    record.preferred_days = payload.preferred_days
    record.preferred_time = payload.preferred_time
    record.status = RequestStatus.RESCHEDULED
    db.commit()
    db.refresh(record)

    # Trigger rescheduling emails
    spec = record.specialist
    service = record.service

    if spec:
        recipient_email = spec.appointment_email
        specialisation_val = spec.specialisation.name if spec.specialisation else "Specialist Care"
        doctor_name = f"{spec.title} {spec.name}" if spec.title else spec.name
    elif service:
        recipient_email = service.contact_email or MAIL_FROM
        specialisation_val = service.specialisation.name if service.specialisation else "Clinic Service"
        doctor_name = service.service_name
    else:
        recipient_email = None
        specialisation_val = record.specialisation.name if record.specialisation else "Specialist Care"
        doctor_name = "TBA"

    pat_vars = {
        "variant": "Rescheduled",
        "patient_name": record.patient_name,
        "specialisation": specialisation_val,
        "doctor_name": doctor_name,
        "clinic_name": CLINIC_NAME,
        "preferred_days": payload.preferred_days,
        "preferred_time": payload.preferred_time,
        "date": payload.preferred_days,
        "time_slot": payload.preferred_time,
        "contact_number": record.contact_number,
        "contact_email": record.email,
    }
    
    norm_date, norm_time = _normalize_preferred_date_time(payload.preferred_days, payload.preferred_time)

    spec_vars = {
        "patient_name": record.patient_name,
        "contact_number": record.contact_number,
        "email": record.email,
        "preferred_days": payload.preferred_days,
        "preferred_time": payload.preferred_time,
        "date": norm_date,
        "time_slot": norm_time,
        "request_reason": record.reason or "General Consultation",
        "doctor_name": doctor_name,
        "specialisation": specialisation_val,
    }

    resched_pat_tpl = _get_template(db, "appointment_rescheduled")
    resched_spec_tpl = _get_template(db, "specialist_reschedule_notification")

    if resched_pat_tpl:
        pat_subj = _render_string(resched_pat_tpl.subject, pat_vars)
        pat_html = _render_string(resched_pat_tpl.body_html, pat_vars)
        pat_text = _render_string(resched_pat_tpl.body_text, pat_vars)
        background_tasks.add_task(send_email, record.email, pat_subj, pat_text, pat_html)

    if resched_spec_tpl and recipient_email:
        spec_subj = _render_string(resched_spec_tpl.subject, spec_vars)
        spec_html = _render_string(resched_spec_tpl.body_html, spec_vars)
        spec_text = _render_string(resched_spec_tpl.body_text, spec_vars)
        background_tasks.add_task(send_email, recipient_email, spec_subj, spec_text, spec_html)

    return record


@router.post("/{request_id}/cancel", response_model=AppointmentRequestResponse)
def cancel(
    request_id: int,
    payload: AppointmentCancelRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    record = db.query(AppointmentRequest).options(joinedload(AppointmentRequest.specialist)).filter(AppointmentRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    
    record.status = RequestStatus.CANCELLED
    record.status_message = payload.reason
    db.commit()
    db.refresh(record)

    # Trigger cancellation emails
    spec = record.specialist
    service = record.service

    if spec:
        recipient_email = spec.appointment_email
        doctor_name_str = f"{spec.title} {spec.name}" if spec.title else spec.name
    elif service:
        recipient_email = service.contact_email or MAIL_FROM
        doctor_name_str = service.service_name
    else:
        recipient_email = None
        doctor_name_str = "TBA"

    vars = {
        "patient_name": record.patient_name,
        "doctor_name": doctor_name_str,
        "clinic_name": CLINIC_NAME,
        "reason": payload.reason,
    }

    cancel_pat_tpl = _get_template(db, "appointment_cancelled")
    cancel_spec_tpl = _get_template(db, "specialist_cancel_notification")

    if cancel_pat_tpl:
        pat_subj = _render_string(cancel_pat_tpl.subject, vars)
        pat_html = _render_string(cancel_pat_tpl.body_html, vars)
        pat_text = _render_string(cancel_pat_tpl.body_text, vars)
        background_tasks.add_task(send_email, record.email, pat_subj, pat_text, pat_html)

    if cancel_spec_tpl and recipient_email:
        spec_subj = _render_string(cancel_spec_tpl.subject, vars)
        spec_html = _render_string(cancel_spec_tpl.body_html, vars)
        spec_text = _render_string(cancel_spec_tpl.body_text, vars)
        background_tasks.add_task(send_email, recipient_email, spec_subj, spec_text, spec_html)

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
