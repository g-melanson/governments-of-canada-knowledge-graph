from __future__ import annotations

from datetime import datetime, timezone


def parse_iso_datetime(value: str | None, *, assume_utc: bool = True) -> datetime | None:
    """Parse publisher datetime string into a timezone-aware datetime."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None and assume_utc:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def staging_json_default(obj: object) -> str:
    """Serialize normalized row values to JSONL-compatible form."""
    if isinstance(obj, datetime):
        iso = obj.astimezone(timezone.utc).isoformat()
        return iso.replace("+00:00", "Z")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
