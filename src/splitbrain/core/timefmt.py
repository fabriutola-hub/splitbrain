"""Unambiguous wall-clock stamps for briefs and decision records.

A timestamp without a zone is a guess. By default every stamp uses the machine's
local zone and prints its offset (``Nov 4 23:18 UTC-04:00``), which is the hour
people see in their chat app. ``SPLITBRAIN_TZ`` selects an IANA zone instead and
still wins when defined.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import SplitbrainError


def resolve_zone() -> tzinfo | None:
    """An explicit IANA zone, or None for the machine's own local zone."""
    name = os.environ.get("SPLITBRAIN_TZ", "").strip()
    if not name:
        return None
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise SplitbrainError(
            f"SPLITBRAIN_TZ={name!r} is not a valid IANA time zone "
            "(e.g. UTC, America/Caracas, Europe/Madrid)."
        ) from exc


def _localize(moment: datetime) -> datetime:
    zone = resolve_zone()
    return moment.astimezone() if zone is None else moment.astimezone(zone)


def _offset_label(moment: datetime) -> str:
    offset = moment.utcoffset()
    if offset is None:
        return moment.tzname() or "UTC"
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, rest = divmod(abs(minutes), 60)
    return f"UTC{sign}{hours:02d}:{rest:02d}"


def _format(moment: datetime) -> str:
    return (
        f"{moment.strftime('%b')} {moment.day} {moment.strftime('%H:%M')} {_offset_label(moment)}"
    )


def zone_label(zone: tzinfo | None = None) -> str:
    """Human-readable setting for a startup banner, never a guessed hour."""
    selected = zone or resolve_zone()
    if selected is None:
        return f"Local time ({_offset_label(datetime.now().astimezone())})"
    name = getattr(selected, "key", None) or str(selected)
    return f"{name} ({_offset_label(datetime.now(UTC).astimezone(selected))})"


def stamp(ts: int) -> str:
    """`Nov 4 23:18 UTC-04:00`, in local time. Never a bare hour."""
    moment = datetime.fromtimestamp(ts / 1000, UTC) if ts > 0 else datetime.now(UTC)
    return _format(_localize(moment))


def stamp_iso(value: str) -> str:
    """Render an ISO-8601 decision timestamp with the same local label."""
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SplitbrainError(f"Invalid decision timestamp {value!r}") from exc
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return _format(_localize(moment))
