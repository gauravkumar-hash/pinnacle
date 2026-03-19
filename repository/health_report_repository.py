from sqlalchemy import text

def fetch_health_report(db, nrics):
    query = text("""
        SELECT
            p.name,
            p.nric,
            MAX(CASE WHEN LOWER(sm.type_name) = 'height' THEN sm.value END) AS height,
            MAX(CASE WHEN LOWER(sm.type_name) = 'weight' THEN sm.value END) AS weight,
            MAX(CASE WHEN LOWER(sm.type_name) = 'systolic_bp' THEN sm.value END) AS systolic_bp,
            MAX(CASE WHEN LOWER(sm.type_name) = 'diastolic_bp' THEN sm.value END) AS diastolic_bp,
            -- ADDED THIS LINE
            MAX(CASE WHEN LOWER(sm.type_name) IN ('heart_rate', 'heartrate') THEN sm.value END) AS heart_rate
        FROM patient_accounts p
        JOIN sgimed_measurements sm
            ON sm.patient_id = p.id::text
        WHERE p.nric = ANY(:nrics)
        GROUP BY p.name, p.nric
    """)

    result = db.execute(query, {"nrics": nrics})
    return result.fetchall()
