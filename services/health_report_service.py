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
            # Change to bracket notation because row is now a dictionary
            data.append({
                "name": row["name"],
                "nric": row["nric"],
                "mobile_number": row["mobile_number"],
                "email": row["email"],
                "height": row["height"],
                "weight": row["weight"],
                "systolic_bp": row["systolic_bp"],
                "diastolic_bp": row["diastolic_bp"],
                "heart_rate": row["heart_rate"],
                "bmi": row["bmi"],
                "smoking": row["smoking_sticks_per_day"],
                "bsa": row["bsa"],
                "last_checkup": row["last_checkup_date"]
            })

        return data

    except Exception as e:
        logger.error(f"Health report error: {str(e)}")
        raise
        
        
