"""Secrets via the macOS Keychain (`security` CLI). Env-var fallback for
other platforms and tests: PAPER_<SERVICE>_SECRET."""

from __future__ import annotations

import os
import subprocess

_TIMEOUT = 10


def _env_key(service: str) -> str:
    return "PAPER_" + service.upper().replace("-", "_") + "_SECRET"


def get_secret(service: str, account: str) -> str:
    env = os.environ.get(_env_key(service))
    if env:
        return env
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", f"paper-{service}", "-a", account, "-w"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def set_secret(service: str, account: str, value: str) -> bool:
    try:
        result = subprocess.run(
            [
                "security",
                "add-generic-password",
                "-s",
                f"paper-{service}",
                "-a",
                account,
                "-w",
                value,
                "-U",  # update if it already exists
            ],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0
