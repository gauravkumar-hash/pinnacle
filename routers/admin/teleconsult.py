from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, text
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from models import get_db
from models.document import Document
from models.model_enums import PatientType, TeleconsultStatus
from models.patient import Account
from models.payments import Invoice
from models.pinnacle import Branch, PinnacleAccount
from models.teleconsult import Teleconsult
from routers.patient.actions.teleconsult_flow_backend import teleconsult_invoice_billed_webhook
from utils import sg_datetime
from utils.fastapi import SuccessResp
from utils.integrations.sgimed import fetch_invoice_details, get_invoice_by_visit_id, update_queue_instructions
from utils.supabase_auth import get_admin_or_superadmin
from datetime import date, datetime, timedelta
import csv
import io

router = APIRouter(dependencies=[Depends(get_admin_or_superadmin)])

class TeleconsultAdminResp(BaseModel):
    id: str
    sgimed_patient_id: str
    sgimed_visit_id: str
    queue_number: Optional[str] = None
    checkin_time: datetime
    patient_type: PatientType
    patient_name: str
    patient_nric: str
    doctor_name: str
    branch_name: str
    corporate_code: Optional[str] = None
    hide_invoice: Optional[bool] = None
    status: TeleconsultStatus

@router.get('/', response_model=list[TeleconsultAdminResp])
def get_teleconsults(date: date, db: Session = Depends(get_db)) -> list[TeleconsultAdminResp]:
    curr_midnight_time = sg_datetime.midnight(date)
    teleconsults = db.query(Teleconsult) \
        .options(
            joinedload(Teleconsult.invoices).load_only(Invoice.hide_invoice),
            joinedload(Teleconsult.account).load_only(Account.sgimed_patient_id, Account.nric, Account.name),
            joinedload(Teleconsult.doctor).load_only(PinnacleAccount.name),
            joinedload(Teleconsult.branch).load_only(Branch.name)
        ) \
        .filter(
            Teleconsult.checkin_time >= curr_midnight_time,
            Teleconsult.checkin_time < curr_midnight_time + timedelta(days=1)
        ) \
        .all()

    return [
        TeleconsultAdminResp(
            id=str(teleconsult.id),
            sgimed_visit_id=teleconsult.sgimed_visit_id if teleconsult.sgimed_visit_id else "",
            queue_number=teleconsult.queue_number,
            checkin_time=teleconsult.checkin_time,
            sgimed_patient_id=teleconsult.account.sgimed_patient_id if teleconsult.account.sgimed_patient_id else "",
            patient_type=teleconsult.patient_type,
            patient_name=teleconsult.account.name,
            patient_nric=teleconsult.account.nric,
            doctor_name=teleconsult.doctor.name if teleconsult.doctor else "",
            branch_name=teleconsult.branch.name,
            corporate_code=teleconsult.corporate_code,
            hide_invoice=teleconsult.invoices[0].hide_invoice if teleconsult.invoices else None,
            status=teleconsult.status
        )
        for teleconsult in teleconsults
    ]

class ToggleHideInvoiceParams(BaseModel):
    id: str
    hide_invoice: bool

@router.post('/toggle_hide_invoice', response_model=SuccessResp)
def toggle_hide_invoice(req: ToggleHideInvoiceParams, db: Session = Depends(get_db)):
    record = db.query(Teleconsult).filter(Teleconsult.id == req.id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    if not record.invoices:
        raise HTTPException(status_code=404, detail="No invoice found")

    record.invoices[0].hide_invoice = req.hide_invoice
    doc = db.query(Document).filter(Document.sgimed_document_id == record.invoices[0].id).first()
    if doc:
        doc.hidden = req.hide_invoice
    db.commit()
    return SuccessResp(success=True)

@router.get('/update_invoice', response_model=SuccessResp)
def update_invoice(id: str, db: Session = Depends(get_db)):
    visit_id = id
    record = db.query(Teleconsult).filter(Teleconsult.sgimed_visit_id == visit_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    data = get_invoice_by_visit_id(visit_id)
    if not data:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice_id = data['id']
    invoice_details = fetch_invoice_details(invoice_id)
    if not invoice_details:
        raise HTTPException(status_code=404, detail="Invoice details not found")

    if record.invoices:
        print(f'Updating Invoice for {visit_id}')
        record.invoices[0].invoice_html = invoice_details.invoice_html
        record.invoices[0].mc_html = invoice_details.mc_html
        record.invoices[0].items = invoice_details.items
        record.invoices[0].prescriptions = invoice_details.prescriptions
        record.invoices[0].amount = invoice_details.invoice_dict['total']
        record.invoices[0].sgimed_last_edited = invoice_details.invoice_dict['last_edited']
        # Update total and balance if changed on invoice
        record.total = invoice_details.invoice_dict['total']
        paid_amt = round(sum([p.payment_amount for p in record.get_successful_payments()]), 2)
        if invoice_details.invoice_dict['patient_outstanding'] > paid_amt:
            record.balance = invoice_details.invoice_dict['patient_outstanding'] - paid_amt
        else:
            record.balance = 0.0
        db.commit()

        # Updating to checked out if patient_outstanding is $0
        if record.balance == 0 and record.status in [TeleconsultStatus.CONSULT_END, TeleconsultStatus.OUTSTANDING]:
            record.complete(db)
            update_queue_instructions(visit_id, record.status.value)

    else:
        print(f'New Invoice for {visit_id}')
        teleconsult_invoice_billed_webhook(**invoice_details.model_dump())

    return SuccessResp(success=True)

@router.get('/ongoing', response_model=list[TeleconsultAdminResp])
def get_ongoing_teleconsults(db: Session = Depends(get_db)):
    teleconsults = db.query(Teleconsult).options(
            joinedload(Teleconsult.invoices).load_only(Invoice.hide_invoice),
            joinedload(Teleconsult.account).load_only(Account.sgimed_patient_id, Account.nric, Account.name),
            joinedload(Teleconsult.doctor).load_only(PinnacleAccount.name),
            joinedload(Teleconsult.branch).load_only(Branch.name)
        ).filter(
            Teleconsult.status.not_in([TeleconsultStatus.PREPAYMENT, TeleconsultStatus.CHECKED_OUT])
        ).order_by(Teleconsult.checkin_time.desc()).all()

    return [
        TeleconsultAdminResp(
            id=str(teleconsult.id),
            sgimed_visit_id=teleconsult.sgimed_visit_id if teleconsult.sgimed_visit_id else "",
            queue_number=teleconsult.queue_number,
            checkin_time=teleconsult.checkin_time,
            sgimed_patient_id=teleconsult.account.sgimed_patient_id if teleconsult.account.sgimed_patient_id else "",
            patient_type=teleconsult.patient_type,
            patient_name=teleconsult.account.name,
            patient_nric=teleconsult.account.nric,
            doctor_name=teleconsult.doctor.name if teleconsult.doctor else "",
            branch_name=teleconsult.branch.name,
            corporate_code=teleconsult.corporate_code,
            hide_invoice=teleconsult.invoices[0].hide_invoice if teleconsult.invoices else None,
            status=teleconsult.status
        )
        for teleconsult in teleconsults
    ]

class UntagDoctorParams(BaseModel):
    id: str

@router.post('/untag_doctor', response_model=SuccessResp)
async def untag_doctor(req: UntagDoctorParams, db: Session = Depends(get_db)):
    updated = db.query(Teleconsult) \
        .filter(Teleconsult.id == req.id) \
        .update({Teleconsult.doctor_id: None})

    db.commit()
    return SuccessResp(success=bool(updated))

class UpdateStatusParams(BaseModel):
    id: str
    status: TeleconsultStatus

@router.post('/update_status', response_model=SuccessResp)
def update_status(req: UpdateStatusParams, db: Session = Depends(get_db)):
    updated = db.query(Teleconsult) \
        .filter(Teleconsult.id == req.id) \
        .update({Teleconsult.status: req.status})

    db.commit()
    return SuccessResp(success=bool(updated))

class TeleconsultReportResp(BaseModel):
    patient_name: str
    patient_id: str
    teleconsult_date: Optional[date] = None
    duration: Optional[str] = None
    doctor_name: Optional[str] = None
    status: str
    checkin_time: datetime
    teleconsult_start_time: Optional[datetime] = None
    teleconsult_join_time: Optional[datetime] = None
    teleconsult_end_time: Optional[datetime] = None
    checkout_time: Optional[datetime] = None

@router.get('/report')
def get_teleconsult_report(
    start_date: date = Query(..., description="Start date for checkin time filter"),
    end_date: date = Query(..., description="End date for checkin time filter"),
    db: Session = Depends(get_db)
):
    """
    Get teleconsult report with patient, doctor, timing information.

    Parameters:
    - start_date: Start date for checkin time filter (expects UTC, will be used as-is)
    - end_date: End date for checkin time filter (expects UTC, will be used as-is)
    - include_incomplete: If True, includes teleconsults where end_time is null or end_time < start_time
    """

    # Convert dates to SGT midnight datetime
    start_datetime = sg_datetime.midnight(start_date)
    end_datetime = sg_datetime.midnight(end_date) + timedelta(days=1)

    # Build the query using SQLAlchemy select
    stmt = select(
        Account.name.label("patient_name"),
        Account.nric.label("patient_id"),
        func.date(Teleconsult.teleconsult_start_time + text("interval '8 hours'")).label("teleconsult_date"),
        (Teleconsult.teleconsult_end_time - Teleconsult.teleconsult_start_time).label("duration"),
        PinnacleAccount.name.label("doctor_name"),
        Teleconsult.status,
        (Teleconsult.checkin_time + text("interval '8 hours'")).label("checkin_time"),
        (Teleconsult.teleconsult_start_time + text("interval '8 hours'")).label("teleconsult_start_time"),
        (Teleconsult.teleconsult_join_time + text("interval '8 hours'")).label("teleconsult_join_time"),
        (Teleconsult.teleconsult_end_time + text("interval '8 hours'")).label("teleconsult_end_time"),
        (Teleconsult.checkout_time + text("interval '8 hours'")).label("checkout_time")
    ).select_from(
        Teleconsult
    ).join(
        Account, Teleconsult.account_id == Account.id, isouter=True
    ).join(
        PinnacleAccount, Teleconsult.doctor_id == PinnacleAccount.id, isouter=True
    ).where(
        Teleconsult.doctor_id.isnot(None),
        Teleconsult.checkin_time >= start_datetime,
        Teleconsult.checkin_time < end_datetime
    )

    # Order by checkin_time
    stmt = stmt.order_by(Teleconsult.checkin_time.asc())

    # Execute the query
    result = db.execute(stmt)
    rows = result.fetchall()

    # Convert rows to response model
    teleconsult_reports = []
    for row in rows:
        # Format duration as string if it exists
        duration_str = None
        if row.duration:
            total_seconds = int(row.duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        teleconsult_reports.append(TeleconsultReportResp(
            patient_name=row.patient_name or "",
            patient_id=row.patient_id or "",
            teleconsult_date=row.teleconsult_date,
            duration=duration_str,
            doctor_name=row.doctor_name,
            status=row.status.value if row.status else "",
            checkin_time=row.checkin_time,
            teleconsult_start_time=row.teleconsult_start_time,
            teleconsult_join_time=row.teleconsult_join_time,
            teleconsult_end_time=row.teleconsult_end_time,
            checkout_time=row.checkout_time
        ))

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            'patient_name', 'patient_id', 'teleconsult_date', 'duration',
            'doctor_name', 'status', 'checkin_time', 'teleconsult_start_time',
            'teleconsult_join_time', 'teleconsult_end_time', 'checkout_time'
        ]
    )
    writer.writeheader()

    for report in teleconsult_reports:
        writer.writerow({
            'patient_name': report.patient_name,
            'patient_id': report.patient_id,
            'teleconsult_date': str(report.teleconsult_date) if report.teleconsult_date else '',
            'duration': report.duration or '',
            'doctor_name': report.doctor_name or '',
            'status': report.status,
            'checkin_time': str(report.checkin_time),
            'teleconsult_start_time': str(report.teleconsult_start_time) if report.teleconsult_start_time else '',
            'teleconsult_join_time': str(report.teleconsult_join_time) if report.teleconsult_join_time else '',
            'teleconsult_end_time': str(report.teleconsult_end_time) if report.teleconsult_end_time else '',
            'checkout_time': str(report.checkout_time) if report.checkout_time else ''
        })

    # Get CSV content and reset position
    output.seek(0)

    # Create filename with date range
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    filename = f"teleconsult_report_{start_str}_to_{end_str}.csv"

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type='text/csv',
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
