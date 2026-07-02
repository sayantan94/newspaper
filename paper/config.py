"""Configuration: ~/.paper/config.toml (or $PAPER_HOME/config.toml)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = """\
# paper — personal daily digest configuration

# Roots scanned for git repos (work evidence, open loops)
workspace_roots = ["~/Documents/Workspace"]

# How many days back ingest looks for unprocessed days
lookback_days = 14

# Optional: directory that receives a human-readable markdown copy of each
# day's journal (e.g. an Obsidian folder). Empty = disabled.
markdown_mirror = ""

[connectors]
# Connector names to disable, e.g. ["calendar", "weather"]
disabled = []

[technews]
# Extra RSS/Atom feeds for the tech wire
rss_feeds = []
hn_count = 15

[weather]
location = "Seattle"

[llm]
command = "claude"
model = ""
"""


def paper_home() -> Path:
    return Path(os.environ.get("PAPER_HOME", str(Path.home() / ".paper"))).expanduser()


@dataclass
class PaperConfig:
    workspace_roots: list[str] = field(
        default_factory=lambda: [str(Path.home() / "Documents" / "Workspace")]
    )
    lookback_days: int = 14
    markdown_mirror: str = ""
    disabled: list[str] = field(default_factory=list)
    rss_feeds: list[str] = field(default_factory=list)
    hn_count: int = 15
    location: str = "Seattle"
    llm_command: str = "claude"
    llm_model: str = ""

    @property
    def roots(self) -> list[Path]:
        return [Path(r).expanduser() for r in self.workspace_roots]


def config_path() -> Path:
    return paper_home() / "config.toml"


def load_config() -> PaperConfig:
    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG)
    data = tomllib.loads(path.read_text())

    cfg = PaperConfig()
    for key in ("workspace_roots", "lookback_days", "markdown_mirror"):
        if key in data:
            setattr(cfg, key, data[key])
    connectors = data.get("connectors", {})
    if "disabled" in connectors:
        cfg.disabled = connectors["disabled"]
    technews = data.get("technews", {})
    cfg.rss_feeds = technews.get("rss_feeds", cfg.rss_feeds)
    cfg.hn_count = technews.get("hn_count", cfg.hn_count)
    cfg.location = data.get("weather", {}).get("location", cfg.location)
    llm = data.get("llm", {})
    cfg.llm_command = llm.get("command", cfg.llm_command)
    cfg.llm_model = llm.get("model", cfg.llm_model)
    return cfg
