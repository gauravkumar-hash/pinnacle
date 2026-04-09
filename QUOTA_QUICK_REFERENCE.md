# Quick Reference: Appointment Quota Controls

## Overview

Enhanced controls for the appointment module allowing administrators to:

1. Control appointments per clinic session
2. Control appointments per corporate code (appointments only, NOT telemedicine)

---

## API Quick Reference

### 1. Clinic Session Limits

**Get Operating Hours:**

```http
GET /admin/appointment/operating-hours/{branch_id}
```

**Update Operating Hours:**

```http
PUT /admin/appointment/operating-hours/{branch_id}
Content-Type: application/json

{
  "MONDAY": [
    {
      "start_time": "09:00",
      "end_time": "12:00",
      "max_bookings": 1,
      "max_appointments_per_session": 15  # NEW
    }
  ]
}
```

**Create Operating Hour:**

```http
POST /admin/appointment/operating-hours
Content-Type: application/json

{
  "day": "MONDAY",
  "start_time": "09:00",
  "end_time": "12:00",
  "max_bookings": 1,
  "max_appointments_per_session": 15,  # NEW
  "branch_id": "uuid"
}
```

---

### 2. Corporate Code Quotas

**Get All Corporate Codes:**

```http
GET /admin/appointment/corporate-codes
```

**Get Corporate Code Details:**

```http
GET /admin/appointment/corporate-codes/{code_id}
```

**Create Corporate Code with Quotas:**

```http
POST /admin/appointment/corporate-codes
Content-Type: application/json

{
  "code": "CORP2026",
  "organization": "ABC Corp",
  "max_appointments_total": 500,      # NEW - Total limit
  "max_appointments_per_day": 50,     # NEW - Daily limit
  "patient_survey": {},
  "corporate_survey": {},
  "is_active": true
}
```

**Update Corporate Code Quotas:**

```http
PUT /admin/appointment/corporate-codes/{code_id}
Content-Type: application/json

{
  "max_appointments_total": 1000,
  "max_appointments_per_day": 100
}
```

**Get Quota Usage (NEW):**

```http
GET /admin/appointment/corporate-codes/{code_id}/quota-usage
```

Response:

```json
{
  "corporate_code_id": "uuid",
  "code": "CORP2026",
  "organization": "ABC Corp",
  "max_appointments_total": 500,
  "max_appointments_per_day": 50,
  "total_appointments_used": 123,
  "today_appointments_used": 8,
  "quota_remaining_total": 377,
  "quota_remaining_today": 42
}
```

---

## Database Fields

### appointment_operating_hours

- `max_appointments_per_session` (int, optional) - Max appointments for this time slot

### appointment_corporate_codes

- `max_appointments_total` (int, optional) - Total appointment limit
- `max_appointments_per_day` (int, optional) - Daily appointment limit

### appointment_corporate_quota_usage (NEW TABLE)

- `corporate_code_id` - FK to corporate code
- `date` - Date of quota tracking
- `appointments_count` - Number of appointments for this date

---

## Migration

```bash
# Apply changes
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

---

## Important Rules

✅ **APPLIES TO:**

- Appointments only

❌ **DOES NOT APPLY TO:**

- Telemedicine
- Walk-ins
- Other services

---

## NULL Behavior

- `null` value = No limit enforced
- `0` value = No appointments allowed
- Positive integer = Maximum allowed

---

## Validation Logic (To Implement)

When booking an appointment:

1. **Check Session Limit:**

   ```python
   if operating_hour.max_appointments_per_session:
       current_count = count_appointments_for_session(...)
       if current_count >= operating_hour.max_appointments_per_session:
           raise QuotaExceeded("Session is full")
   ```

2. **Check Corporate Code Total Quota:**

   ```python
   if corporate_code.max_appointments_total:
       total_used = count_total_appointments(corporate_code)
       if total_used >= corporate_code.max_appointments_total:
           raise QuotaExceeded("Total quota reached")
   ```

3. **Check Corporate Code Daily Quota:**
   ```python
   if corporate_code.max_appointments_per_day:
       daily_used = count_appointments_for_date(corporate_code, date)
       if daily_used >= corporate_code.max_appointments_per_day:
           raise QuotaExceeded("Daily quota reached for this date")
   ```

---

## Example Scenarios

### Scenario 1: Health Screening Campaign

```json
{
  "code": "HEALTHSCREEN2026",
  "max_appointments_total": 1000,
  "max_appointments_per_day": 50
}
```

- Total 1000 appointments across all dates
- Maximum 50 appointments per day

### Scenario 2: Clinic Capacity Management

```json
{
  "day": "MONDAY",
  "start_time": "09:00",
  "end_time": "12:00",
  "max_appointments_per_session": 20
}
```

- Monday morning session limited to 20 appointments

### Scenario 3: VIP Corporate Code (No Limits)

```json
{
  "code": "VIP2026",
  "max_appointments_total": null,
  "max_appointments_per_day": null
}
```

- No quota restrictions

---

## Testing Checklist

- [ ] Create operating hours with session limit
- [ ] Verify session limit enforced
- [ ] Create corporate code with total quota
- [ ] Create corporate code with daily quota
- [ ] Book appointments until quota reached
- [ ] Verify quota usage endpoint returns correct counts
- [ ] Verify cancelled appointments don't count
- [ ] Verify null values allow unlimited bookings
- [ ] Test quota update functionality

---

## Support

Full documentation: `documentation/appointment_quota_controls.md`
Implementation summary: `APPOINTMENT_QUOTA_IMPLEMENTATION_SUMMARY.md`
