# Appointment Module Enhancement - Summary

## Changes Implemented

### 1. Database Model Updates

#### `models/appointment.py`

**AppointmentBranchOperatingHours:**

- Added `max_appointments_per_session` field (Integer, Optional)
- Controls the number of appointments allowed per clinic session/time slot

**AppointmentCorporateCode:**

- Added `max_appointments_total` field (Integer, Optional) - Total appointment limit
- Added `max_appointments_per_day` field (Integer, Optional) - Daily appointment limit
- These quotas apply ONLY to appointments, NOT telemedicine

**AppointmentCorporateQuotaUsage (NEW MODEL):**

- Tracks daily appointment usage per corporate code
- Fields: id, corporate_code_id, date, appointments_count, created_at, updated_at
- Indexed on corporate_code_id and date for efficient querying

---

### 2. API Endpoints Updated

#### `routers/admin/appointment.py`

**Updated Schemas:**

- `CorporateCodeBase` - Added quota fields
- `CorporateCodeUpdate` - Added quota fields
- `OperatingHourBase` - Added max_appointments_per_session
- `OperatingHourUpdate` - Added max_appointments_per_session

**Updated Endpoints:**

1. **GET /admin/appointment/corporate-codes**
   - Now returns quota fields in response

2. **POST /admin/appointment/corporate-codes**
   - Accepts quota fields during creation

3. **GET /admin/appointment/corporate-codes/{code_id}**
   - Returns quota fields in details

4. **PUT /admin/appointment/corporate-codes/{code_id}**
   - Allows updating quota fields

5. **GET /admin/appointment/operating-hours/{branch_id}**
   - Returns max_appointments_per_session in response

6. **PUT /admin/appointment/operating-hours/{branch_id}**
   - Accepts max_appointments_per_session during update

7. **POST /admin/appointment/operating-hours**
   - Accepts max_appointments_per_session during creation

**New Endpoint:**

8. **GET /admin/appointment/corporate-codes/{code_id}/quota-usage**
   - Returns real-time quota usage statistics
   - Shows total appointments used, today's appointments, and remaining quotas

---

### 3. Database Migration

**File:** `alembic/versions/e1f2a3b4c5d6_add_appointment_quota_controls.py`

**Changes:**

- Adds `max_appointments_per_session` column to `appointment_operating_hours`
- Adds `max_appointments_total` and `max_appointments_per_day` columns to `appointment_corporate_codes`
- Creates new `appointment_corporate_quota_usage` table with indexes

**To Apply:**

```bash
alembic upgrade head
```

---

### 4. Documentation

**File:** `documentation/appointment_quota_controls.md`

Comprehensive documentation covering:

- Feature overview and usage
- API endpoint details
- Database schema changes
- Implementation examples
- Testing scenarios
- Important notes about scope (appointments only, not telemedicine)

---

## Key Features

### Feature 1: Clinic Session Limits

- Administrators can set maximum appointments per session (time slot)
- Example: Morning session 9AM-12PM can have max 15 appointments
- Null value = unlimited appointments

### Feature 2: Corporate Code Quotas (Appointments Only)

- **Total Quota**: Limit total appointments across all dates
- **Daily Quota**: Limit appointments per specific date
- Quotas apply ONLY to appointments, NOT telemedicine or other services
- Real-time quota usage tracking via API

---

## Usage Examples

### Set Session Limit

```json
POST /admin/appointment/operating-hours
{
    "day": "MONDAY",
    "start_time": "09:00",
    "end_time": "12:00",
    "max_appointments_per_session": 15,
    "branch_id": "branch-uuid"
}
```

### Set Corporate Code Quotas

```json
POST /admin/appointment/corporate-codes
{
    "code": "CORP2026",
    "organization": "Health Screening",
    "max_appointments_total": 500,
    "max_appointments_per_day": 50
}
```

### Check Quota Usage

```bash
GET /admin/appointment/corporate-codes/{code_id}/quota-usage
```

Response:

```json
{
  "total_appointments_used": 45,
  "today_appointments_used": 5,
  "quota_remaining_total": 455,
  "quota_remaining_today": 45
}
```

---

## Next Steps

1. **Run Migration:**

   ```bash
   alembic upgrade head
   ```

2. **Test Endpoints:**
   - Test creating/updating operating hours with session limits
   - Test creating/updating corporate codes with quotas
   - Test quota usage endpoint

3. **Frontend Implementation:**
   - Update admin UI to show/edit new quota fields
   - Implement quota checks in patient booking flow
   - Display remaining slots to users

4. **Validation Logic:**
   - Add booking validation to check session limits
   - Add booking validation to check corporate code quotas
   - Handle quota exceeded scenarios gracefully

---

## Important Notes

- **Scope:** Corporate code quotas apply ONLY to appointments
- **Null Values:** Null quota values mean no limit is enforced
- **Cancelled Appointments:** Should not count toward quotas (check Appointment.status != CANCELLED)
- **Date Tracking:** Daily quotas are based on appointment start_datetime date

---

## Files Modified

1. `models/appointment.py` - Added fields and new model
2. `routers/admin/appointment.py` - Updated schemas and endpoints
3. `alembic/versions/e1f2a3b4c5d6_add_appointment_quota_controls.py` - Migration file
4. `documentation/appointment_quota_controls.md` - Feature documentation

---

## Contact

For questions or issues related to these changes, please contact the development team.
