from models import OperatingHour, PublicHoliday, Blockoff, AppointmentBranchOperatingHours, AppointmentCount, Branch
from models.model_enums import DayOfWeek
from sqlalchemy.orm import Session, joinedload
from datetime import date, datetime, timedelta
from cachetools import cached, TTLCache, LRUCache
import math
from utils.sg_datetime import sgtz

# This is to mock the date while some are time based on DayOfWeek for date operations to work
DISCRETE_TIME_INTERVAL = 15
MOCK_DATE = date(2025,1, 1)

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


@cached(cache=TTLCache(maxsize=1024, ttl=600))
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
        appt_operating_hours_discrete[row.day].extend(discrete_times)
        appt_operating_hours_discrete_max_bookings[row.day].extend((discrete_time, row.max_bookings) for discrete_time in discrete_times)
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

        current_date += timedelta(days=1)

    return operating_hours_discrete, operating_hours_max_bookings

@cached(cache=LRUCache(maxsize=32))
def convert_start_end_time_to_discrete(start_dt: datetime, end_dt: datetime, interval: int) -> list[datetime]:
    # Ensure start_dt is multiple of interval
    start_dt_interval = start_dt - timedelta(minutes=start_dt.minute % interval, seconds=start_dt.second, microseconds=start_dt.microsecond)
    discrete_times = []
    while start_dt_interval < end_dt:
        discrete_times.append(start_dt_interval)
        start_dt_interval += timedelta(minutes=interval)
    return discrete_times

def get_appointment_booked_slots(db: Session, branch: Branch, start_date: datetime, end_date: datetime, available_slots: set[datetime], appt_operating_hours_discrete_max_bookings: dict[datetime, int]):
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

    return set([row.time for row in filter(filter_booked_slots, booked_slots)])

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
