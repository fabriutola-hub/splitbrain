"""Unambiguous wall-clock stamps for briefs and decision records.

A timestamp without a zone is a guess: the M6 brief printed UTC hours with no
marker. `SPLITBRAIN_TZ` selects a zoneinfo zone (e.g. America/Caracas); without
it every stamp says UTC explicitly. A zone whose abbreviation is a bare numeric
offset (tzdata does that for America/Caracas) is expanded to UTC-04:00.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import SplitbrainError

_NUMERIC_OFFSET = re.compile(r"^[+-]\d{2}(?::?\d{2})?$")


def resolve_zone() -> tzinfo:
    name = os.environ.get("SPLITBRAIN_TZ", "").strip()
    if not name:
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise SplitbrainError(
            f"SPLITBRAIN_TZ={name!r} is not a valid IANA time zone "
            "(e.g. UTC, America/Caracas, Europe/Madrid)."
        ) from exc


def _abbreviation(moment: datetime) -> str:
    name = moment.tzname() or "UTC"
    if not _NUMERIC_OFFSET.match(name):
        return name
    digits = name.replace(":", "")
    return f"UTC{digits[:3]}:{digits[3:] or '00'}"


def zone_label(zone: tzinfo | None = None) -> str:
    """Human-readable setting for a startup banner, never a guessed hour."""
    selected = zone or resolve_zone()
    if selected is UTC:
        return "UTC (no SPLITBRAIN_TZ set)"
    name = getattr(selected, "key", None) or str(selected)
    return f"{name} ({_abbreviation(datetime.now(UTC).astimezone(selected))})"


def stamp(ts: int) -> str:
    """`Nov 4 12:49 UTC` or `Nov 4 08:49 UTC-04:00`. Never a bare hour."""
    zone = resolve_zone()
    moment = datetime.fromtimestamp(ts / 1000, UTC) if ts > 0 else datetime.now(UTC)
    local = moment.astimezone(zone)
    return f"{local.strftime('%b')} {local.day} {local.strftime('%H:%M')} {_abbreviation(local)}"
