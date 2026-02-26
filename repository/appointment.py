from models.patient import Account
from models.appointment import Appointment
from models.payments import Payment
from models.model_enums import AppointmentStatus
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Literal
from utils.sg_datetime import sgtz

class AppointmentRow(BaseModel):
    id: str
    type: Literal['appointment']
    title: str
    subtitle: str
    content: str
    icon: str
    tag: AppointmentStatus

def get_appointment_by_payment(db: Session, payment: Payment) -> Appointment | None:
    return db.query(Appointment).filter(
        Appointment.payment_ids.any(str(payment.id)) # type: ignore
    ).first()
    
def get_grouped_appointments(db: Session, appt: Appointment):
    if appt.group_id:
        return db.query(Appointment).filter(
            Appointment.group_id == appt.group_id,
            Appointment.start_datetime == appt.start_datetime,
            Appointment.status == appt.status
        ).order_by(Appointment.index.asc()).all()
    return [appt]

def process_grouped_appts(rows: list[Appointment], family_members: dict[str, Account], user: Account) -> list[AppointmentRow]:
    # Filter to keep only self and family members.
    rows = [r for r in rows if r.index is None or r.index == 0 or r.account_id in family_members]
    grouped_appts = []
    # Handle change in status or start time
    for status, start_time in set([(r.status, r.start_datetime) for r in rows]):
        curr_rows = [r for r in rows if r.status == status and r.start_datetime == start_time]
        row = curr_rows[0] # Due to potential change of appointments start_datetime and status, first record might not be the main appointment

        # In the event that there is only 1 appointment not for myself and no guests, then we don't need to show this appointment
        if len(curr_rows) == 1 and row.account_id is None and not row.guests:
            continue

        consult_for = []
        for r in curr_rows:
            if r.account_id in family_members:
                consult_for.append(family_members[r.account_id].name)
            elif r.account_id == user.id:
                consult_for = ['Myself'] + consult_for
        if row.guests:
            consult_for += [g['name'] for g in row.guests]

        grouped_appts.append(
            AppointmentRow(
                id=str(row.id),
                type='appointment',
                title=', '.join([svc['name'] for svc in row.services]),
                subtitle='Appointment for: **' + ', '.join(consult_for) + '**' if consult_for else '',
                content=f"{row.branch['name']}\n{row.start_datetime.astimezone(sgtz).strftime('%d %b %Y, %I:%M %p')}",
                icon=row.services[0].get('icon', 'https://yaadelemrtuxfyxayxpu.supabase.co/storage/v1/object/public/uploads/appointments/chronic.png'),
                tag=row.status,
            )
        )

    return grouped_appts
