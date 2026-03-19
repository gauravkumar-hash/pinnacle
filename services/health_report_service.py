from repository.health_report_repository import fetch_health_report
import logging

logger = logging.getLogger(__name__)


def get_health_report(db, nrics):

    try:

        if not nrics:
            raise ValueError("NRIC list cannot be empty")

        rows = fetch_health_report(db, nrics)

        data = []

        for row in rows:
            data.append({
                "name": row.name,
                "nric": row.nric,
                "height": row.height,
                "weight": row.weight,
                "systolic_bp": row.systolic_bp,
                "diastolic_bp": row.diastolic_bp,
                "heart_rate": row.heart_rate  # ADDED THIS LINE
            })

        return data

    except Exception as e:
        logger.error(f"Health report error: {str(e)}")
        raise
        
        
