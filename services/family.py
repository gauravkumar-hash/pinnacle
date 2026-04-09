from enum import Enum
from sqlalchemy.orm import Session
from models.model_enums import WalkinQueueStatus
from models.teleconsult import Teleconsult, TeleconsultStatus
from models.walkin import WalkInQueue

class OngoingStatus(Enum):
    TELECONSULT = "teleconsult"
    WALKIN_QUEUE = "walkin_queue"
    
def check_ongoing_consults(db: Session, account_id: str) -> OngoingStatus | None:
    # Check if the family member is in Teleconsult or Walk in Queue
    teleconsult = db.query(Teleconsult.id) \
        .filter(
            Teleconsult.account_id == account_id, 
            Teleconsult.status.not_in([TeleconsultStatus.PREPAYMENT, TeleconsultStatus.CHECKED_OUT])
        ).first()
    if teleconsult:
        return OngoingStatus.TELECONSULT

    queue = db.query(WalkInQueue.id) \
        .filter(
            WalkInQueue.account_id == account_id, 
            WalkInQueue.status.in_([WalkinQueueStatus.PENDING, WalkinQueueStatus.CHECKED_IN, WalkinQueueStatus.CONSULT_START])
        ).first()
    if queue:
        return OngoingStatus.WALKIN_QUEUE

    return None
