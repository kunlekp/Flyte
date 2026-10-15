"""Small pure helpers (the original module-level helpers live here)."""

import math
import os
import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception

DATETIME_FORMAT = "%Y-%m-%d %H:%M"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_PASSPORT_RE = re.compile(r"^[A-Z0-9]{6,12}$")
_PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
_FLIGHT_NO_RE = re.compile(r"^[A-Z]{2}[0-9]{2,4}$")


def money(value):
    return f"₦{float(value):,.2f}"


def money_short(value):
    """₦1.2M / ₦85k style used on dashboards."""
    value = float(value)
    if abs(value) >= 1_000_000_000:
        return f"₦{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"₦{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"₦{value / 1_000:.0f}k"
    return f"₦{value:,.0f}"


def email_valid(email):
    return _EMAIL_RE.match(email or "") is not None


def passport_valid(passport):
    return _PASSPORT_RE.match(passport or "") is not None


def phone_valid(phone):
    return _PHONE_RE.match(phone or "") is not None


def flight_number_valid(number):
    return _FLIGHT_NO_RE.match(number or "") is not None


def app_timezone():
    """The airline's local time zone (servers usually run on UTC).

    Set APP_TIMEZONE to change it. Falls back to a fixed UTC+1 if the
    tz database is missing (Windows without the `tzdata` package)."""
    name = os.environ.get("APP_TIMEZONE", "Africa/Lagos")
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            pass
    return timezone(timedelta(hours=1), "WAT")


def now():
    """Single clock for the whole app: naive local airline time.
    Flight times are stored as local wall-clock strings, so 'now' must be too."""
    return datetime.now(app_timezone()).replace(tzinfo=None)


def utc_offset():
    """'+01:00' – appended to ISO strings handed to the browser."""
    offset = datetime.now(app_timezone()).utcoffset() or timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def timestamp(moment=None):
    return (moment or now()).strftime(TIMESTAMP_FORMAT)


def parse_datetime(value):
    """Parse 'YYYY-MM-DD HH:MM', HTML datetime-local ('T') or with seconds."""
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip().replace("T", " ")
    for fmt in (DATETIME_FORMAT, TIMESTAMP_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid date/time: {value!r} (use YYYY-MM-DD HH:MM)")


def format_datetime(moment):
    return moment.strftime(DATETIME_FORMAT)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two coordinates in kilometres."""
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))
