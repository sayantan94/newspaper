"""LLM access via headless coding-agent CLIs.

Two engines, no API keys — both reuse your existing CLI auth:
  - claude: `claude -p --output-format json` (default)
  - codex:  `codex exec -s read-only -o <file> -`
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

_DEFAULT_TIMEOUT = 240


def _clean_env() -> dict:
    """Child env without CLAUDE* vars so a nested claude CLI starts fresh."""
    return {k: v for k, v in os.environ.items() if not k.upper().startswith("CLAUDE")}


def _extract_json(text: str) -> dict | None:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


class _BaseEditor:
    def __init__(self, command=None, model: str = "", timeout: int = _DEFAULT_TIMEOUT):
        default = self.default_command  # subclass attr
        cmd = command or default
        self.command = cmd if isinstance(cmd, list) else [cmd]
        self.model = model
        self.timeout = timeout

    def _run(self, prompt: str) -> str | None:
        raise NotImplementedError

    def _parse(self, stdout: str) -> dict | None:
        return _extract_json(stdout)

    def complete_json(self, prompt: str) -> dict | None:
        """Run the prompt, expecting a JSON object back. One retry, then None."""
        for attempt in (0, 1):
            p = prompt if attempt == 0 else prompt + "\n\nReturn ONLY valid JSON."
            stdout = self._run(p)
            if stdout is None:
                return None  # process-level failure; retrying won't fix auth/timeout
            obj = self._parse(stdout)
            if obj is not None:
                return obj
        return None


class ClaudeEditor(_BaseEditor):
    default_command = "claude"

    def _run(self, prompt: str) -> str | None:
        argv = [*self.command, "-p", "--output-format", "json"]
        if self.model:
            argv += ["--model", self.model]
        try:
            result = subprocess.run(
                argv,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=_clean_env(),
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        return result.stdout if result.returncode == 0 else None

    def _parse(self, stdout: str) -> dict | None:
        # claude -p --output-format json wraps the answer: {"result": "..."}
        wrapper = _extract_json(stdout)
        if wrapper and isinstance(wrapper.get("result"), str):
            return _extract_json(wrapper["result"])
        if wrapper and isinstance(wrapper.get("result"), dict):
            return wrapper["result"]
        return wrapper


class CodexEditor(_BaseEditor):
    default_command = "codex"

    def _run(self, prompt: str) -> str | None:
        with tempfile.NamedTemporaryFile(mode="r", suffix=".txt", delete=False) as tmp:
            out_path = Path(tmp.name)
        argv = [
            *self.command,
            "exec",
            "--skip-git-repo-check",
            "-s",
            "read-only",
            "-o",
            str(out_path),
            "-",
        ]
        if self.model:
            argv += ["-m", self.model]
        try:
            result = subprocess.run(
                argv, input=prompt, capture_output=True, text=True, timeout=self.timeout
            )
            if result.returncode != 0:
                return None
            return out_path.read_text()
        except (subprocess.TimeoutExpired, OSError):
            return None
        finally:
            out_path.unlink(missing_ok=True)


_ENGINES = {"claude": ClaudeEditor, "codex": CodexEditor}


def make_editor(config) -> _BaseEditor:
    """Build the editor from config: [llm] engine / command / model."""
    engine = getattr(config, "llm_engine", "claude") or "claude"
    cls = _ENGINES.get(engine)
    if cls is None:
        raise ValueError(f"unknown llm engine {engine!r} (choose from: {', '.join(_ENGINES)})")
    return cls(command=config.llm_command or None, model=config.llm_model)
