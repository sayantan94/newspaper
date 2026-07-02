import json
import sys

import pytest

from paper.config import PaperConfig
from paper.llm import ClaudeEditor, CodexEditor, make_editor


def fake_cli(tmp_path, body: str) -> list:
    """A stand-in for the claude CLI: a python script reading stdin."""
    script = tmp_path / "fake_claude.py"
    script.write_text(body)
    return [sys.executable, str(script)]


def test_happy_path(tmp_path):
    cmd = fake_cli(
        tmp_path,
        "import json,sys; sys.stdin.read(); "
        "print(json.dumps({'result': json.dumps({'ok': 1})}))",
    )
    assert ClaudeEditor(command=cmd).complete_json("hi") == {"ok": 1}


def test_fenced_json_in_result(tmp_path):
    inner = "```json\\n{\\\"ok\\\": 2}\\n```"
    cmd = fake_cli(
        tmp_path,
        f"import json,sys; sys.stdin.read(); print(json.dumps({{'result': '{inner}'}}))",
    )
    assert ClaudeEditor(command=cmd).complete_json("hi") == {"ok": 2}


def test_garbage_then_valid_retries(tmp_path):
    marker = tmp_path / "called_once"
    cmd = fake_cli(
        tmp_path,
        f"""
import json, sys, pathlib
sys.stdin.read()
marker = pathlib.Path({str(marker)!r})
if marker.exists():
    print(json.dumps({{'result': json.dumps({{'ok': 3}})}}))
else:
    marker.touch()
    print("total garbage no json here")
""",
    )
    assert ClaudeEditor(command=cmd).complete_json("hi") == {"ok": 3}


def test_always_garbage_returns_none(tmp_path):
    cmd = fake_cli(tmp_path, "import sys; sys.stdin.read(); print('nope')")
    assert ClaudeEditor(command=cmd).complete_json("hi") is None


def test_nonzero_exit_returns_none(tmp_path):
    cmd = fake_cli(tmp_path, "import sys; sys.stdin.read(); sys.exit(1)")
    assert ClaudeEditor(command=cmd).complete_json("hi") is None


def test_timeout_returns_none(tmp_path):
    cmd = fake_cli(tmp_path, "import sys,time; time.sleep(5); print('late')")
    assert ClaudeEditor(command=cmd, timeout=1).complete_json("hi") is None


def test_codex_editor_writes_via_output_file(tmp_path):
    # fake `codex exec ... -o <file> -`: read stdin, write answer to the -o file
    cmd = fake_cli(
        tmp_path,
        """
import json, sys
args = sys.argv[1:]
assert args[0] == "exec" and "-o" in args and "read-only" in args
sys.stdin.read()
out = args[args.index("-o") + 1]
open(out, "w").write(json.dumps({"ok": "codex"}))
""",
    )
    assert CodexEditor(command=cmd).complete_json("hi") == {"ok": "codex"}


def test_make_editor_engine_selection():
    assert isinstance(make_editor(PaperConfig(llm_engine="claude")), ClaudeEditor)
    assert isinstance(make_editor(PaperConfig(llm_engine="codex")), CodexEditor)
    codex = make_editor(PaperConfig(llm_engine="codex"))
    assert codex.command == ["codex"]  # empty command falls back to engine name
    with pytest.raises(ValueError):
        make_editor(PaperConfig(llm_engine="gemini"))
