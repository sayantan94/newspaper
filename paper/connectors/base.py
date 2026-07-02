"""Connector contracts. Every source of paper content implements one of these."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from ..config import PaperConfig
from ..models import Evidence, LedgerDay, Section


@dataclass
class PaperContext:
    """What section connectors get to work with."""

    config: PaperConfig
    date: dt.date  # edition date (today)
    recent_themes: list[str] = field(default_factory=list)
    latest_ledger: LedgerDay | None = None
    store: object | None = None  # Store, for connectors that want caching


class WorkConnector:
    """Produces evidence of work done on a given day (feeds the ledger)."""

    name: str = ""

    def available(self) -> tuple[bool, str]:
        return True, ""

    def collect(self, date: dt.date) -> list[Evidence]:
        raise NotImplementedError


class SectionConnector:
    """Produces a live section of the paper."""

    name: str = ""
    title: str = ""
    timeout: float = 5.0

    def available(self) -> tuple[bool, str]:
        return True, ""

    def fetch(self, ctx: PaperContext) -> Section:
        raise NotImplementedError
