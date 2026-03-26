from sqlalchemy import text

# STRATEGY 1: Full History (Returns every visit date)
def fetch_health_history(db, nrics):
    query = text("""
        SELECT
            p.name, p.nric, sm.measurement_date, sm.branch_id,
            MAX(CASE WHEN sm.type_name = 'Height' THEN sm.value END) AS height,
            MAX(CASE WHEN sm.type_name = 'Weight' THEN sm.value END) AS weight,
            MAX(CASE WHEN sm.type_name = 'Systolic' THEN sm.value END) AS systolic_bp,
            MAX(CASE WHEN sm.type_name = 'Diastolic' THEN sm.value END) AS diastolic_bp,
            MAX(CASE WHEN sm.type_name = 'HeartRate' THEN sm.value END) AS heart_rate,
            MAX(CASE WHEN sm.type_name = 'BMI' THEN sm.value END) AS bmi,
            MAX(CASE WHEN sm.type_name = 'Smoking' THEN sm.value END) AS smoking,
            MAX(CASE WHEN sm.type_name = 'BSA' THEN sm.value END) AS bsa
        FROM public.patient_accounts p
        LEFT JOIN public.sgimed_measurements sm ON sm.patient_id = p.sgimed_patient_id
        WHERE p.nric = ANY(:nrics)
        GROUP BY p.name, p.nric, sm.measurement_date, sm.branch_id
        ORDER BY p.name, sm.measurement_date DESC
    """)
    result = db.execute(query, {"nrics": nrics})
    return [dict(row) for row in result.mappings()]

# STRATEGY 2: Latest Only (Returns only the most recent visit per user)
def fetch_latest_health_report(db, nrics):
    query = text("""
        SELECT DISTINCT ON (p.nric)
            p.name, p.nric, sm.measurement_date, sm.branch_id,
            MAX(CASE WHEN sm.type_name = 'Height' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS height,
            MAX(CASE WHEN sm.type_name = 'Weight' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS weight,
            MAX(CASE WHEN sm.type_name = 'Systolic' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS systolic_bp,
            MAX(CASE WHEN sm.type_name = 'Diastolic' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS diastolic_bp,
            MAX(CASE WHEN sm.type_name = 'HeartRate' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS heart_rate,
            MAX(CASE WHEN sm.type_name = 'BMI' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS bmi,
            MAX(CASE WHEN sm.type_name = 'Smoking' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS smoking,
            MAX(CASE WHEN sm.type_name = 'BSA' THEN sm.value END) OVER(PARTITION BY p.nric, sm.measurement_date) AS bsa
        FROM public.patient_accounts p
        LEFT JOIN public.sgimed_measurements sm ON sm.patient_id = p.sgimed_patient_id
        WHERE p.nric = ANY(:nrics)
        ORDER BY p.nric, sm.measurement_date DESC
    """)
    result = db.execute(query, {"nrics": nrics})
    return [dict(row) for row in result.mappings()]
