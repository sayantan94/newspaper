import datetime as dt
import shutil
from pathlib import Path

from paper.connectors.codex import CodexConnector

FIXTURE = Path(__file__).parent / "fixtures" / "codex_rollout.jsonl"
TARGET = dt.date(2026, 6, 30)


def make_connector(tmp_path) -> CodexConnector:
    sessions = tmp_path / "sessions"
    day_dir = sessions / "2026" / "06" / "30"
    day_dir.mkdir(parents=True)
    shutil.copy(FIXTURE, day_dir / "rollout-2026-06-30T18-00-00-abc.jsonl")
    return CodexConnector(sessions_dir=sessions)


def test_collect_prompts_and_last_response(tmp_path):
    ev = make_connector(tmp_path).collect(TARGET)
    assert all(e.project == "mesh" and e.source == "codex" for e in ev)

    prompts = [e.text for e in ev if e.kind == "prompt"]
    assert prompts == ["refactor the mesh loader to stream chunks"]

    responses = [e.text for e in ev if e.kind == "response"]
    assert responses == ["Refactored the mesh loader to stream chunks; tests green."]


def test_no_dir_for_date(tmp_path):
    connector = make_connector(tmp_path)
    assert connector.collect(dt.date(2026, 7, 1)) == []


def test_missing_root_unavailable(tmp_path):
    connector = CodexConnector(sessions_dir=tmp_path / "nope")
    ok, hint = connector.available()
    assert not ok and "not found" in hint
    assert connector.collect(TARGET) == []
