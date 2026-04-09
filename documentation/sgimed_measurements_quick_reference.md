# SGiMED Clinical Measurements - Quick Reference Guide

## For SGiMED Integration Team

### Required Field Names in SGiMED

When sending measurements via the `/measurement` API endpoint, use these exact `type_name` values:

| Measurement Type     | `type_name`                 | `type_unit` | Expected Value Format                     |
| -------------------- | --------------------------- | ----------- | ----------------------------------------- |
| **Tonometry**        |
| Right Eye IOP        | `IOP Right`                 | `mmHg`      | Numeric (e.g., "15", "12.5")              |
| Left Eye IOP         | `IOP Left`                  | `mmHg`      | Numeric (e.g., "15", "12.5")              |
| **Visual Acuity**    |
| Right Eye VA         | `Visual Acuity Right`       | _(empty)_   | Text (e.g., "6/6", "6/9", "6/12", "6/4")  |
| Left Eye VA          | `Visual Acuity Left`        | _(empty)_   | Text (e.g., "6/6", "6/9", "6/12")         |
| **Colour Vision**    |
| Red-Green            | `Red-Green Deficiency`      | _(empty)_   | "Yes" or "No"                             |
| Blue-Yellow          | `Blue-Yellow Deficiency`    | _(empty)_   | "Yes" or "No"                             |
| Complete             | `Complete Colour Blindness` | _(empty)_   | "Yes" or "No"                             |
| **Body Composition** |
| Body Fat             | `Total Body Fat Percentage` | `%`         | Numeric (e.g., "22.5", "18.0")            |
| Visceral Fat         | `Visceral Fat Level`        | _(empty)_   | Numeric 1-30 (e.g., "8", "12")            |
| **Spirometry**       |
| Lung Function        | `Spirometry Result`         | _(empty)_   | "Normal", "Restrictive", or "Obstructive" |
| **Anthropometric**   |
| Waist                | `Waist Circumference`       | `cm`        | Numeric (e.g., "85", "92")                |
| Hip                  | `Hip Circumference`         | `cm`        | Numeric (e.g., "95", "100")               |

### Example API Payload

```json
{
  "id": "measurement_123456",
  "patient": {
    "id": "patient_789",
    "name": "John Doe"
  },
  "type": {
    "id": "type_001",
    "name": "IOP Right",
    "unit": "mmHg"
  },
  "value": "15",
  "branch_id": "branch_raffles",
  "date": "2026-04-08T10:30:00+08:00",
  "time": "10:30:00",
  "created_at": "2026-04-08T10:30:00+08:00",
  "last_edited": "2026-04-08T10:30:00+08:00"
}
```

## Clinical Ranges Summary

### Tonometry (IOP)

- ✅ **Normal:** 10-21 mmHg
- ⚠️ **Low:** <10 mmHg → Refer to ophthalmologist
- ⚠️ **High:** >21 mmHg → Refer to ophthalmologist

### Visual Acuity

- ✅ **Normal:** 6/6, 6/9, 6/12, 6/4
- ⚠️ **Abnormal:** Worse than 6/12 → Refer to ophthalmologist

### Colour Vision

- ✅ **Normal:** No deficiency detected
- ⚠️ **Abnormal:** Any deficiency detected → Refer to ophthalmologist

### Body Fat Percentage

**Males:**

- ⚠️ **Low:** <8%
- ✅ **Normal:** 8-25%
- ⚠️ **High:** >25%

**Females:**

- ⚠️ **Low:** <21%
- ✅ **Normal:** 21-33%
- ⚠️ **High:** >33%

### Visceral Fat Level

- ✅ **Normal:** 1-9
- ⚠️ **High:** 10-14
- 🔴 **Very High:** 15-30

### Spirometry

- ✅ **Normal:** Normal lung function
- ⚠️ **Restrictive:** Restriction pattern
- ⚠️ **Obstructive:** Obstruction pattern

### Waist-Hip Ratio (WHR)

**Males:**

- ✅ **Low Risk:** <0.90
- ⚠️ **Moderate Risk:** 0.90-0.99
- 🔴 **High Risk:** ≥1.0

**Females:**

- ✅ **Low Risk:** <0.80
- ⚠️ **Moderate Risk:** 0.80-0.84
- 🔴 **High Risk:** ≥0.85

## Important Notes

### 1. Cross-Branch/Cross-Day Measurements

✅ **Supported** - The system can handle measurements from:

- Different branches (each measurement has `branch_id`)
- Different days (measurements within ±30 days of report date)
- Different visits

### 2. Measurement Selection

When multiple measurements of the same type exist:

- System uses measurements within ±30 days of lab report date
- Latest measurements are preferred
- WHR requires both Waist and Hip from any valid measurement dates

### 3. Data Validation

Ensure:

- Numeric values don't include units (e.g., "15" not "15 mmHg")
- Text values match exactly (case-insensitive for spirometry/colour vision)
- Visual acuity uses forward slash format (e.g., "6/6" not "6-6")
- Yes/No values are strings, not booleans

### 4. Calculated Fields

**WHR is auto-calculated** when both measurements exist:

- Formula: WHR = Waist ÷ Hip
- No need to send WHR separately
- Both Waist and Hip required for calculation

## Testing Checklist

Before go-live, verify:

- [ ] All measurement type names match exactly
- [ ] Numeric values are sent as strings without units
- [ ] Visual acuity uses "6/X" format
- [ ] Colour vision tests use "Yes"/"No" (not boolean)
- [ ] Spirometry uses "Normal"/"Restrictive"/"Obstructive"
- [ ] Waist and Hip measurements available for WHR calculation
- [ ] Measurements sync to database correctly
- [ ] Health reports display all measurements
- [ ] Cross-branch measurements work
- [ ] Cross-day measurements work

## Troubleshooting

### Measurement Not Showing in Report

1. **Check measurement sync:**
   - Verify measurement in `sgimed_measurements` table
   - Check `type_name` matches exactly

2. **Check date range:**
   - Measurement must be within ±30 days of report date
   - Check `measurement_date` field

3. **Check patient ID:**
   - Verify `patient_id` matches

4. **For WHR specifically:**
   - Both Waist AND Hip must exist
   - Hip cannot be zero
   - Check for calculation errors in logs

### Wrong Tag/Color in Report

1. **Check value format:**
   - Ensure numeric values are valid numbers
   - Verify text values match expected options

2. **Check gender:**
   - Some ranges are gender-specific (WHR, Body Fat)
   - Verify patient gender in system

## Contact

For technical issues with integration:

- Development Team: [contact details]

For clinical range questions:

- Clinical Team: [contact details]

---

**Last Updated:** April 8, 2026  
**Version:** 1.0
