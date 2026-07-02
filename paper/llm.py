"""LLM access via the Claude Code CLI in print mode (`claude -p`).

No API key handling: reuses the user's existing claude CLI auth.
"""

from __future__ import annotations

import json
import os
import subprocess


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


class ClaudeEditor:
    def __init__(self, command="claude", model: str = "", timeout: int = 120):
        self.command = command if isinstance(command, list) else [command]
        self.model = model
        self.timeout = timeout

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
        except subprocess.TimeoutExpired:
            return None
        except OSError:
            return None
        if result.returncode != 0:
            return None
        return result.stdout

    def complete_json(self, prompt: str) -> dict | None:
        """Run the prompt, expecting a JSON object back. One retry, then None."""
        for attempt in (0, 1):
            p = prompt if attempt == 0 else prompt + "\n\nReturn ONLY valid JSON."
            stdout = self._run(p)
            if stdout is None:
                return None  # process-level failure; retrying won't fix auth/timeout
            # claude -p --output-format json wraps the answer: {"result": "..."}
            wrapper = _extract_json(stdout)
            if wrapper and isinstance(wrapper.get("result"), str):
                obj = _extract_json(wrapper["result"])
            elif wrapper and isinstance(wrapper.get("result"), dict):
                obj = wrapper["result"]
            else:
                obj = wrapper
            if obj is not None:
                return obj
        return None
