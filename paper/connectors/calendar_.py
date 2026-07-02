"""Section: today's calendar, via your Google Calendar's secret iCal URL.

Connect it with `paper auth gmail` (it asks for the URL alongside the inbox),
or paste the URL into [calendar] ics_url. Get it from Google Calendar →
Settings → your calendar → "Secret address in iCal format". Zero OAuth,
no extra tools.
"""

from __future__ import annotations

import datetime as dt

from ..models import Section, SectionItem
from ..secrets import get_secret
from .base import PaperContext, SectionConnector
from . import _http

_WEEKDAY_CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]


def _unfold(text: str) -> list[str]:
    """ICS continuation lines start with whitespace; join them."""
    lines: list[str] = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw.rstrip("\r"))
    return lines


def _parse_dtstart(value: str) -> tuple[dt.date | None, str]:
    """'20260701T093000Z' / '20260701' → (date, 'HH:MM' or '')."""
    value = value.strip()
    try:
        if "T" in value:
            stamp = value.rstrip("Z")
            parsed = dt.datetime.strptime(stamp[:15], "%Y%m%dT%H%M%S")
            if value.endswith("Z"):
                parsed = parsed.replace(tzinfo=dt.timezone.utc).astimezone().replace(tzinfo=None)
            return parsed.date(), parsed.strftime("%-I:%M %p")
        return dt.datetime.strptime(value[:8], "%Y%m%d").date(), ""
    except ValueError:
        return None, ""


def ics_events_today(ics_text: str, today: dt.date) -> list[SectionItem]:
    """Best-effort: today's one-off events plus simple DAILY/WEEKLY recurrences."""
    items: list[SectionItem] = []
    summary, dtstart, rrule = "", "", ""
    in_event = False
    for line in _unfold(ics_text):
        if line == "BEGIN:VEVENT":
            in_event, summary, dtstart, rrule = True, "", "", ""
        elif line == "END:VEVENT" and in_event:
            in_event = False
            date, time_str = _parse_dtstart(dtstart)
            if date is None:
                continue
            hit = date == today
            if not hit and rrule and date <= today:
                daily = "FREQ=DAILY" in rrule
                weekly = "FREQ=WEEKLY" in rrule
                byday = _WEEKDAY_CODES[today.weekday()]
                in_byday = byday in rrule.split("BYDAY=")[-1].split(";")[0].split(",") if "BYDAY=" in rrule else False
                if daily or (weekly and in_byday):
                    hit = "UNTIL" not in rrule  # skip ended series (best effort)
            if hit and summary:
                items.append(SectionItem(title=summary, meta=time_str))
        elif in_event:
            if line.startswith("SUMMARY"):
                summary = line.split(":", 1)[-1].strip()
            elif line.startswith("DTSTART"):
                dtstart = line.split(":", 1)[-1]
            elif line.startswith("RRULE"):
                rrule = line.split(":", 1)[-1]
    items.sort(key=lambda i: i.meta)
    return items


def _ics_url(config) -> str:
    return config.calendar_ics_url or get_secret("gcal-ics", "default")


class CalendarConnector(SectionConnector):
    name = "calendar"
    title = "TODAY'S CALENDAR"
    timeout = 12.0

    def fetch(self, ctx: PaperContext) -> Section:
        url = _ics_url(ctx.config)
        if not url:
            return Section(
                name=self.name,
                title=self.title,
                notice="connect your Google Calendar: paper auth gmail",
            )
        items = ics_events_today(_http.get_text(url), ctx.date)
        if not items:
            items = [SectionItem(title="clear calendar — nothing scheduled")]
        return Section(name=self.name, title=self.title, items=items)
