"""Declarative base, PK/timestamp mixins, and a UTC-safe DateTime type.

Convention: all datetimes are UTC. SQLite stores naive UTC; ``UTCDateTime``
attaches/normalizes tzinfo so application code always sees aware UTC datetimes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, String, types
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from game_companion.utils import new_id, utcnow


class Base(DeclarativeBase):
    pass


class TolerantJSON(types.TypeDecorator):
    """JSON column that never raises on a corrupt stored value.

    SQLAlchemy's SQLite JSON type deserializes while building result rows, so a
    single malformed cell raises ``JSONDecodeError`` from the query itself and
    takes down the whole page -- page-level try/except cannot catch it. This
    type decodes defensively: unparseable text becomes an empty container of
    the column's shape (``[]`` for list columns, ``{}`` otherwise) so every
    ``.get(...)`` / ``for ... in ...`` call site keeps working.
    """

    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: object) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: object) -> Any:
        if value is None:
            return None
        if not isinstance(value, (str, bytes, bytearray)):
            return value
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            text = value.decode("utf-8", "replace") if isinstance(value, (bytes, bytearray)) else value
            # Give callers the container they would have had, so page code that
            # does d.get(...) or iterates keeps working instead of crashing.
            return [] if text.lstrip()[:1] in ("[",) else {}



class UTCDateTime(types.TypeDecorator):
    """DateTime stored as naive UTC, returned timezone-aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: object) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class PKMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow, nullable=False)
