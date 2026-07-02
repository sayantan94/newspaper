"""Tiny HTTP seam so section connectors are testable without a network."""

from __future__ import annotations

import json
import urllib.request

_TIMEOUT = 5
_UA = {"User-Agent": "paper-digest/0.1 (personal terminal newspaper)"}


def get_text(url: str) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_json(url: str) -> dict:
    return json.loads(get_text(url))
