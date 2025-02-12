
import re
import datetime
import dateparser  # pip install dateparser

def calculate_default_reminder_time(text: str) -> datetime.datetime:
    """
    Given the text of the reminder request, calculate a default reminder datetime.
    For example, if the text contains '明天上午', default to tomorrow at 09:00.
    Otherwise, if a full datetime can be parsed, use that.
    As a fallback, return one hour from now.
    """
    now = datetime.datetime.now()
    if "明天上午" in text:
        tomorrow = now + datetime.timedelta(days=1)
        return datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0)
    elif "明天下午" in text:
        tomorrow = now + datetime.timedelta(days=1)
        return datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 15, 0)
    elif "明天晚上" in text:
        tomorrow = now + datetime.timedelta(days=1)
        return datetime.datetime(tomorrow.year, tomorrow.month, tomorrow.day, 20, 0)
    else:
        # Try to parse a full datetime from the text.
        dt = dateparser.parse(text, languages=['zh'])
        if dt and dt > now:
            return dt
    # Fallback: one hour from now.
    return now + datetime.timedelta(hours=1)

def extract_time_correction(user_text: str, base_date: datetime.datetime) -> datetime.datetime or None:
    """
    Attempts to extract a corrected time from the user_text.
    First, it tries to parse a full datetime.
    If that fails, it looks for a time pattern like '15:30' and applies it to the base_date.
    """
    dt = dateparser.parse(user_text, languages=['zh'])
    if dt and dt > datetime.datetime.now():
        return dt
    # Look for a time pattern (HH:MM)
    time_match = re.search(r'(\d{1,2}:\d{2})', user_text)
    if time_match:
        time_str = time_match.group(1)
        try:
            hour, minute = map(int, time_str.split(':'))
            # Use the date portion from base_date.
            corrected = base_date.replace(hour=hour, minute=minute)
            # If the corrected time is already past, assume the next day.
            if corrected < datetime.datetime.now():
                corrected += datetime.timedelta(days=1)
            return corrected
        except Exception:
            return None
    return None
