import datetime as dt
import json

import pytest

import paper.cli as cli
import paper.connectors as registry
from paper.config import config_path
from paper.models import Evidence, Section, SectionItem
from paper.store import Store

from conftest import FakeEditor

EDITORIAL = {
    "headline": "Parser lands",
    "lead": "You left off with red tests.",
    "yesterday": [{"project": "x-lens", "story": "Built the parser."}],
    "open_loops": ["x-lens: tests red"],
    "tech_wire": [{"title": "Show HN: paper", "url": "", "meta": "412 pts", "why": ""}],
    "github": [],
    "calendar": [],
    "actions": ["Fix the tests"],
}

LEDGER = {
    "projects": [
        {"project": "x-lens", "summary": "I built the parser.", "where_left_off": "tests red"}
    ]
}


class StubWork:
    name = "stub-work"

    def available(self):
        return True, ""

    def collect(self, date):
        if date == dt.date.today() - dt.timedelta(days=1):
            return [Evidence("x-lens", "stub-work", "prompt", "build parser", "")]
        return []


class StubSection:
    name = "stub-section"
    title = "STUB"
    timeout = 2.0

    def available(self):
        return True, ""

    def fetch(self, ctx):
        return Section(name=self.name, title=self.title, items=[SectionItem(title="hi")])


@pytest.fixture
def wired(paper_home_tmp, monkeypatch):
    """Config in place (skips first-run prompt), fake editor + connectors."""
    paper_home_tmp.mkdir(parents=True, exist_ok=True)
    config_path().write_text('masthead = "THE TEST TIMES"\nlookback_days = 2\n')
    editor = FakeEditor(responses=[LEDGER, EDITORIAL])
    monkeypatch.setattr(cli, "ClaudeEditor", lambda **kw: editor)
    monkeypatch.setattr(registry, "work_connectors", lambda cfg: [StubWork()])
    monkeypatch.setattr(registry, "section_connectors", lambda cfg: [StubSection()])
    return editor


def test_default_flow_end_to_end(wired, capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "THE TEST TIMES" in out
    assert "Parser lands" in out
    store = Store()
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    assert store.read_ledger(yesterday).projects[0].project == "x-lens"
    assert store.read_edition(dt.date.today().isoformat()).headline == "Parser lands"


def test_first_run_writes_default_config_non_tty(paper_home_tmp, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ClaudeEditor", lambda **kw: FakeEditor(response=None))
    monkeypatch.setattr(registry, "work_connectors", lambda cfg: [])
    monkeypatch.setattr(registry, "section_connectors", lambda cfg: [])
    assert not config_path().exists()
    cli.main(["config"])
    assert config_path().exists()
    assert 'masthead = "THE DAILY YOU"' in config_path().read_text()


def test_journal_command(wired, capsys):
    cli.main([])  # builds the ledger
    capsys.readouterr()
    yesterday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    assert cli.main(["journal", yesterday]) == 0
    out = capsys.readouterr().out
    assert "x-lens" in out and "built the parser" in out.lower()


def test_journal_missing_date(wired, capsys):
    assert cli.main(["journal", "1999-01-01"]) == 1


def test_connectors_command(wired, capsys):
    assert cli.main(["connectors"]) == 0
    out = capsys.readouterr().out
    assert "stub-work" in out and "stub-section" in out


def test_pdf_falls_back_to_html_without_chrome(wired, monkeypatch, capsys):
    cli.main([])
    capsys.readouterr()
    monkeypatch.setattr(cli, "_find_chrome", lambda: None)
    assert cli.main(["pdf"]) == 0
    out = capsys.readouterr().out
    assert ".html" in out
    html_file = Store().root / "editions" / f"{dt.date.today().isoformat()}.html"
    content = html_file.read_text()
    assert "THE TEST TIMES" in content
    assert "Parser lands" in content


def test_unknown_command_errors(wired):
    with pytest.raises(SystemExit):
        cli.main(["frobnicate"])
