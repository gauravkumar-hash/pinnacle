from collections import defaultdict
from datetime import date, timedelta
from io import StringIO
import csv
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from models import get_db
from models.document import Document
from models.model_enums import DocumentStatus, DocumentType, PatientType
from models.payments import PaymentMethod, PaymentProvider, PaymentReconciliation, PaymentType
from models.teleconsult import Teleconsult
from utils.excel import create_excel_with_styled_header
from utils.supabase_auth import get_superadmin
from utils import sg_datetime

router = APIRouter(dependencies=[Depends(get_superadmin)])

def convert_sqlalchemy_to_csv(
    db_results: list,
    header_mapping: dict = {},
    header_exclusions: list = [],
    filename: str = "export.csv",
    content_render: dict = {}
):
    # Handle empty result set
    if not db_results:
        raise HTTPException(status_code=500, detail="No data to export")

    # Create a string buffer to write CSV
    output = StringIO()
    writer = csv.writer(output)

    # Write headers (using first object's attributes)
    first_result = db_results[0]
    headers = [
        column.name
        for column in first_result.__table__.columns
        if column.name not in header_exclusions
    ]
    writer.writerow([header_mapping.get(header, header) for header in headers])

    # Write data rows
    for result in db_results:
        row = [
            content_render.get(header, lambda x: x)(getattr(result, header))
            for header in headers
        ]
        writer.writerow(row)

    # Prepare for streaming
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

def download_reconciliation_csv(db: Session, records: list[PaymentReconciliation], csv_filename: str):
    header_mapping = {
        "payment_id": "Transaction ID",
        "payment_type": "Transaction Category",
        "completed_at": "Paid On",
        "branch": "Branch",
        "patients": "Patient Details (NRIC Name)",
        "payment_provider": "Payment Provider",
        "payment_method": "Payment Method",
        "sgimed_invoice_id": "SGiMed Invoice ID",
        "payment_amount": "Transaction Amount",
        "payment_platform_fees": "Payment Platform Fees",
        "payment_amount_nett": "Nett Amount (after fees)",
    }

    content_mapping = {
        PaymentType.PREPAYMENT: 'Consult Payment',
        PaymentType.POSTPAYMENT: 'Outstanding Payment',
        PaymentType.APPOINTMENT: 'Appointment',
        PaymentProvider.APP_STRIPE: 'Stripe',
        PaymentProvider.APP_2C2P: '2C2P',
        PaymentMethod.CARD_STRIPE: 'Debit / Credit Card',
        PaymentMethod.CARD_2C2P: 'Debit / Credit Card',
        PaymentMethod.PAYNOW_STRIPE: 'PayNow',
    }

    content_render = {
        'patients': lambda x: '\n'.join(x),
        'completed_at': lambda x: sg_datetime.sg(x).strftime('%d/%m/%Y %H:%M:%S'),
        'payment_type': lambda x: content_mapping.get(x, x.value),
        'payment_provider': lambda x: content_mapping.get(x, x.value),
        'payment_method': lambda x: content_mapping.get(x, x.value),
    }
    header_exclusions = [
        'id',
        'sgimed_visit_id'
    ]

    return convert_sqlalchemy_to_csv(
        records,
        header_mapping,
        header_exclusions,
        filename=csv_filename,
        content_render=content_render
    )

@router.get("/reconciliation")
async def export_reconciliation_report(start_date: date, end_date: date, db: Session = Depends(get_db)):
    records = db.query(PaymentReconciliation) \
        .order_by(PaymentReconciliation.completed_at.asc()) \
        .filter(
            PaymentReconciliation.completed_at >= sg_datetime.midnight(start_date),
            PaymentReconciliation.completed_at < sg_datetime.midnight(end_date) + timedelta(days=1)
        ) \
        .all()

    return download_reconciliation_csv(db, records, csv_filename=f'{start_date}-{end_date}_reconciliation_report.csv')


# MC flagged cases: teleconsults where the patient already had MCs in the 30 days up to the visit
MC_LOOKBACK_DAYS = 30  # same window as the doctor app's "MCs (last 30 days)" chip
MC_REPORT_MAX_DAYS = 366

class McFlaggedRow(BaseModel):
    id: str  # teleconsult id
    visit_date: date
    patient_nric: str
    patient_name: str
    branch: str  # "MW" (migrant worker) or "PT" (private patient)
    doctor_name: Optional[str] = None
    mc_count_30d: int  # MCs in the 30 days up to the visit, excluding this visit's own MC
    mc_given: bool  # an MC was issued for this visit

def get_mc_flagged_rows(db: Session, start_date: date, end_date: date) -> list[McFlaggedRow]:
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date")
    if (end_date - start_date).days >= MC_REPORT_MAX_DAYS:
        raise HTTPException(status_code=400, detail="Select a date range of up to 1 year")

    # Same visit definition as the teleconsultation report: a doctor was assigned, checked in within the SG dates
    teleconsults = db.query(Teleconsult) \
        .options(joinedload(Teleconsult.account), joinedload(Teleconsult.doctor)) \
        .filter(
            Teleconsult.doctor_id.isnot(None),
            Teleconsult.checkin_time >= sg_datetime.midnight(start_date),
            Teleconsult.checkin_time < sg_datetime.midnight(end_date) + timedelta(days=1),
        ) \
        .order_by(Teleconsult.checkin_time.asc()) \
        .all()

    patient_ids = {t.account.sgimed_patient_id for t in teleconsults if t.account and t.account.sgimed_patient_id}
    if not patient_ids:
        return []

    # One query for every MC these patients could need; no upper date bound so an MC issued after the visit day still counts as given
    mcs_by_patient = defaultdict(list)
    for mc in db.query(Document.sgimed_patient_id, Document.sgimed_visit_id, Document.document_date).filter(
        Document.sgimed_patient_id.in_(patient_ids),
        Document.document_type == DocumentType.MC,
        Document.document_date > start_date - timedelta(days=MC_LOOKBACK_DAYS),
        or_(Document.status == None, Document.status != DocumentStatus.VOID),
    ):
        mcs_by_patient[mc.sgimed_patient_id].append(mc)

    rows = []
    for t in teleconsults:
        if not t.account or not t.account.sgimed_patient_id:
            continue
        visit_date = sg_datetime.sg(t.checkin_time).date()
        mcs = mcs_by_patient.get(t.account.sgimed_patient_id, [])
        is_this_visit = lambda mc: bool(t.sgimed_visit_id) and mc.sgimed_visit_id == t.sgimed_visit_id
        prior_count = sum(
            1 for mc in mcs
            if visit_date - timedelta(days=MC_LOOKBACK_DAYS) < mc.document_date <= visit_date and not is_this_visit(mc)
        )
        if prior_count == 0:
            continue
        rows.append(McFlaggedRow(
            id=str(t.id),
            visit_date=visit_date,
            patient_nric=t.account.nric or "",
            patient_name=t.account.name or "",
            branch="MW" if t.patient_type == PatientType.MIGRANT_WORKER else "PT",
            doctor_name=t.doctor.name if t.doctor else None,
            mc_count_30d=prior_count,
            mc_given=any(is_this_visit(mc) for mc in mcs),
        ))
    return rows

@router.get("/mc-flagged", response_model=list[McFlaggedRow])
def get_mc_flagged_report(start_date: date, end_date: date, db: Session = Depends(get_db)):
    return get_mc_flagged_rows(db, start_date, end_date)

@router.get("/mc-flagged/export")
def export_mc_flagged_report(start_date: date, end_date: date, db: Session = Depends(get_db)):
    rows = get_mc_flagged_rows(db, start_date, end_date)
    headers = ["Visit Date", "Patient NRIC", "Patient Name", "Branch (MW/PT)", "Doctor Assigned", "No. of MC (30 days before visit)", "MC Given on Visit"]
    data_rows = [
        [r.visit_date, r.patient_nric, r.patient_name, r.branch, r.doctor_name or "", r.mc_count_30d, "Yes" if r.mc_given else "No"]
        for r in rows
    ]
    return StreamingResponse(
        create_excel_with_styled_header(headers, data_rows),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=mc_flagged_report_{start_date}_{end_date}.xlsx"},
    )
