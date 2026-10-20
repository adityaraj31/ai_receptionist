from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..models import Clinic


def clinic_timezone(clinic: Clinic) -> ZoneInfo:
    return ZoneInfo(clinic.timezone)


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must include a timezone")
    return value.astimezone(UTC)
