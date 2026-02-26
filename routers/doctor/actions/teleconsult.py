from datetime import date, timedelta
from models.model_enums import TeleconsultStatus
from models.teleconsult import Teleconsult
from sqlalchemy.orm import Session
from routers.doctor.actions.webhook import TeleconsultResponse, UserResponse
from routers.patient.actions.teleconsult_utils import get_grouped_teleconsults
from utils import sg_datetime

def group_teleconsults(teleconsults: list[Teleconsult]):
    grouped_teleconsults = {}
    for teleconsult in teleconsults:
        if teleconsult.group_id:
            if teleconsult.group_id not in grouped_teleconsults:
                grouped_teleconsults[teleconsult.group_id] = []
            grouped_teleconsults[teleconsult.group_id].append(teleconsult)
        else:
            grouped_teleconsults[teleconsult.id] = [teleconsult]

    return [
        get_teleconsult_response(t) for t in grouped_teleconsults.values()
    ]

def get_teleconsult_response(teleconsults: list[Teleconsult]):
    # Sort by index
    if len(teleconsults) > 1:
        teleconsults = sorted(teleconsults, key=lambda x: x.index if x.index else 0)
    
    return TeleconsultResponse(
        id=str(teleconsults[0].id),
        patient_type=teleconsults[0].patient_type,
        status=teleconsults[0].status,
        additional_status=teleconsults[0].additional_status,
        checkin_time=teleconsults[0].checkin_time,
        queue_number=",".join([str(t.queue_number) for t in teleconsults]),
        branch_name=teleconsults[0].branch.name,
        user=UserResponse(
            name=teleconsults[0].account.name,
            ic_type=teleconsults[0].account.ic_type,
            nric=teleconsults[0].account.nric
        )
    )

def get_teleconsult_with_doctor_id(db: Session, doctor_id: str):
    teleconsults = db.query(Teleconsult).filter(
            Teleconsult.status == TeleconsultStatus.CONSULT_START,
            Teleconsult.doctor_id == doctor_id
        ).all()

    if not teleconsults:
        return None

    return get_teleconsult_response(teleconsults)

def get_teleconsults(db: Session):
    teleconsults = db.query(Teleconsult).filter(
            Teleconsult.status == TeleconsultStatus.CHECKED_IN
        ).all()

    return sorted(group_teleconsults(teleconsults), key=lambda x: x.checkin_time)

def get_ended_teleconsults_with_doctor_id(db: Session, doctor_id: str, date: date):
    curr_midnight_time = sg_datetime.midnight(date)
    teleconsults = db.query(Teleconsult).filter(
            Teleconsult.status.in_(["CONSULT_END", "OUTSTANDING", "CHECKED_OUT"]),
            Teleconsult.doctor_id == doctor_id,
            Teleconsult.checkin_time >= curr_midnight_time,
            Teleconsult.checkin_time < (curr_midnight_time + timedelta(days=1)),
            Teleconsult.checkin_time >= (curr_midnight_time - timedelta(days=60)) # Doctors are only allowed to view teleconsults within 60 days
        ).order_by(Teleconsult.checkin_time.desc()).all()

    return sorted(group_teleconsults(teleconsults), key=lambda x: x.checkin_time, reverse=True)

def get_teleconsult_with_id(db: Session, id: str):
    teleconsult = db.query(Teleconsult).filter(
            Teleconsult.id == id
        ).first()
    if not teleconsult:
        return None

    teleconsults = get_grouped_teleconsults(db, teleconsult)
    return get_teleconsult_response(teleconsults)
