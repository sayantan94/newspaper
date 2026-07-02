import datetime as dt
from pathlib import Path

from paper.config import PaperConfig
from paper.ingest import ingest_date, unprocessed_dates
from paper.models import Evidence, LedgerDay
from paper.store import Store

from conftest import FakeEditor

TODAY = dt.date(2026, 7, 1)


class StubWork:
    name = "stub"

    def __init__(self, evidence):
        self.evidence = evidence

    def available(self):
        return True, ""

    def collect(self, date):
        return self.evidence


def ev(project="x-lens", kind="prompt", text="do the thing", source="claude-code"):
    return Evidence(project, source, kind, text, "2026-06-30T18:00:00Z")


def test_unprocessed_dates_excludes_existing_and_today():
    store = Store()
    cfg = PaperConfig(lookback_days=3)
    store.write_ledger(LedgerDay(date="2026-06-29", projects=[]))
    dates = unprocessed_dates(store, cfg, TODAY)
    assert dates == [dt.date(2026, 6, 28), dt.date(2026, 6, 30)]


def test_distillation_writes_ledger():
    store = Store()
    cfg = PaperConfig()
    editor = FakeEditor(
        response={
            "date": "wrong-key",
            "projects": [
                {
                    "project": "x-lens",
                    "summary": "I built the thing.",
                    "where_left_off": "tests red",
                    "tags": ["feature"],
                }
            ],
        }
    )
    day = ingest_date(dt.date(2026, 6, 30), cfg, store, editor, connectors=[StubWork([ev()])])
    assert day.date == "2026-06-30"  # model's date ignored
    assert day.projects[0].summary == "I built the thing."
    assert day.projects[0].sources == ["claude-code"]  # backfilled from evidence
    assert store.read_ledger("2026-06-30") is not None
    assert "do the thing" in editor.prompts[0]


def test_empty_evidence_writes_empty_ledger():
    store = Store()
    editor = FakeEditor(response={"should": "not be called"})
    day = ingest_date(dt.date(2026, 6, 30), PaperConfig(), store, editor, connectors=[StubWork([])])
    assert day.projects == []
    assert editor.prompts == []
    assert store.read_ledger("2026-06-30").projects == []


def test_editor_failure_falls_back_to_raw():
    store = Store()
    editor = FakeEditor(response=None)
    evidence = [ev(kind="commit", text="commits: fix parser; add tests", source="git"), ev()]
    day = ingest_date(dt.date(2026, 6, 30), PaperConfig(), store, editor, connectors=[StubWork(evidence)])
    assert day.projects[0].summary.startswith("commits:")
    assert day.projects[0].sources == ["claude-code", "git"]


def test_markdown_mirror(tmp_path):
    store = Store()
    cfg = PaperConfig(markdown_mirror=str(tmp_path / "vault"))
    editor = FakeEditor(
        response={"projects": [{"project": "x-lens", "summary": "I did it.", "next_steps": ["ship"]}]}
    )
    ingest_date(dt.date(2026, 6, 30), cfg, store, editor, connectors=[StubWork([ev()])])
    mirror = (tmp_path / "vault" / "2026-06-30.md").read_text()
    assert "# 2026-06-30" in mirror
    assert "## x-lens" in mirror
    assert "**Next:** ship" in mirror
