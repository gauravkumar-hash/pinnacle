from datetime import date, timedelta
from io import StringIO
import csv
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from models import get_db
from models.payments import PaymentMethod, PaymentProvider, PaymentReconciliation, PaymentType
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
