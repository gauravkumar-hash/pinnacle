
from datetime import datetime, time, timedelta

def is_time_in_range(curr_dt: datetime, start_time: time, end_time: time, cutoff_time: int = 0) -> bool:
    # Combine current date with end time and subtract cut off time
    _end_time = end_time
    if cutoff_time > 0:
        _end_time = (datetime.combine(curr_dt.date(), end_time) - timedelta(minutes=cutoff_time)).time()

    return start_time <= curr_dt.time() <= _end_time
