from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from datetime import date, datetime, timedelta
from pydantic import BaseModel
from models import get_db
from models.patient import AccountYuuLink, YuuTransactionLog, Account
from utils.pagination import PaginationInput, paginate, Page
from utils.supabase_auth import get_superadmin
from services.yuu import generate_yuu_refunds_csv_data
from fastapi.responses import StreamingResponse
from utils import sg_datetime

router = APIRouter(dependencies=[Depends(get_superadmin)])

class YuuEnrollmentResp(BaseModel):
    id: str
    patient_name: str
    nric: str
    tomo_id: str
    linked_at: datetime

    class Config:
        from_attributes = True

class YuuTransactionResp(BaseModel):
    id: str
    transaction_id: str
    patient_name: str
    tomo_id: str
    amount: float
    success: bool
    created_at: datetime
    refund_details: Optional[dict]

    class Config:
        from_attributes = True

@router.get('/enrollments', response_model=Page[YuuEnrollmentResp])
def get_yuu_enrollments(
    pagination: PaginationInput = Depends(),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(
        AccountYuuLink.id,
        AccountYuuLink.tomo_id,
        AccountYuuLink.linked_at,
        Account.name,
        Account.nric
    ).join(Account).filter(AccountYuuLink.deleted == False)
    if search:
        query = query.filter(or_(
            Account.name.ilike(f'%{search}%'),
            Account.nric.ilike(f'%{search}%'),
            AccountYuuLink.tomo_id.ilike(f'%{search}%')
        ))
    query = query.order_by(AccountYuuLink.linked_at.desc())

    # Transform the results to match the response model
    results = paginate(query, db, pagination)

    # Convert to response format
    enrollment_data = []
    for row in results.data:
        enrollment_data.append(YuuEnrollmentResp(
            id=str(row.id),
            patient_name=row.name,
            nric=row.nric,
            tomo_id=row.tomo_id,
            linked_at=row.linked_at
        ))

    results.data = enrollment_data
    return results

@router.get('/transactions', response_model=Page[YuuTransactionResp])
def get_yuu_transactions(
    pagination: PaginationInput = Depends(),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),  # 'all', 'success', 'failed'
    show_refunds_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    query = db.query(
        YuuTransactionLog.id,
        YuuTransactionLog.transaction_id,
        YuuTransactionLog.tomo_id,
        YuuTransactionLog.sgimed_invoice_dict,
        YuuTransactionLog.success,
        YuuTransactionLog.created_at,
        YuuTransactionLog.refund_details,
        Account.name
    ).join(Account)

    if start_date:
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        start_datetime = sg_datetime.midnight(start_date_obj)
        query = query.filter(YuuTransactionLog.created_at >= start_datetime)

    if end_date:
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        end_datetime = sg_datetime.midnight(end_date_obj + timedelta(days=1))
        query = query.filter(YuuTransactionLog.created_at < end_datetime)

    if status and status != 'all':
        success_filter = status == 'success'
        query = query.filter(YuuTransactionLog.success == success_filter)

    if show_refunds_only:
        query = query.filter(YuuTransactionLog.refund_details.isnot(None))

    # Apply ordering by created_at desc
    query = query.order_by(YuuTransactionLog.created_at.desc())

    results = paginate(query, db, pagination)

    # Transform to response format
    transaction_data = []
    for row in results.data:
        # Calculate amount from sgimed_invoice_dict
        amount = row.sgimed_invoice_dict.get('total', 0.0) if row.sgimed_invoice_dict else 0.0
        amount = round(amount, 2)

        transaction_data.append(YuuTransactionResp(
            id=str(row.id),
            transaction_id=row.transaction_id,
            patient_name=row.name,
            tomo_id=row.tomo_id,
            amount=amount,
            success=row.success,
            created_at=row.created_at,
            refund_details=row.refund_details
        ))

    results.data = transaction_data
    return results

@router.get('/transactions/export-refunds')
def export_refund_csv_endpoint(year: int, month: int, db: Session = Depends(get_db)):
    """API endpoint for manual CSV download"""
    filename, content = generate_yuu_refunds_csv_data(db, year, month)
    return StreamingResponse(
        content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

@router.get('/transactions/export-csv')
def export_transactions_csv(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    status: Optional[str] = Query(None),
    show_refunds_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    """Export transactions to CSV based on filters"""
    from io import StringIO
    import csv

    # Build query with same filters as get_yuu_transactions
    query = db.query(
        YuuTransactionLog.transaction_id,
        YuuTransactionLog.tomo_id,
        YuuTransactionLog.sgimed_invoice_dict,
        YuuTransactionLog.success,
        YuuTransactionLog.created_at,
        YuuTransactionLog.refund_details,
        Account.name
    ).join(Account)

    if start_date:
        start_datetime = sg_datetime.midnight(start_date)
        query = query.filter(YuuTransactionLog.created_at >= start_datetime)

    if end_date:
        end_datetime = sg_datetime.midnight(end_date + timedelta(days=1))
        query = query.filter(YuuTransactionLog.created_at < end_datetime)

    if status and status != 'all':
        success_filter = status == 'success'
        query = query.filter(YuuTransactionLog.success == success_filter)

    if show_refunds_only:
        query = query.filter(YuuTransactionLog.refund_details.isnot(None))

    query = query.order_by(YuuTransactionLog.created_at.desc())

    # Generate CSV
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'Transaction ID', 'Patient Name', 'Tomo ID', 'Amount', 'Status',
        'Created At', 'Refund Amount', 'Refunded At'
    ])

    # Write data
    for row in query.all():
        amount = row.sgimed_invoice_dict.get('total', 0.0) if row.sgimed_invoice_dict else 0.0
        refund_amount = row.refund_details.get('refund_amount', '') if row.refund_details else ''
        refunded_at = row.refund_details.get('refunded_at', '') if row.refund_details else ''

        writer.writerow([
            row.transaction_id,
            row.name,
            row.tomo_id,
            f"{amount:.2f}",
            'Success' if row.success else 'Failed',
            row.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            f"{refund_amount:.2f}" if refund_amount else '',
            refunded_at
        ])

    output.seek(0)

    # Generate filename
    date_suffix = ""
    if start_date and end_date:
        date_suffix = f"_{start_date}_to_{end_date}"
    elif start_date:
        date_suffix = f"_from_{start_date}"
    elif end_date:
        date_suffix = f"_until_{end_date}"

    filename = f"yuu_transactions{date_suffix}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
