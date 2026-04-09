from typing import Optional
from sqlalchemy.orm import Session
from models.model_enums import CollectionMethod, PatientType, TeleconsultStatus
from models.patient import Account
from models.teleconsult import Teleconsult
from services.teleconsult import PaymentTotal

def upsert_teleconsult(
        db: Session, 
        patient: Account, 
        patient_type: PatientType, 
        allergy: Optional[str],
        corporate_code: Optional[str], 
        payment_total: PaymentTotal, 
        address: str, 
        branch_id: str, 
        collection_method: Optional[CollectionMethod],
        group_id: Optional[str],
        index: Optional[int],
        created_by: Optional[str]
    ):
    teleconsult = db.query(Teleconsult).filter(
            Teleconsult.account_id == patient.id, 
            Teleconsult.status == TeleconsultStatus.PREPAYMENT
        ).first()

    teleconsult_dict = {
        "patient_type": patient_type,
        "allergy": allergy,
        "corporate_code": corporate_code,
        "payment_breakdown": [b.model_dump() for b in payment_total.breakdown],
        "total": payment_total.total,
        "address": address,
        "branch_id": branch_id,
        "collection_method": collection_method,
        "group_id": group_id,
        "index": index,
        "created_by": created_by
    }

    if teleconsult:
        teleconsult.update_vars(teleconsult_dict)
    else:
        teleconsult = Teleconsult(
            account_id=str(patient.id),
            **teleconsult_dict
        )
        db.add(teleconsult)
    db.commit()

    return teleconsult