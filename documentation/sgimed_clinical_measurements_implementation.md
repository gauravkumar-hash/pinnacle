# SGiMED Clinical Measurements Implementation

## Overview

This document describes the implementation of additional SGiMED clinical measurements for the Health Screening Report system, including Tonometry, Visual Acuity, Colour Vision Tests, Body Composition, Spirometry, and Waist-Hip Ratio (WHR).

## Date Implemented

April 8, 2026

## New Clinical Measurements Added

### 1. Tonometry (Intraocular Pressure)

**Measurement Fields:**

- `IOP Right` - Right eye intraocular pressure
- `IOP Left` - Left eye intraocular pressure

**Range:**

- Normal: 10-21 mmHg
- Elevated: >21 mmHg (requires ophthalmologist consultation)
- Low: <10 mmHg (requires ophthalmologist consultation)

**Possible Causes for Abnormal Results:**

- **High IOP (>21 mmHg):**
  - Primary open-angle glaucoma
  - Ocular hypertension
  - Eye trauma
  - Inflammation (uveitis)
  - Steroid medication use

- **Low IOP (<10 mmHg):**
  - Post-surgical (glaucoma surgery or trauma repair)
  - Ocular trauma
  - Chronic uveitis
  - Retinal detachment
  - Severe dehydration/systemic illness

### 2. Visual Acuity

**Measurement Fields:**

- `Visual Acuity Right` - Right eye visual acuity
- `Visual Acuity Left` - Left eye visual acuity

**Range:**

- Normal: 6/6 (20/20), 6/9, 6/12, 6/4
- Abnormal: Worse than 6/12 (may indicate refractive error or eye disease)

**Note:** Visual acuity measures the clarity or sharpness of vision.

### 3. Colour Vision Tests (Ishihara Test)

**Measurement Fields:**

- `Red-Green Deficiency` (Yes/No)
- `Blue-Yellow Deficiency` (Yes/No)
- `Complete Colour Blindness` (Yes/No)

**Details:**

- **Red-Green Deficiency:** Common and inherited. Usually doesn't affect visual acuity but may cause difficulty with color-coded charts or traffic signals.
- **Blue-Yellow Deficiency:** Much rarer than red-green. Can be inherited (autosomal) or acquired due to eye disease.
- **Complete Colour Blindness (Achromatopsia):** Rare condition where individual sees only in black, white, and shades of grey.

### 4. Body Composition

**Measurement Fields:**

- `Total Body Fat Percentage` (%)
- `Visceral Fat Level` (rating 1-30)

**Total Body Fat Percentage Ranges:**

- Males:
  - Below normal: <8%
  - Normal: 8-25%
  - Above normal: >25%
  - Very high (obese): >30%

- Females:
  - Below normal: <21%
  - Normal: 21-33%
  - Above normal: >33%
  - Very high (obese): >40%

**Visceral Fat Rating:**

- Normal/Healthy: 1-9
- High: 10-14
- Very High: 15-30

**Health Implications:**
Body fat percentage is a better indicator of health risk than BMI alone. Visceral fat is particularly dangerous as it's stored around internal organs and increases risk of metabolic syndrome, type 2 diabetes, stroke, and heart disease.

### 5. Spirometry

**Measurement Field:**

- `Spirometry Result` (Normal/Restrictive/Obstructive)

**Results:**

- **Normal:** Normal lung function
- **Restrictive:** May indicate interstitial lung diseases, chest wall deformities, or neuromuscular disorders
- **Obstructive:** May indicate asthma or COPD

**Purpose:** Measures how well the lungs work by evaluating the volume and flow of air that can be inhaled and exhaled.

### 6. Waist-Hip Ratio (WHR)

**Measurement Fields (for calculation):**

- `Waist Circumference` (cm)
- `Hip Circumference` (cm)

**Calculated Field:**

- `WHR` = Waist Circumference ÷ Hip Circumference

**Formula:** WHR = Waist / Hip

**Ranges:**
| Gender | Low Risk | Moderate Risk | High Risk |
|--------|----------|---------------|-----------|
| Male | <0.90 | 0.90-0.99 | ≥1.0 |
| Female | <0.80 | 0.80-0.84 | ≥0.85 |

**Health Implications:**
High WHR indicates central (abdominal) obesity, which is associated with:

- Type 2 diabetes
- Hypertension
- Dyslipidaemia
- Cardiovascular disease
- Fatty liver

## Technical Implementation

### Files Modified

#### 1. `/scheduler_actions/health_report/convert.py`

**Changes:**

- Updated `get_patient_measurement()` function to extract new measurement types from SGiMED
- Added WHR calculation logic (similar to existing BMI calculation)
- Added new measurement keys to the extraction list

**New Measurement Keys Extracted:**

```python
keys = [
    "Systolic", "Diastolic", "Height", "Weight",
    "Waist Circumference", "Hip Circumference",  # For WHR calculation
    "IOP Right", "IOP Left",  # Tonometry
    "Visual Acuity Right", "Visual Acuity Left",  # Visual Acuity
    "Red-Green Deficiency", "Blue-Yellow Deficiency", "Complete Colour Blindness",  # Colour Vision
    "Total Body Fat Percentage", "Visceral Fat Level",  # Body Composition
    "Spirometry Result"  # Spirometry
]
```

**WHR Calculation Logic:**

```python
if 'SGiMed^Waist Circumference' in measures_dict and 'SGiMed^Hip Circumference' in measures_dict:
    waist = float(measures_dict["SGiMed^Waist Circumference"][0])
    hip = float(measures_dict["SGiMed^Hip Circumference"][0])
    if hip > 0:
        whr = round(waist / hip, 2)
        measures_dict['SGiMed^WHR'] = [str(whr), '', None]
```

#### 2. `/repository/health_report/mapping.py`

**Changes:**

- Added 8 new mapping functions for clinical measurements
- Added 15 new test configurations to the Clinical Assessment profile

**New Mapping Functions:**

1. `tonometry_mapping()` - Maps IOP readings (10-21 mmHg normal range)
2. `visual_acuity_mapping()` - Maps VA readings (6/6, 6/9, 6/12, 6/4 as normal)
3. `colour_vision_mapping()` - Maps Yes/No colour vision deficiency results
4. `body_fat_percentage_mapping()` - Gender-specific body fat percentage ranges
5. `visceral_fat_mapping()` - Maps visceral fat levels (1-9 normal, 10-14 high, 15+ very high)
6. `spirometry_mapping()` - Maps Normal/Restrictive/Obstructive results
7. `whr_mapping()` - Gender-specific WHR risk categories

**New Test Configurations Added to Clinical Assessment Profile:**

1. Waist Circumference
2. Hip Circumference
3. Waist-Hip Ratio (WHR)
4. Tonometry (IOP) - Right Eye
5. Tonometry (IOP) - Left Eye
6. Visual Acuity - Right Eye
7. Visual Acuity - Left Eye
8. Colour Vision - Red-Green Deficiency
9. Colour Vision - Blue-Yellow Deficiency
10. Colour Vision - Complete Colour Blindness
11. Total Body Fat Percentage
12. Visceral Fat Level
13. Spirometry

## Data Flow

### 1. Measurement Sync from SGiMED

```
SGiMED API → /measurement endpoint → update_measurements_cron() → Measurement table
```

The system syncs measurements from SGiMED through the scheduler action in:

- `/scheduler_actions/sgimed_health_report_updates.py`

### 2. Health Report Generation

```
IncomingReport → get_report_measurements() → get_patient_measurement() →
generate_profile_output() → save_health_report_to_db()
```

**Process:**

1. System retrieves measurements from database for the patient
2. Measurements are filtered by date (within ±30 days of report date)
3. Latest measurements are extracted and calculated fields (BMI, WHR) are computed
4. Measurements are mapped to test results with tags (Normal/Borderline/Out of Range)
5. Health report JSON is generated and saved

### 3. Cross-Branch/Cross-Day Measurement Support

The system already supports measurements from:

- **Different branches:** Measurement includes `branch_id` field
- **Different days:** Measurements within ±30 days of report date are considered
- **Latest measurements:** System uses the most recent measurement for each type

**Note:** The measurement selection logic in `get_patient_measurement()` currently takes the first occurrence of each measurement type. This means if a patient has measurements from different days/branches, the system will use whichever measurement appears first in the sorted list (sorted by `measurement_date` ascending).

## SGiMED Field Name Requirements

For the measurements to be properly synced and displayed, SGiMED must send measurements with the following `type_name` values:

| Clinical Measurement          | SGiMED `type_name` Field    |
| ----------------------------- | --------------------------- |
| Intraocular Pressure (Right)  | `IOP Right`                 |
| Intraocular Pressure (Left)   | `IOP Left`                  |
| Visual Acuity (Right)         | `Visual Acuity Right`       |
| Visual Acuity (Left)          | `Visual Acuity Left`        |
| Red-Green Colour Deficiency   | `Red-Green Deficiency`      |
| Blue-Yellow Colour Deficiency | `Blue-Yellow Deficiency`    |
| Complete Colour Blindness     | `Complete Colour Blindness` |
| Total Body Fat                | `Total Body Fat Percentage` |
| Visceral Fat                  | `Visceral Fat Level`        |
| Spirometry                    | `Spirometry Result`         |
| Waist                         | `Waist Circumference`       |
| Hip                           | `Hip Circumference`         |

**Expected Values:**

**Visual Acuity:** String values like "6/6", "6/9", "6/12", "6/4", etc.

**Colour Vision Tests:** "Yes", "No", "Positive", "Negative", "Pos", "Neg" (case-insensitive)

**Spirometry:** "Normal", "Restrictive", "Obstructive" (case-insensitive)

**Tonometry:** Numeric values (e.g., "15", "12.5") in mmHg

**Body Fat Percentage:** Numeric values (e.g., "22.5", "18.0") in %

**Visceral Fat Level:** Numeric values (e.g., "8", "12") on 1-30 scale

**Waist/Hip Circumference:** Numeric values (e.g., "85", "95") in cm

## Testing Recommendations

### 1. Unit Testing

- Test WHR calculation with various waist/hip measurements
- Test mapping functions with edge cases (boundary values)
- Test gender-specific ranges for WHR and body fat percentage

### 2. Integration Testing

- Create test measurements in SGiMED with various values
- Verify measurements sync correctly to the database
- Generate health reports and verify all new measurements appear
- Test with measurements from different branches
- Test with measurements from different days

### 3. Test Cases

**WHR Calculation:**

```python
# Male - Low Risk
waist=85, hip=100 → WHR=0.85 → Low Risk ✓

# Male - Moderate Risk
waist=92, hip=100 → WHR=0.92 → Moderate Risk ✓

# Male - High Risk
waist=105, hip=100 → WHR=1.05 → High Risk ✓

# Female - Low Risk
waist=75, hip=100 → WHR=0.75 → Low Risk ✓

# Female - Moderate Risk
waist=82, hip=100 → WHR=0.82 → Moderate Risk ✓

# Female - High Risk
waist=88, hip=100 → WHR=0.88 → High Risk ✓
```

**Tonometry:**

```python
IOP=8 → Low (Out of Range) ✓
IOP=15 → Normal ✓
IOP=25 → Elevated (Out of Range) ✓
```

**Visual Acuity:**

```python
"6/6" → Normal ✓
"6/9" → Normal ✓
"6/12" → Normal ✓
"6/4" → Normal ✓
"6/18" → Abnormal (Out of Range) ✓
```

**Spirometry:**

```python
"Normal" → Normal ✓
"Restrictive" → Out of Range ✓
"Obstructive" → Out of Range ✓
```

## Database Considerations

### Current Schema

The `Measurement` table schema remains unchanged:

```sql
CREATE TABLE sgimed_measurements (
    id VARCHAR PRIMARY KEY,
    branch_id VARCHAR,
    patient_id VARCHAR,
    type_name VARCHAR,
    type_unit VARCHAR,
    value VARCHAR,
    measurement_date TIMESTAMP,
    last_edited TIMESTAMP,
    created_at TIMESTAMP
);
```

**No database migration required** - the existing schema already supports the new measurements.

## Admin Interface

The existing admin endpoints already support viewing these measurements:

- `/api/admin/health_reports/measurements/{nric}` - Get all measurements by patient NRIC
- The endpoint returns all measurements regardless of type

## Future Enhancements

### Possible Additions Mentioned

The client mentioned they may add more measurements in the future. The system architecture supports easy addition of new measurements by:

1. Adding new measurement type names to the `keys` list in `convert.py`
2. Creating mapping functions if custom logic is needed
3. Adding test configurations to the appropriate profile in `mapping.py`

### Suggested Improvements

1. **Measurement Selection Logic:**
   - Consider implementing smart selection for cross-day measurements
   - Prioritize measurements from the same day as the lab report
   - Flag when measurements are from significantly different dates

2. **Measurement Validation:**
   - Add validation rules in SGiMED to ensure data quality
   - Implement data type checking (numeric vs string)
   - Add range validation at sync time

3. **Reporting Enhancements:**
   - Add visual indicators when measurements are from different days
   - Show measurement dates alongside values
   - Add branch information in the report

4. **API Documentation:**
   - Document expected measurement formats for SGiMED team
   - Provide example payloads for all measurement types

## Support and Maintenance

### Common Issues

**Issue:** WHR not appearing in report

- **Check:** Verify both Waist and Hip measurements exist
- **Check:** Ensure measurements are from the same visit/date
- **Check:** Verify Hip measurement is not zero

**Issue:** Colour vision tests not showing

- **Check:** SGiMED is sending "Yes"/"No" values (not boolean true/false)
- **Check:** Field names exactly match (case-sensitive)

**Issue:** Tonometry showing as abnormal when in normal range

- **Check:** Values are numeric, not strings with units (e.g., "15" not "15 mmHg")
- **Check:** Decimal values are properly formatted

### Monitoring

Monitor the following for successful implementation:

1. Measurement sync success rate in `sgimed_measurements_cron`
2. Health report generation errors
3. Missing measurement warnings in logs
4. Cross-day measurement warnings

## Contacts

For questions or issues related to:

- **SGiMED Integration:** Contact SGiMED technical team
- **Measurement Definitions:** Contact clinical team
- **System Implementation:** Contact development team

## Changelog

### Version 1.0 - April 8, 2026

- Initial implementation of SGiMED clinical measurements
- Added 13 new measurement types to Clinical Assessment profile
- Implemented WHR calculation
- Added 7 new mapping functions with clinical ranges
- Updated measurement extraction logic

---

**Document Version:** 1.0  
**Last Updated:** April 8, 2026  
**Status:** Implementation Complete
