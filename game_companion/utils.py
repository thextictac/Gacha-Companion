"""Small shared utilities: IDs and UTC time handling."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime


def new_id() -> str:
    """Compact random UUID (32 hex chars) used as primary key."""
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Timezone-aware UTC now. Stored naive-UTC in SQLite via UTCDateTime."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime (naive input is assumed UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def as_dict(value: object) -> dict:
    """Coerce a stored JSON blob to a dict.

    TolerantJSON returns unparseable cells verbatim, so a ``data`` column may be
    a str, list, int, or None. Callers treat these fields as mappings, so return
    an empty dict for anything that is not a mapping instead of raising.
    """
    return value if isinstance(value, dict) else {}


def as_list(value: object) -> list:
    """Coerce a stored JSON blob to a list.

    Same rationale as :func:`as_dict`: ``TolerantJSON`` returns corrupt cells
    verbatim, so a ``substats`` column may parse to an int or a string. Callers
    iterate these fields, so return an empty list for anything else.
    """
    return value if isinstance(value, list) else []


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return ensure_utc(dt).isoformat().replace("+00:00", "Z")
