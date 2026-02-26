from sqlalchemy.orm import Session
from models.delivery import TeleconsultDelivery
from utils import sg_datetime
from utils.fastapi import SuccessResp
from utils.supabase_s3 import delete_file_from_s3
from config import SUPABASE_PRIVATE_BUCKET
from datetime import timedelta

def hide_expired_delivery_note_action(db: Session):
    teleconsult_deliveries = (
        db.query(TeleconsultDelivery)
        .filter(
            TeleconsultDelivery.is_delivery_note_exists == True,
            TeleconsultDelivery.receipt_date < sg_datetime.now() - timedelta(days=180),
        )
        .all()
    )

    for teleconsult_delivery in teleconsult_deliveries:
        if teleconsult_delivery.delivery_note_file_path:
            delete_file_from_s3(SUPABASE_PRIVATE_BUCKET, teleconsult_delivery.delivery_note_file_path)

        teleconsult_delivery.is_delivery_note_exists = False
        teleconsult_delivery.delivery_note_file_path = None

    db.commit()
    return SuccessResp(success=True)