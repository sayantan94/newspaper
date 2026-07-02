import datetime as dt
import shutil
from pathlib import Path

from paper.connectors.claude_code import ClaudeCodeConnector

FIXTURE = Path(__file__).parent / "fixtures" / "claude_session.jsonl"
# The fixture's in-day timestamps are 2026-06-30T18:00Z; compute that instant's
# local date so the test passes in any timezone.
TARGET = (
    dt.datetime.fromisoformat("2026-06-30T18:00:00+00:00").astimezone().date()
)


def make_connector(tmp_path) -> ClaudeCodeConnector:
    projects = tmp_path / "projects"
    session_dir = projects / "-Users-dev-Workspace-x-lens"
    session_dir.mkdir(parents=True)
    shutil.copy(FIXTURE, session_dir / "abc123.jsonl")
    return ClaudeCodeConnector(projects_dir=projects)


def test_collect_prompts_response_files(tmp_path):
    ev = make_connector(tmp_path).collect(TARGET)
    by_kind = {}
    for e in ev:
        by_kind.setdefault(e.kind, []).append(e)
        assert e.project == "x-lens"
        assert e.source == "claude-code"

    prompts = [e.text for e in by_kind["prompt"]]
    assert prompts == ["add a parser for lens files", "also fix the unicode bug"]

    assert len(by_kind["response"]) == 1
    assert "unicode bug" in by_kind["response"][0].text

    assert len(by_kind["files"]) == 1
    assert "parser.py" in by_kind["files"][0].text
    assert "test_parser.py" in by_kind["files"][0].text


def test_other_dates_excluded(tmp_path):
    connector = make_connector(tmp_path)
    ev = connector.collect(TARGET)
    assert not any("old prompt" in e.text for e in ev)
    # A day with no activity yields nothing
    assert connector.collect(TARGET + dt.timedelta(days=1)) == []


def test_missing_dir_unavailable(tmp_path):
    connector = ClaudeCodeConnector(projects_dir=tmp_path / "nope")
    ok, hint = connector.available()
    assert not ok and "not found" in hint
    assert connector.collect(TARGET) == []
