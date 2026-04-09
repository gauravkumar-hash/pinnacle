# Implementation Checklist for Appointment Quota Controls

## Backend Implementation ✅ COMPLETED

- [x] Add database fields to models
- [x] Create quota usage tracking model
- [x] Update API schemas
- [x] Update endpoints to handle quota fields
- [x] Create quota usage endpoint
- [x] Create database migration
- [x] Write documentation

---

## Frontend Admin UI - TODO

### Corporate Code Management

- [ ] **Display Quota Fields**
  - [ ] Add "Max Appointments Total" field to corporate code form
  - [ ] Add "Max Appointments Per Day" field to corporate code form
  - [ ] Show quota fields in corporate code list/detail views

- [ ] **Quota Usage Dashboard**
  - [ ] Create quota usage widget showing:
    - Total appointments used / total limit
    - Today's appointments used / daily limit
    - Progress bars for visual representation
  - [ ] Add "View Quota Usage" button on corporate code details
  - [ ] Display real-time quota statistics

### Operating Hours Management

- [ ] **Display Session Limits**
  - [ ] Add "Max Appointments Per Session" field to operating hours form
  - [ ] Show session limit in operating hours list
  - [ ] Allow editing session limits

---

## Patient Booking Flow - TODO

### Validation Logic

- [ ] **Session Limit Check**

  ```javascript
  // Before showing time slot as available
  if (operatingHour.max_appointments_per_session) {
    const currentCount = await getAppointmentsForSession(sessionId);
    if (currentCount >= operatingHour.max_appointments_per_session) {
      // Mark slot as full or hide it
      slot.isFull = true;
    }
  }
  ```

- [ ] **Corporate Code Quota Check**

  ```javascript
  // When corporate code is entered
  const quotaUsage = await fetch(`/api/corporate-codes/${codeId}/quota-usage`);

  // Check total quota
  if (quotaUsage.max_appointments_total) {
    if (quotaUsage.quota_remaining_total <= 0) {
      showError("This corporate code has reached its maximum appointments");
      return false;
    }
  }

  // Check daily quota for selected date
  if (quotaUsage.max_appointments_per_day) {
    const dailyUsed = await getDailyUsage(codeId, selectedDate);
    if (dailyUsed >= quotaUsage.max_appointments_per_day) {
      showError(
        "This corporate code has reached its daily limit for this date",
      );
      return false;
    }
  }
  ```

### User Experience

- [ ] **Show Available Slots**
  - [ ] Display remaining appointments for each session
  - [ ] Example: "15/20 slots available"
  - [ ] Hide or grey out full sessions

- [ ] **Corporate Code Feedback**
  - [ ] Show remaining quota when code is validated
  - [ ] Example: "45 appointments remaining (5 today)"
  - [ ] Warning message when quota is low (< 10%)

- [ ] **Error Messages**
  - [ ] "Session is fully booked. Please select another time."
  - [ ] "Corporate code has reached its maximum appointments."
  - [ ] "Corporate code daily limit reached. Please select another date."

---

## Backend Validation - TODO

### Booking Creation Endpoint

Add validation in the appointment booking endpoint:

```python
def create_appointment(...):
    # 1. Check session limit
    if operating_hour.max_appointments_per_session:
        session_count = db.query(func.count(Appointment.id)).filter(
            Appointment.start_datetime >= session_start,
            Appointment.start_datetime < session_end,
            Appointment.status != AppointmentStatus.CANCELLED
        ).scalar()

        if session_count >= operating_hour.max_appointments_per_session:
            raise HTTPException(
                status_code=400,
                detail="This session is fully booked"
            )

    # 2. Check corporate code total quota
    if corporate_code and corporate_code.max_appointments_total:
        total_count = db.query(func.count(Appointment.id)).filter(
            Appointment.corporate_code == corporate_code.code,
            Appointment.status != AppointmentStatus.CANCELLED
        ).scalar()

        if total_count >= corporate_code.max_appointments_total:
            raise HTTPException(
                status_code=400,
                detail="Corporate code quota exceeded"
            )

    # 3. Check corporate code daily quota
    if corporate_code and corporate_code.max_appointments_per_day:
        daily_count = db.query(func.count(Appointment.id)).filter(
            Appointment.corporate_code == corporate_code.code,
            Appointment.status != AppointmentStatus.CANCELLED,
            func.date(Appointment.start_datetime) == appointment_date
        ).scalar()

        if daily_count >= corporate_code.max_appointments_per_day:
            raise HTTPException(
                status_code=400,
                detail="Daily quota exceeded for this date"
            )

    # Proceed with booking...
```

---

## Database Migration - TODO

```bash
# Run migration to add new fields
alembic upgrade head
```

---

## Testing - TODO

### Unit Tests

- [ ] Test operating hours with session limits
- [ ] Test corporate code with total quota
- [ ] Test corporate code with daily quota
- [ ] Test quota usage endpoint
- [ ] Test booking validation with quotas

### Integration Tests

- [ ] Test full booking flow with session limits
- [ ] Test full booking flow with corporate quotas
- [ ] Test quota enforcement across multiple bookings
- [ ] Test cancelled appointments don't count

### Manual Testing

- [ ] Admin can set/update session limits
- [ ] Admin can set/update corporate quotas
- [ ] Admin can view quota usage
- [ ] Patients cannot book when quota reached
- [ ] Patients see accurate available slots
- [ ] Error messages are clear and helpful

---

## Deployment Steps

1. **Backup Database**

   ```bash
   pg_dump database_name > backup_$(date +%Y%m%d).sql
   ```

2. **Run Migration**

   ```bash
   alembic upgrade head
   ```

3. **Verify Migration**

   ```bash
   # Check tables exist
   psql -d database_name -c "\d appointment_operating_hours"
   psql -d database_name -c "\d appointment_corporate_codes"
   psql -d database_name -c "\d appointment_corporate_quota_usage"
   ```

4. **Test Endpoints**
   - Test creating/updating operating hours
   - Test creating/updating corporate codes
   - Test quota usage endpoint

5. **Deploy Frontend**
   - Deploy admin UI updates
   - Deploy patient booking flow updates

6. **Monitor**
   - Watch for validation errors
   - Monitor quota usage
   - Check user feedback

---

## Rollback Plan

If issues occur:

```bash
# Rollback migration
alembic downgrade -1

# Restore from backup if needed
psql database_name < backup_YYYYMMDD.sql
```

---

## Performance Considerations

- [ ] Add indexes on frequently queried fields
- [ ] Cache quota usage data (short TTL)
- [ ] Optimize appointment count queries
- [ ] Consider using database triggers for quota tracking

---

## Future Enhancements

Potential improvements for later:

- [ ] Weekly quota limits
- [ ] Monthly quota limits
- [ ] Quota alerts (email admin when 80% reached)
- [ ] Quota override permissions
- [ ] Historical quota usage reports
- [ ] Auto-reset quota feature
- [ ] Quota sharing across multiple corporate codes

---

## Documentation

- ✅ API documentation: `documentation/appointment_quota_controls.md`
- ✅ Implementation summary: `APPOINTMENT_QUOTA_IMPLEMENTATION_SUMMARY.md`
- ✅ Quick reference: `QUOTA_QUICK_REFERENCE.md`
- [ ] User manual for admins
- [ ] API integration guide for frontend

---

## Support Contacts

- Backend Team: [Contact Info]
- Frontend Team: [Contact Info]
- Database Admin: [Contact Info]
- Product Owner: [Contact Info]

---

**Last Updated:** April 8, 2026
