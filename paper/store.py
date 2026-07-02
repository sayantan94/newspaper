"""On-disk state under $PAPER_HOME: ledger/, editions/, cache/."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .config import paper_home
from .models import Edition, LedgerDay


class Store:
    def __init__(self, root: Path | None = None):
        self.root = root or paper_home()
        for sub in ("ledger", "editions", "cache"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # --- ledger ---

    def ledger_path(self, date: str) -> Path:
        return self.root / "ledger" / f"{date}.json"

    def ledger_dates(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "ledger").glob("*.json"))

    def read_ledger(self, date: str) -> LedgerDay | None:
        path = self.ledger_path(date)
        if not path.exists():
            return None
        return LedgerDay.from_dict(json.loads(path.read_text()))

    def write_ledger(self, day: LedgerDay) -> Path:
        path = self.ledger_path(day.date)
        path.write_text(json.dumps(day.to_dict(), indent=2))
        return path

    # --- editions ---

    def edition_path(self, date: str) -> Path:
        return self.root / "editions" / f"{date}.json"

    def read_edition(self, date: str) -> Edition | None:
        path = self.edition_path(date)
        if not path.exists():
            return None
        return Edition.from_dict(json.loads(path.read_text()))

    def write_edition(self, ed: Edition) -> Path:
        path = self.edition_path(ed.date)
        path.write_text(json.dumps(ed.to_dict(), indent=2))
        return path

    # --- cache ---

    def _cache_path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
        return self.root / "cache" / f"{safe}.json"

    def cache_get(self, key: str, ttl_seconds: int) -> Any | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > ttl_seconds:
            return None
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def cache_put(self, key: str, value: Any) -> None:
        self._cache_path(key).write_text(json.dumps(value))
