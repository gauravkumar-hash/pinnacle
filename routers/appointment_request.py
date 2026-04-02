from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from models.appointment_request import AppointmentRequest, RequestStatus
from models.specialist import Specialist
from schemas.appointment_request import (
    AppointmentRequestCreate,
    AppointmentRequestStatusUpdate,
    AppointmentRequestResponse
)
from models import get_db
import smtplib
from email.mime.text import MIMEText

router = APIRouter(prefix="/appointment-requests", tags=["Appointment Requests"])


def send_email(to: str, subject: str, body: str):
    # replace with your SMTP config or plug in SendGrid / Resend etc.
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = "noreply@yourclinic.com"
    msg["To"] = to
    # with smtplib.SMTP("smtp.yourclinic.com", 587) as server:
    #     server.login("user", "password")
    #     server.send_message(msg)
    print(f"[EMAIL] To: {to} | Subject: {subject}")   # placeholder for testing


@router.get("/", response_model=List[AppointmentRequestResponse])
def get_all(db: Session = Depends(get_db)):
    return db.query(AppointmentRequest).order_by(AppointmentRequest.submitted_at.desc()).all()


@router.get("/by-status/{status}", response_model=List[AppointmentRequestResponse])
def get_by_status(status: RequestStatus, db: Session = Depends(get_db)):
    return (
        db.query(AppointmentRequest)
        .filter(AppointmentRequest.status == status)
        .order_by(AppointmentRequest.submitted_at.desc())
        .all()
    )


@router.get("/{request_id}", response_model=AppointmentRequestResponse)
def get_one(request_id: int, db: Session = Depends(get_db)):
    record = db.query(AppointmentRequest).filter(AppointmentRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    return record


@router.post("/", response_model=AppointmentRequestResponse)
def create(payload: AppointmentRequestCreate, db: Session = Depends(get_db)):
    # fetch specialist to get their appointment email
    specialist = db.query(Specialist).filter(Specialist.id == payload.specialist_id).first()
    if not specialist:
        raise HTTPException(status_code=404, detail="Specialist not found")

    # save request
    record = AppointmentRequest(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)

    # email to specialist
    send_email(
        to=specialist.appointment_email,
        subject=f"New Appointment Request — {payload.patient_name}",
        body=f"""
You have a new appointment request.

Patient: {payload.patient_name}
DOB: {payload.patient_dob or 'Not provided'}
Contact: {payload.contact_number}
Email: {payload.email}
Preferred Days: {payload.preferred_days or 'Not specified'}
Preferred Time: {payload.preferred_time or 'Not specified'}
Reason: {payload.reason or 'Not provided'}

Please reach out to the patient to arrange their appointment.
        """.strip()
    )

    # email to patient
    send_email(
        to=payload.email,
        subject="Your Appointment Request Has Been Received",
        body=f"""
Dear {payload.patient_name},

Your appointment request with {specialist.title} {specialist.name} has been received.

{specialist.title} {specialist.name}'s team will be in touch to arrange your appointment.

Thank you.
        """.strip()
    )

    return record


@router.patch("/{request_id}/status", response_model=AppointmentRequestResponse)
def update_status(
    request_id: int,
    payload: AppointmentRequestStatusUpdate,
    db: Session = Depends(get_db)
):
    record = db.query(AppointmentRequest).filter(AppointmentRequest.id == request_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Appointment request not found")
    record.status = payload.status
    record.status_message = payload.status_message
    db.commit()
    db.refresh(record)
    return record