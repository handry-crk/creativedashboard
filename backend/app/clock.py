"""Semua waktu dalam WIB (Asia/Jakarta). `set_now` dipakai di test."""
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo

WIB = ZoneInfo("Asia/Jakarta")
_frozen: datetime | None = None


def set_now(dt: datetime | None) -> None:
    global _frozen
    _frozen = dt


def now() -> datetime:
    if _frozen is not None:
        return _frozen.astimezone(WIB) if _frozen.tzinfo else _frozen.replace(tzinfo=WIB)
    return datetime.now(WIB)


def today() -> date:
    return now().date()


def today_str() -> str:
    return today().isoformat()


def iso_utc() -> str:
    return now().astimezone(timezone.utc).isoformat()


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s[:10])


def add_days(d: date, n: int) -> date:
    return d + timedelta(days=n)
