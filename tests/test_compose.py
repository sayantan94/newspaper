import datetime as dt

from paper.compose import compose
from paper.config import PaperConfig
from paper.models import LedgerDay, ProjectEntry, Section, SectionItem
from paper.store import Store

from conftest import FakeEditor

DATE = dt.date(2026, 7, 1)


class StubSection:
    def __init__(self, name, title, items=(), fail=False, unavailable=""):
        self.name, self.title = name, title
        self.timeout = 2.0
        self._items = list(items)
        self._fail = fail
        self._unavailable = unavailable
        self.fetch_count = 0

    def available(self):
        return (False, self._unavailable) if self._unavailable else (True, "")

    def fetch(self, ctx):
        self.fetch_count += 1
        if self._fail:
            raise OSError("boom")
        return Section(name=self.name, title=self.title, items=self._items)


def seed_ledger(store):
    store.write_ledger(
        LedgerDay(
            date="2026-06-30",
            projects=[
                ProjectEntry(
                    project="x-lens",
                    summary="I built the parser.",
                    where_left_off="unicode tests red",
                    next_steps=["fix tests"],
                    tags=["feature"],
                )
            ],
        )
    )


def stub_connectors():
    return [
        StubSection("openloops", "OPEN LOOPS", [SectionItem(title="x-lens: 2 uncommitted changes")]),
        StubSection("technews", "TECH WIRE", [SectionItem(title="Show HN: paper", meta="412 pts")]),
        StubSection("github", "GITHUB", [SectionItem(title="livecv: CI failed")]),
        StubSection("weather", "WEATHER", [SectionItem(title="72°F partly cloudy · Seattle")]),
        StubSection("calendar", "TODAY'S CALENDAR", unavailable="install gcalcli"),
    ]


EDITORIAL = {
    "headline": "Parser lands; unicode fight continues",
    "lead": "You left off with red unicode tests.",
    "yesterday": [{"project": "x-lens", "story": "Built the parser."}],
    "open_loops": ["x-lens: unicode tests red"],
    "tech_wire": [{"title": "Show HN: paper", "url": "", "meta": "412 pts", "why": "your project"}],
    "github": ["livecv: CI failed"],
    "calendar": [],
    "actions": ["Fix unicode tests"],
}


def test_compose_editorial_path():
    store = Store()
    seed_ledger(store)
    editor = FakeEditor(response=EDITORIAL)
    ed = compose(DATE, PaperConfig(), store, editor, section_conns=stub_connectors())
    assert ed.headline.startswith("Parser lands")
    assert ed.weather == "72°F partly cloudy · Seattle"
    assert ed.date == "2026-07-01"
    assert any("gcalcli" in n for n in ed.notices)
    assert store.read_edition("2026-07-01") is not None
    prompt = editor.prompts[0]
    assert "x-lens" in prompt and "2 uncommitted changes" in prompt


def test_compose_cache_hit_skips_fetch():
    store = Store()
    seed_ledger(store)
    conns = stub_connectors()
    editor = FakeEditor(response=EDITORIAL)
    compose(DATE, PaperConfig(), store, editor, section_conns=conns)
    fetches = sum(c.fetch_count for c in conns)
    ed2 = compose(DATE, PaperConfig(), store, editor, section_conns=conns)
    assert sum(c.fetch_count for c in conns) == fetches  # untouched
    assert ed2.headline == EDITORIAL["headline"]
    compose(DATE, PaperConfig(), store, editor, section_conns=conns, refresh=True)
    assert sum(c.fetch_count for c in conns) > fetches


def test_failing_connector_becomes_notice_not_crash():
    store = Store()
    seed_ledger(store)
    conns = stub_connectors() + [StubSection("stocks", "MARKETS", fail=True)]
    ed = compose(DATE, PaperConfig(), store, FakeEditor(response=EDITORIAL), section_conns=conns)
    assert any("markets" in n and "boom" in n for n in ed.notices)


def test_progress_events_fire():
    store = Store()
    seed_ledger(store)
    events = []
    compose(
        DATE,
        PaperConfig(),
        store,
        FakeEditor(response=EDITORIAL),
        section_conns=stub_connectors(),
        on_progress=lambda e, p: events.append(e),
    )
    assert events[0] == "gathering"
    assert events.count("section") == len(stub_connectors())
    assert events[-2:] == ["editorial", "editorial_done"]
    # cache hit emits a single "cached" event
    events.clear()
    compose(
        DATE,
        PaperConfig(),
        store,
        FakeEditor(response=EDITORIAL),
        section_conns=stub_connectors(),
        on_progress=lambda e, p: events.append(e),
    )
    assert events == ["cached"]


def test_fallback_edition_when_editor_dies():
    store = Store()
    seed_ledger(store)
    ed = compose(DATE, PaperConfig(), store, FakeEditor(response=None), section_conns=stub_connectors())
    assert ed.fallback is True
    assert ed.yesterday == [{"project": "x-lens", "story": "I built the parser."}]
    # open loops come from the openloops section (which carries ledger threads in real flow)
    assert any("2 uncommitted" in loop for loop in ed.open_loops)
    assert any("editorial desk unavailable" in n for n in ed.notices)
    assert ed.tech_wire[0]["title"] == "Show HN: paper"
    assert ed.weather == "72°F partly cloudy · Seattle"
