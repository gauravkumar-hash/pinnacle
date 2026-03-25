from sqlalchemy import text

def fetch_health_report(db, nrics):
    query = text("""
        SELECT
            p.name,
            p.nric,
            sm.measurement_date,
            sm.branch_id,
            -- Pivot clinical measurements for EACH visit date
            MAX(CASE WHEN sm.type_name = 'Height' THEN sm.value END) AS height,
            MAX(CASE WHEN sm.type_name = 'Weight' THEN sm.value END) AS weight,
            MAX(CASE WHEN sm.type_name = 'Systolic' THEN sm.value END) AS systolic_bp,
            MAX(CASE WHEN sm.type_name = 'Diastolic' THEN sm.value END) AS diastolic_bp,
            MAX(CASE WHEN sm.type_name = 'HeartRate' THEN sm.value END) AS heart_rate,
            MAX(CASE WHEN sm.type_name = 'BMI' THEN sm.value END) AS bmi,
            MAX(CASE WHEN sm.type_name = 'Smoking' THEN sm.value END) AS smoking_sticks_per_day,
            MAX(CASE WHEN sm.type_name = 'BSA' THEN sm.value END) AS bsa
        FROM public.patient_accounts p
        LEFT JOIN public.sgimed_measurements sm 
            ON sm.patient_id = p.sgimed_patient_id
        WHERE p.nric = ANY(:nrics)
        -- Removed contact details from grouping
        GROUP BY p.name, p.nric, sm.measurement_date, sm.branch_id
        ORDER BY sm.measurement_date DESC
    """)

    result = db.execute(query, {"nrics": nrics})
    return [dict(row) for row in result.mappings()]
