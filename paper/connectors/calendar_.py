"""Section: today's calendar — gcalcli if configured, else macOS icalBuddy."""

from __future__ import annotations

import shutil
import subprocess

from ..models import Section, SectionItem
from .base import PaperContext, SectionConnector

_CAL_TIMEOUT = 10


def _run(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=_CAL_TIMEOUT)
    return result.stdout if result.returncode == 0 else ""


class CalendarConnector(SectionConnector):
    name = "calendar"
    title = "TODAY'S CALENDAR"
    timeout = 12.0

    def available(self) -> tuple[bool, str]:
        if shutil.which("gcalcli") or shutil.which("icalBuddy"):
            return True, ""
        return False, "install gcalcli (Google) or icalBuddy (macOS) for calendar"

    def fetch(self, ctx: PaperContext) -> Section:
        items: list[SectionItem] = []
        if shutil.which("gcalcli"):
            out = _run(["gcalcli", "agenda", "--nocolor", "--tsv", "today", "tomorrow"])
            for line in out.splitlines():
                parts = line.split("\t")
                # tsv: start_date start_time end_date end_time title...
                if len(parts) >= 5 and parts[4].strip():
                    items.append(SectionItem(title=parts[4].strip(), meta=parts[1].strip()))
        elif shutil.which("icalBuddy"):
            out = _run(["icalBuddy", "-nc", "-b", "- ", "eventsToday"])
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("- "):
                    items.append(SectionItem(title=line[2:]))
                elif line and items and not items[-1].meta:
                    items[-1].meta = line  # time line follows the title line
        return Section(name=self.name, title=self.title, items=items)
