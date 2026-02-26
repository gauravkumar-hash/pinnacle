from datetime import datetime
from models.patient import Account
from models.payments import Payment, PaymentMethod, PaymentReconciliation, PaymentStatus
from models.pinnacle import Branch
from models.appointment import Appointment
from models.teleconsult import Teleconsult
from sqlalchemy.orm import Session, joinedload, load_only
from utils.sg_datetime import sg

from sqlalchemy import cast, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR
from sqlalchemy.orm import Session, joinedload, load_only

# Calculate Rates
mdr_rates = {
    PaymentMethod.CARD_STRIPE: '3.4% + S$0.50',
    PaymentMethod.PAYNOW_STRIPE: '1.3%',
    PaymentMethod.CARD_2C2P: '2.7%',
}

def calc_nett_amt(amount, method: PaymentMethod):
    amount_after_mdr = 0
    if method == PaymentMethod.CARD_STRIPE:
        amount_after_mdr = amount - (amount * 0.034 + 0.50)
    elif method == PaymentMethod.PAYNOW_STRIPE:
        amount_after_mdr = amount - (amount * 0.013)
    elif method == PaymentMethod.CARD_2C2P:
        amount_after_mdr = amount - (amount * 0.027)
    if amount_after_mdr == 0:
        raise ValueError(f'Invalid payment method: {method}')
    
    return round(amount_after_mdr, 2)

def process_reconciliation(db: Session, start_time: datetime, end_time: datetime):
    payments, patients, visits = fetch_from_db(db, start_time, end_time)
    processed = {}

    for payment in payments:
        if payment.payment_id not in processed:
            processed[payment.payment_id] = []

        processed[payment.payment_id].append({
            'completed_at': sg(payment.updated_at),
            'branch' : visits[str(payment.id)]['branch'], # Teleconsults > Branch > Name
            'patients' : patients[str(payment.id)], # Teleconsults > Account > NRIC, Name
            'sgimed_visit_id' : visits[str(payment.id)]['sgimed_id'], # GET /queue/{visit_id}/invoice -> given_id
            'payment_id' : payment.payment_id,
            'payment_type' : payment.payment_type,
            'payment_provider' : payment.payment_provider,
            'payment_method' : payment.payment_method,
            'payment_amount' : payment.payment_amount,
            # 'Payment Platform Fees' : mdr_rates.get(payment.payment_method, None),
            # 'Nett Amount' : calc_nett_amt(payment.payment_amount, payment.payment_method),
        })

    # Merge Similar Payments Together

    def merge_records(item):
        k, v = item
        first = v[0]
        record = {
            'completed_at': first['completed_at'],
            'branch' : first['branch'],
            'patients' : [ p['patients'] for p in v ],
            'sgimed_visit_id' : [ p['sgimed_visit_id'] for p in v ],
            'payment_id' : first['payment_id'],
            'payment_type' : first['payment_type'],
            'payment_provider' : first['payment_provider'],
            'payment_method' : first['payment_method'],
            'payment_amount' : sum([ p['payment_amount'] for p in v ]),
            'payment_amount_nett' : calc_nett_amt(sum([ p['payment_amount'] for p in v ]), first['payment_method']),
            'payment_platform_fees' : mdr_rates.get(first['payment_method'], None),
        }
        
        return record
    merged = list(map(merge_records, processed.items()))
    insert_records(db, merged)

#### DB Helpers

def get_visits(db: Session, payment_ids: list[str]):
    # Get Branches
    qry = select(Branch.id, Branch.name)
    results = db.execute(qry).all()
    branches = { str(b.id): b.name for b in results }

    # Get Teleconsults
    qry = (
        select(
            Payment.id,
            Teleconsult.sgimed_visit_id,
            Teleconsult.branch_id
        )
        .select_from(Payment)
        .join(Payment.teleconsults)
        .where(Payment.id.in_(payment_ids))
    )
    results = db.execute(qry).all()
    visits = { str(p.id): { 'branch': branches[str(p.branch_id)], 'sgimed_id': p.sgimed_visit_id } for p in results }

    # Get Appointments
    qry = select(Appointment.sgimed_appointment_id, Appointment.branch, Appointment.payment_ids).where(
        Appointment.payment_ids.op('&&')(cast(payment_ids, ARRAY(VARCHAR)))
    )
    results = db.execute(qry).all()
    appointments = { str(payment_id): { 'branch': branches[str(p.branch['id'])], 'sgimed_id': p.sgimed_appointment_id } for p in results for payment_id in p.payment_ids }
    
    appointments.update(visits)
    return appointments

def get_patients(db: Session, payment_ids: list[str]):
    consults = db.query(Payment) \
        .options(
            load_only(Payment.id),
            joinedload(Payment.account).load_only(Account.nric, Account.name), # Left Join
        ) \
        .filter(Payment.id.in_(payment_ids)) \
        .all()
    
    return { str(p.id): f'{p.account.nric}: {p.account.name}' for p in consults }

def get_payments(db: Session, start_time: datetime, end_time: datetime):
    payments = db.query(Payment) \
        .filter(
            Payment.payment_method != PaymentMethod.DEFERRED_PAYMENT,
            Payment.status == PaymentStatus.PAYMENT_SUCCESS,
            Payment.updated_at >= start_time,
            Payment.updated_at < end_time
        ) \
        .all()

    return payments

def fetch_from_db(db: Session, start_time: datetime, end_time: datetime):    
    payments = get_payments(db, start_time, end_time)
    payment_ids = [str(p.id) for p in payments]
    patients = get_patients(db, payment_ids)
    visits = get_visits(db, payment_ids)
    return payments, patients, visits

def insert_records(db: Session, records: list[dict]):
    for r in records:
        db_record = PaymentReconciliation(**r)
        db.add(db_record)
        db.commit()
