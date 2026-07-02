"""Small shared helpers."""

from __future__ import annotations

import datetime as dt


def daypart(now: dt.datetime | None = None) -> str:
    """morning / afternoon / evening / late night — by local clock."""
    hour = (now or dt.datetime.now()).hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "late night"
