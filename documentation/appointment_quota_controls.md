# Appointment Module Enhanced Control Features

## Overview

This document describes the enhanced control features added to the appointment module to manage patient flow to clinics through appointment quotas and session limits.

**Date Added:** April 8, 2026  
**Migration:** `e1f2a3b4c5d6_add_appointment_quota_controls.py`

---

## Features

### 1. Clinic Session Appointment Limits

Control the number of appointments allowed per clinic session (operating hours).

#### Database Changes

- **Table:** `appointment_operating_hours`
- **New Field:** `max_appointments_per_session` (Integer, Optional)

#### Usage

**Set Maximum Appointments Per Session:**
When creating or updating operating hours for a branch, you can now specify how many appointments are allowed for that time slot.

```python
# Example: Create operating hours with 10 appointments max per session
{
    "day": "MONDAY",
    "start_time": "09:00",
    "end_time": "12:00",
    "max_bookings": 1,
    "max_appointments_per_session": 10,  # NEW FIELD
    "branch_id": "branch-uuid"
}
```

**API Endpoints:**

- `POST /admin/appointment/operating-hours` - Create with session limit
- `PUT /admin/appointment/operating-hours/{branch_id}` - Update session limits
- `GET /admin/appointment/operating-hours/{branch_id}` - View current limits

---

### 2. Corporate Code Appointment Quotas

Control the total number of appointments and daily appointments allowed per corporate code. **This applies ONLY to appointments, NOT to telemedicine or other services.**

#### Database Changes

- **Table:** `appointment_corporate_codes`
- **New Fields:**
  - `max_appointments_total` (Integer, Optional) - Total appointment limit
  - `max_appointments_per_day` (Integer, Optional) - Daily appointment limit

- **New Table:** `appointment_corporate_quota_usage`
  - Tracks daily appointment usage per corporate code
  - Fields: `id`, `corporate_code_id`, `date`, `appointments_count`, `created_at`, `updated_at`

#### Usage

**Set Appointment Quotas for Corporate Code:**

```python
# Example: Create corporate code with quotas
{
    "code": "CORP123",
    "organization": "ABC Corporation",
    "max_appointments_total": 100,      # NEW FIELD - Total limit
    "max_appointments_per_day": 10,     # NEW FIELD - Daily limit
    "patient_survey": {},
    "corporate_survey": {},
    "is_active": true
}
```

**API Endpoints:**

1. **Create Corporate Code with Quotas**

   ```
   POST /admin/appointment/corporate-codes
   ```

2. **Update Corporate Code Quotas**

   ```
   PUT /admin/appointment/corporate-codes/{code_id}
   ```

3. **View Corporate Code Details (includes quotas)**

   ```
   GET /admin/appointment/corporate-codes/{code_id}
   ```

4. **Check Quota Usage (NEW)**

   ```
   GET /admin/appointment/corporate-codes/{code_id}/quota-usage
   ```

   **Response:**

   ```json
   {
     "corporate_code_id": "uuid",
     "code": "CORP123",
     "organization": "ABC Corporation",
     "max_appointments_total": 100,
     "max_appointments_per_day": 10,
     "total_appointments_used": 45,
     "today_appointments_used": 5,
     "quota_remaining_total": 55,
     "quota_remaining_today": 5
   }
   ```

---

## Important Notes

### Scope Limitations

- Corporate code quotas apply **ONLY to appointments**
- They do **NOT** apply to:
  - Telemedicine consultations
  - Walk-in visits
  - Other service types

### Quota Behavior

- **Total Quota (`max_appointments_total`):**
  - Tracks all appointments with this corporate code
  - Does not reset automatically
  - When limit is reached, no more appointments can be booked

- **Daily Quota (`max_appointments_per_day`):**
  - Tracks appointments scheduled for each specific date
  - Resets for each new date
  - When daily limit is reached, no more appointments can be booked for that day

### Null Values

- If `max_appointments_per_session` is `null`, no session limit is enforced
- If `max_appointments_total` is `null`, no total quota is enforced
- If `max_appointments_per_day` is `null`, no daily quota is enforced

---

## Database Migration

To apply these changes to the database:

```bash
# Run the migration
alembic upgrade head
```

To rollback:

```bash
# Rollback to previous version
alembic downgrade -1
```

---

## Implementation Details

### Models Updated

1. `models/appointment.py`:
   - `AppointmentBranchOperatingHours` - Added `max_appointments_per_session`
   - `AppointmentCorporateCode` - Added quota fields
   - `AppointmentCorporateQuotaUsage` - New tracking model

### Routers Updated

1. `routers/admin/appointment.py`:
   - Updated schemas: `CorporateCodeBase`, `CorporateCodeUpdate`, `OperatingHourBase`, `OperatingHourUpdate`
   - Updated endpoints to handle new fields
   - Added quota usage endpoint

### Client Implementation Requirements

When implementing quota checks in the patient-facing booking flow, you should:

1. Check corporate code quotas before allowing booking
2. Query the quota usage endpoint to show remaining slots
3. Display appropriate messages when quotas are exhausted
4. Filter out time slots that have reached session limits

---

## Examples

### Example 1: Limit Clinic to 15 Appointments Per Morning Session

```json
{
  "MONDAY": [
    {
      "start_time": "09:00",
      "end_time": "12:00",
      "max_bookings": 1,
      "max_appointments_per_session": 15
    }
  ]
}
```

### Example 2: Corporate Code with 500 Total and 50 Daily Appointments

```json
{
  "code": "HEALTHSCREEN2026",
  "organization": "Annual Health Screening Program",
  "max_appointments_total": 500,
  "max_appointments_per_day": 50,
  "valid_from": "2026-01-01T00:00:00+08:00",
  "valid_to": "2026-12-31T23:59:59+08:00"
}
```

---

## Testing

### Test Scenarios

1. **Session Limits:**
   - Create operating hours with `max_appointments_per_session`
   - Verify limit is enforced during booking
   - Verify null value allows unlimited bookings

2. **Corporate Code Total Quota:**
   - Create corporate code with `max_appointments_total`
   - Book appointments until quota reached
   - Verify further bookings are blocked

3. **Corporate Code Daily Quota:**
   - Create corporate code with `max_appointments_per_day`
   - Book appointments for specific date until quota reached
   - Verify bookings for other dates still work
   - Verify quota resets for new dates

4. **Quota Usage Endpoint:**
   - Test `/quota-usage` endpoint returns accurate counts
   - Verify cancelled appointments don't count toward quota

---

## Support

For questions or issues, please contact the development team.
