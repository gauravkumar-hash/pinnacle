
import re
from typing import Optional

def _looks_like_date(value: str | None) -> bool:
    if not value:
        return False
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", value):
        return True
    if re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", value):
        return True
    if re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", value, re.I):
        return True
    return False


def _looks_like_time(value: str | None) -> bool:
    if not value:
        return False
    if re.search(r"\b\d{1,2}:\d{2}\b", value):
        return True
    if re.search(r"\b(?:am|pm)\b", value, re.I):
        return True
    if re.search(r"\b(?:morning|afternoon|evening|noon|night|midday|midnight)\b", value, re.I):
        return True
    return False


def normalize_preferred_date_time(preferred_days: str | None, preferred_time: str | None) -> tuple[str, str]:
    days = (preferred_days or "").strip()
    time = (preferred_time or "").strip()

    # 1. If we have a clear date and a clear time, match them regardless of order
    if _looks_like_date(time) and _looks_like_time(days):
        return time, days
    if _looks_like_date(days) and _looks_like_time(time):
        return days, time
    
    # 2. If only one is clearly identifiable, treat the other as the counterpart if it exists
    if _looks_like_time(time) and days:
        return days, time
    if _looks_like_time(days) and time:
        return time, days
    if _looks_like_date(days) and time:
        return days, time
    if _looks_like_date(time) and days:
        return time, days

    # 3. Fallback to what we have, using "Flexible" instead of "TBA" for better UX
    return days or "Flexible", time or "Flexible"
