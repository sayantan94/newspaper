"""Work connector: OpenAI Codex CLI rollouts (~/.codex/sessions/YYYY/MM/DD/*.jsonl)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from ..models import Evidence
from .base import WorkConnector

_MAX_PROMPT = 500
_MAX_RESPONSE = 1000


def _texts(content, block_type: str) -> str:
    if not isinstance(content, list):
        return ""
    return "\n".join(
        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == block_type
    ).strip()


class CodexConnector(WorkConnector):
    name = "codex"

    def __init__(self, sessions_dir: Path | None = None):
        self.sessions_dir = Path(sessions_dir or Path.home() / ".codex" / "sessions")

    def available(self) -> tuple[bool, str]:
        if self.sessions_dir.is_dir():
            return True, ""
        return False, f"{self.sessions_dir} not found"

    def collect(self, date: dt.date) -> list[Evidence]:
        day_dir = self.sessions_dir / f"{date:%Y}" / f"{date:%m}" / f"{date:%d}"
        evidence: list[Evidence] = []
        if not day_dir.is_dir():
            return evidence
        for path in sorted(day_dir.glob("*.jsonl")):
            evidence.extend(self._parse_rollout(path))
        return evidence

    def _parse_rollout(self, path: Path) -> list[Evidence]:
        project = ""
        prompts: list[tuple[str, str]] = []
        last_response: tuple[str, str] | None = None
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            return []
        for line in lines:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = obj.get("timestamp", "")
            payload = obj.get("payload") or {}
            if obj.get("type") == "session_meta":
                cwd = payload.get("cwd")
                if cwd:
                    project = Path(cwd).name
                continue
            if obj.get("type") != "response_item" or payload.get("type") != "message":
                continue
            role = payload.get("role")
            if role == "user":
                text = _texts(payload.get("content"), "input_text")
                if text and not text.startswith("<"):
                    prompts.append((ts, text[:_MAX_PROMPT]))
            elif role == "assistant":
                text = _texts(payload.get("content"), "output_text")
                if text:
                    last_response = (ts, text[:_MAX_RESPONSE])
        if not project or not (prompts or last_response):
            return []
        out = [Evidence(project, self.name, "prompt", text, ts) for ts, text in prompts]
        if last_response:
            out.append(Evidence(project, self.name, "response", last_response[1], last_response[0]))
        return out
