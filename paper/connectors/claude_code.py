"""Work connector: Claude Code session transcripts (~/.claude/projects/*/*.jsonl)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from ..models import Evidence
from .base import WorkConnector

_EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
_MAX_PROMPT = 500
_MAX_RESPONSE = 1000
_MAX_FILES = 20


def _local_date(iso_ts: str) -> dt.date | None:
    try:
        return dt.datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone().date()
    except ValueError:
        return None


def _text_of(content) -> str:
    """message.content is a string or a list of blocks; join the text blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return ""


class ClaudeCodeConnector(WorkConnector):
    name = "claude-code"

    def __init__(self, projects_dir: Path | None = None):
        self.projects_dir = Path(projects_dir or Path.home() / ".claude" / "projects")

    def available(self) -> tuple[bool, str]:
        if self.projects_dir.is_dir():
            return True, ""
        return False, f"{self.projects_dir} not found"

    def collect(self, date: dt.date) -> list[Evidence]:
        evidence: list[Evidence] = []
        if not self.projects_dir.is_dir():
            return evidence
        day_start = dt.datetime.combine(date, dt.time.min).astimezone().timestamp()
        for path in self.projects_dir.glob("*/*.jsonl"):
            try:
                if path.stat().st_mtime < day_start:
                    continue  # file finished before this day began
            except OSError:
                continue
            evidence.extend(self._parse_session(path, date))
        return evidence

    def _parse_session(self, path: Path, date: dt.date) -> list[Evidence]:
        project = ""
        prompts: list[tuple[str, str]] = []  # (ts, text)
        last_response: tuple[str, str] | None = None
        files: list[str] = []
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            return []
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("isSidechain") or obj.get("isMeta"):
                continue
            ts = obj.get("timestamp", "")
            if _local_date(ts) != date:
                continue
            kind = obj.get("type")
            if kind not in ("user", "assistant"):
                continue
            if obj.get("cwd"):
                project = Path(obj["cwd"]).name
            message = obj.get("message") or {}
            if kind == "user":
                text = _text_of(message.get("content"))
                if text and not text.startswith("<"):
                    prompts.append((ts, text[:_MAX_PROMPT]))
            else:
                text = _text_of(message.get("content"))
                if text:
                    last_response = (ts, text[:_MAX_RESPONSE])
                for block in message.get("content") or []:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_use"
                        and block.get("name") in _EDIT_TOOLS
                    ):
                        fp = (block.get("input") or {}).get("file_path")
                        if fp and fp not in files:
                            files.append(fp)
        if not project:
            return []
        out = [Evidence(project, self.name, "prompt", text, ts) for ts, text in prompts]
        if last_response:
            out.append(Evidence(project, self.name, "response", last_response[1], last_response[0]))
        if files:
            out.append(
                Evidence(
                    project,
                    self.name,
                    "files",
                    "edited: " + ", ".join(files[:_MAX_FILES]),
                    prompts[-1][0] if prompts else "",
                )
            )
        return out
