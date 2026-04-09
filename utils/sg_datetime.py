# Used to get localized Singapore Time
from datetime import date, datetime, time

import pytz
sgtz = pytz.timezone("Asia/Singapore") 

def sg(dt: datetime):
    return dt.replace(tzinfo=pytz.utc).astimezone(sgtz)

def now():
    return datetime.now(sgtz)

def midnight(curr_date: date | None = None):
    if curr_date is None:
        curr_date = now()
    return sgtz.localize(datetime.combine(curr_date, time.min))

def strptime(date_str: str, format: str):
    return datetime.strptime(date_str, format).astimezone(sgtz)

def fromtimestamp(timestamp: float):
    return datetime.fromtimestamp(timestamp).astimezone(sgtz)

def custom_date_serializer(obj):
    if isinstance(obj, datetime):
        # Format: DD-MM-YYYY HH:MMam/pm
        return obj.strftime("%d-%m-%Y %I:%M%p")
    elif isinstance(obj, date):
        # Format: DD-MM-YYYY
        return obj.strftime("%d-%m-%Y")
    else:
        return obj  # Return as is if not date/datetime
    
def custom_time_serializer(obj):
    if isinstance(obj, datetime):
        return obj.strftime("%I:%M%p")
    else:
        return obj  # Return as is if not datetime
