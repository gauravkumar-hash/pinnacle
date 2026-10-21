from models import OperatingHour, PublicHoliday, Blockoff, AppointmentBranchOperatingHours, AppointmentCount, Branch
from models.appointment import Appointment
from models.model_enums import AppointmentStatus, DayOfWeek
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from datetime import date, datetime, timedelta
from typing import Collection, Optional
from cachetools import cached, TTLCache, LRUCache
import math
from utils.sg_datetime import sgtz

# This is to mock the date while some are time based on DayOfWeek for date operations to work
DISCRETE_TIME_INTERVAL = 15
MOCK_DATE = date(2025,1, 1)

# Global cache for operating hours - used to invalidate cache when appointments change
_operating_hours_cache = None

def _init_cache():
    """Initialize the cache object for get_appointment_operating_hours."""
    global _operating_hours_cache
    if _operating_hours_cache is None:
        _operating_hours_cache = TTLCache(maxsize=1024, ttl=600)
    return _operating_hours_cache

def clear_operating_hours_cache():
    """Clear the operating hours cache to force refresh on next call."""
    global _operating_hours_cache
    if _operating_hours_cache is not None:
        _operating_hours_cache.clear()

def compute_time_changes(time_changes: dict[str, dict[datetime, int]], branch_id: str, calendar_id: str, start_time: datetime, end_time: datetime, cancelled: bool):
    '''
    Compute Time Changes for Appointment Count Cache
    '''
    branch_cal_id = f"{branch_id}_{calendar_id}"
    if branch_cal_id not in time_changes:
        time_changes[branch_cal_id] = {}

    branch_changes = time_changes[branch_cal_id]
    # Ensure start time is in DISCRETE_TIME_INTERVAL minute intervals
    new_start_time = start_time - timedelta(minutes=start_time.minute % DISCRETE_TIME_INTERVAL)
    while new_start_time < end_time:
        if new_start_time not in branch_changes:
            branch_changes[new_start_time] = 0
        branch_changes[new_start_time] += 1 if not cancelled else -1
        new_start_time += timedelta(minutes=DISCRETE_TIME_INTERVAL)

    return time_changes

def update_time_changes(db: Session, time_changes: dict[str, dict[datetime, int]]):
    '''
    Update Appointment Count Cache
    '''
    # TODO: Can just update after current time since we are not using the time changes for anything else

    for branch_cal_id, changes in time_changes.items():
        branch_id, calendar_id = branch_cal_id.split('_')
        start_time = min(changes.keys())
        end_time = max(changes.keys())

        rows = db.query(AppointmentCount).filter(
                AppointmentCount.sgimed_branch_id == branch_id,
                AppointmentCount.sgimed_calendar_id == calendar_id,
                AppointmentCount.time >= start_time,
                AppointmentCount.time <= end_time
            ).all()

        existing_changes = { row.time: row for row in rows }
        for time, count in changes.items():
            if time in existing_changes:
                existing_changes[time].count += count
            else:
                db.add(AppointmentCount(
                    sgimed_branch_id=branch_id,
                    sgimed_calendar_id=calendar_id,
                    time=time,
                    count=count
                ))
        db.commit()


@cached(cache=_init_cache())
def get_appointment_operating_hours(db: Session, branch: Branch, start_date: datetime, end_date: datetime):
    '''
    1. Get Branch Operating Hours
    2. Get Appointment Operating Hours
    3. Combine operating hours and appointment operating hours
    4. Get Public Holidays & Blockoffs
    5. Convert to discrete times
    6. Remove blockoffs from operating hours
    '''
    # Get Branch Operating Hours
    # 1. Managing by DayOfWeek and Time
    operating_hours = db.query(OperatingHour).filter(
        OperatingHour.branch_id == branch.id
    ).all()
    branch_operating_hours_discrete: dict[DayOfWeek, list[datetime]] = {}
    for row in operating_hours:
        start_time = sgtz.localize(datetime.combine(MOCK_DATE, row.start_time))
        end_time = sgtz.localize(datetime.combine(MOCK_DATE, row.end_time)) - timedelta(minutes=row.cutoff_time)
        discrete_times = convert_start_end_time_to_discrete(start_time, end_time, DISCRETE_TIME_INTERVAL)
        if row.day not in branch_operating_hours_discrete:
            branch_operating_hours_discrete[row.day] = []
        branch_operating_hours_discrete[row.day].extend(discrete_times)
    # Get Appointment Operating Hours
    appt_operating_hours_discrete: dict[DayOfWeek, list[datetime]] = {}
    appt_operating_hours_discrete_max_bookings: dict[DayOfWeek, list[tuple[datetime, int]]] = {}
    appt_operating_hours_discrete_max_per_session: dict[DayOfWeek, list[tuple[datetime, int | None]]] = {}
    appt_operating_hours_discrete_max_clinic: dict[DayOfWeek, list[tuple[datetime, int | None]]] = {}
    appt_operating_hours_discrete_max_corporate: dict[DayOfWeek, list[tuple[datetime, int | None]]] = {}
    appointment_operating_hours = db.query(AppointmentBranchOperatingHours).filter(
        AppointmentBranchOperatingHours.branch_id == branch.id
    ).all()
    for row in appointment_operating_hours:
        start_time = sgtz.localize(datetime.combine(MOCK_DATE, row.start_time))
        end_time = sgtz.localize(datetime.combine(MOCK_DATE, row.end_time)) - timedelta(minutes=row.cutoff_time)
        discrete_times = convert_start_end_time_to_discrete(start_time, end_time, DISCRETE_TIME_INTERVAL)
        if row.day not in appt_operating_hours_discrete:
            appt_operating_hours_discrete[row.day] = []
            appt_operating_hours_discrete_max_bookings[row.day] = []
            appt_operating_hours_discrete_max_per_session[row.day] = []
            appt_operating_hours_discrete_max_clinic[row.day] = []
            appt_operating_hours_discrete_max_corporate[row.day] = []
        appt_operating_hours_discrete[row.day].extend(discrete_times)
        appt_operating_hours_discrete_max_bookings[row.day].extend((discrete_time, row.max_bookings) for discrete_time in discrete_times)
        appt_operating_hours_discrete_max_per_session[row.day].extend((discrete_time, row.max_appointments_per_session) for discrete_time in discrete_times)
        appt_operating_hours_discrete_max_clinic[row.day].extend((discrete_time, row.max_clinic_bookings) for discrete_time in discrete_times)
        appt_operating_hours_discrete_max_corporate[row.day].extend((discrete_time, row.max_corporate_bookings) for discrete_time in discrete_times)
        # This updates the max bookings for each discrete time
    # Combine operating hours and appointment operating hours
    for day in appt_operating_hours_discrete:
        if day not in branch_operating_hours_discrete:
            appt_operating_hours_discrete[day] = []
            continue
        appt_operating_hours_discrete[day] = list(set(appt_operating_hours_discrete[day]) & set(branch_operating_hours_discrete[day]))

    # 2. Convert to dates
    public_holidays = db.query(PublicHoliday.date).filter(
        PublicHoliday.date >= start_date,
        PublicHoliday.date <= end_date,
    ).all()
    public_holidays = [row[0] for row in public_holidays]

    blockoffs = db.query(Blockoff) \
        .options(
            joinedload(Blockoff.branches).load_only(Branch.id),
        ) \
        .filter(
            Blockoff.branches.any(Branch.id == branch.id),
            Blockoff.date >= start_date,
            Blockoff.date <= end_date,
            Blockoff.enabled == True,
            Blockoff.deleted == False
        ).all()
    blockoffs_dict: dict[date, list[datetime]] = {}
    for row in blockoffs:
        if row.date not in blockoffs_dict:
            blockoffs_dict[row.date] = []
        blockoffs_dict[row.date] += convert_start_end_time_to_discrete(
            sgtz.localize(datetime.combine(row.date, row.start_time)),
            sgtz.localize(datetime.combine(row.date, row.end_time)),
            DISCRETE_TIME_INTERVAL
        )

    operating_hours_discrete: set[datetime] = set()
    operating_hours_max_bookings: dict[datetime, int] = {}
    operating_hours_max_appts_per_session: dict[datetime, int] = {}
    operating_hours_max_clinic: dict[datetime, int] = {}
    operating_hours_max_corporate: dict[datetime, int] = {}
    current_date = start_date
    while current_date <= end_date:
        curr_day = DayOfWeek[current_date.strftime("%A").upper()]
        if current_date.date() in public_holidays:
            curr_day = DayOfWeek.PUBLIC_HOLIDAY

        hours = appt_operating_hours_discrete.get(curr_day, None)
        if hours is None:
            current_date += timedelta(days=1)
            continue

        # Remove any blockoffs
        blockoffs = blockoffs_dict.get(current_date.date(), None)
        hours = set([
            sgtz.localize(datetime.combine(current_date, hour.time()))
            for hour in hours
        ])
        if blockoffs:
            hours -= set(blockoffs)

        # Update the operating hours and max bookings
        operating_hours_discrete.update(hours)
        operating_hours_max_bookings.update({
            sgtz.localize(datetime.combine(current_date, day_time.time())): max_bookings
            for day_time, max_bookings in appt_operating_hours_discrete_max_bookings[curr_day]
            if sgtz.localize(datetime.combine(current_date, day_time.time())) in hours
        })
        # Update max_appointments_per_session (only store slots that have a limit set)
        operating_hours_max_appts_per_session.update({
            sgtz.localize(datetime.combine(current_date, day_time.time())): max_per_session
            for day_time, max_per_session in appt_operating_hours_discrete_max_per_session[curr_day]
            if max_per_session is not None
            and sgtz.localize(datetime.combine(current_date, day_time.time())) in hours
        })
        # Clinic / corporate split of max_bookings (only store slots that have a limit set)
        operating_hours_max_clinic.update({
            sgtz.localize(datetime.combine(current_date, day_time.time())): max_clinic
            for day_time, max_clinic in appt_operating_hours_discrete_max_clinic[curr_day]
            if max_clinic is not None
            and sgtz.localize(datetime.combine(current_date, day_time.time())) in hours
        })
        operating_hours_max_corporate.update({
            sgtz.localize(datetime.combine(current_date, day_time.time())): max_corporate
            for day_time, max_corporate in appt_operating_hours_discrete_max_corporate[curr_day]
            if max_corporate is not None
            and sgtz.localize(datetime.combine(current_date, day_time.time())) in hours
        })

        current_date += timedelta(days=1)

    return operating_hours_discrete, operating_hours_max_bookings, operating_hours_max_appts_per_session, operating_hours_max_clinic, operating_hours_max_corporate

@cached(cache=LRUCache(maxsize=32))
def convert_start_end_time_to_discrete(start_dt: datetime, end_dt: datetime, interval: int) -> list[datetime]:
    # Ensure start_dt is multiple of interval
    start_dt_interval = start_dt - timedelta(minutes=start_dt.minute % interval, seconds=start_dt.second, microseconds=start_dt.microsecond)
    discrete_times = []
    while start_dt_interval < end_dt:
        discrete_times.append(start_dt_interval)
        start_dt_interval += timedelta(minutes=interval)
    return discrete_times

def get_appointment_booked_slots(db: Session, branch: Branch, start_date: datetime, end_date: datetime, available_slots: set[datetime], appt_operating_hours_discrete_max_bookings: dict[datetime, int], max_appts_per_session: dict[datetime, int] = {}):
    booked_slots = db.query(AppointmentCount).filter(
        AppointmentCount.sgimed_branch_id == branch.sgimed_branch_id,
        AppointmentCount.sgimed_calendar_id == branch.sgimed_calendar_id,
        AppointmentCount.time >= start_date,
        AppointmentCount.time <= end_date,
        AppointmentCount.count >= min(appt_operating_hours_discrete_max_bookings.values()),
    ).all()

    # This is to check if the max bookings are different for different times
    require_max_bookings_check = len(set(appt_operating_hours_discrete_max_bookings.values())) > 1
    def filter_booked_slots(booked_slot: AppointmentCount):
        if booked_slot.time not in available_slots:
            return False

        # This is to check if the booked slot is available within the available timeslots
        if require_max_bookings_check:
            if booked_slot.count < appt_operating_hours_discrete_max_bookings[booked_slot.time]:
                return False

        # This means the booked slot is not available within the available timeslots
        return True

    sgimed_full_slots = set([row.time for row in filter(filter_booked_slots, booked_slots)])

    # Enforce max_appointments_per_session: count actual confirmed/completed appointments per slot
    session_full_slots: set[datetime] = set()
    if max_appts_per_session:
        branch_id_str = str(branch.id)
        # Get all active appointment counts per start_datetime for this branch in range
        appt_counts = db.query(
            Appointment.start_datetime,
            func.count(Appointment.id).label('count')
        ).filter(
            Appointment.start_datetime >= start_date,
            Appointment.start_datetime <= end_date,
            Appointment.status.not_in([AppointmentStatus.CANCELLED, AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED]),
            Appointment.branch.op('->>')('id') == branch_id_str,
        ).group_by(Appointment.start_datetime).all()

        for slot_dt, count in appt_counts:
            if slot_dt in available_slots and slot_dt in max_appts_per_session:
                if count >= max_appts_per_session[slot_dt]:
                    session_full_slots.add(slot_dt)

    return sgimed_full_slots | session_full_slots

def get_corporate_slot_counts(db: Session, branch: Branch, start_date: datetime, end_date: datetime, exclude_appointment_ids: Collection = ()) -> dict[datetime, int]:
    '''
    Count bookings made with an appointment corporate code per 15 min slot at this branch.
    Mirrors how they are placed in SGiMed: patients of one booking go back to back from start_datetime
    (main appointment first, then family members by index), so a booking holds one place in each slot it covers.
    '''
    rows = db.query(
        Appointment.id, Appointment.group_id, Appointment.index, Appointment.start_datetime, Appointment.duration, Appointment.status
    ).filter(
        Appointment.corporate_code.isnot(None),
        Appointment.corporate_code != '',
        Appointment.branch.op('->>')('id') == str(branch.id),
        # A booking with several patients can start before the range and run into it
        Appointment.start_datetime >= start_date - timedelta(days=1),
        Appointment.start_datetime <= end_date,
    ).all()

    # Rows of one booking share group_id and start_datetime; cancelled rows still keep their place in the sequence
    bookings: dict[tuple, list] = {}
    for row in rows:
        if row.id in exclude_appointment_ids:
            continue
        bookings.setdefault((row.group_id or str(row.id), row.start_datetime), []).append(row)

    released_statuses = (AppointmentStatus.CANCELLED, AppointmentStatus.PREPAYMENT, AppointmentStatus.PAYMENT_STARTED)
    counts: dict[datetime, int] = {}
    for (_, start_datetime), booking_rows in bookings.items():
        cursor = start_datetime
        for row in sorted(booking_rows, key=lambda r: r.index or 0):
            row_end = cursor + timedelta(minutes=row.duration or 0)
            if row.status not in released_statuses:
                for slot in convert_start_end_time_to_discrete(cursor, row_end, DISCRETE_TIME_INTERVAL):
                    counts[slot] = counts.get(slot, 0) + 1
            cursor = row_end
    return counts

def get_category_full_slots(
    db: Session,
    branch: Branch,
    slots: set[datetime],
    max_clinic: dict[datetime, int],
    max_corporate: dict[datetime, int],
    is_corporate: bool,
    code_max_bookings: Optional[int] = None,
    exclude_appointment_ids: Collection = (),
) -> set[datetime]:
    '''
    Slots where this patient's category has used up its share of max_bookings.
    - Clinic patient (no corporate code): clinic bookings = all SGiMed bookings - corporate bookings, limited by max_clinic_bookings
    - Corporate patient: corporate bookings limited by max_corporate_bookings and the code's max_bookings_per_slot.
      The code limit is compared against ALL corporate bookings in the slot, i.e. it is how many of the corporate
      slots this code may see (limits of different codes do not stack).
    Limits that are not set do not restrict, so nothing is queried when no split is configured.
    '''
    caps: dict[datetime, int] = {}
    for slot in slots:
        limits = [max_corporate.get(slot), code_max_bookings] if is_corporate else [max_clinic.get(slot)]
        limits = [limit for limit in limits if limit is not None]
        if limits:
            caps[slot] = min(limits)
    if not caps:
        return set()

    start_date = min(caps)
    end_date = max(caps) + timedelta(minutes=DISCRETE_TIME_INTERVAL)
    counts = get_corporate_slot_counts(db, branch, start_date, end_date, exclude_appointment_ids)
    if not is_corporate:
        total_counts = {
            row.time: row.count
            for row in db.query(AppointmentCount.time, AppointmentCount.count).filter(
                AppointmentCount.sgimed_branch_id == branch.sgimed_branch_id,
                AppointmentCount.sgimed_calendar_id == branch.sgimed_calendar_id,
                AppointmentCount.time >= start_date,
                AppointmentCount.time <= end_date,
            ).all()
        }
        # SGiMed counts lag until the appointments cron picks up new bookings, so clamp at 0 rather than go negative
        counts = {slot: max(0, total_counts.get(slot, 0) - counts.get(slot, 0)) for slot in caps}

    return {slot for slot, cap in caps.items() if counts.get(slot, 0) >= cap}

def get_available_slots(timings: set[datetime], duration_mins: int): # , spacing: Optional[int] = None):
    interval = timedelta(minutes=DISCRETE_TIME_INTERVAL)
    slots_needed = math.ceil(duration_mins / DISCRETE_TIME_INTERVAL)
    # spacing_delta = timedelta(minutes=spacing) if spacing else None

    valid_start_times = []
    # prev_time = None
    for start_time in sorted(timings):
        # Check if all required slots exist using set operations
        all_slots_exist = all(
            start_time + interval * i in timings
            for i in range(1, slots_needed)
        )
        if all_slots_exist:
            # if spacing_delta:
            #     if prev_time and start_time - prev_time < spacing_delta:
            #         continue
            valid_start_times.append(start_time)
            # prev_time = start_time

    return valid_start_times
