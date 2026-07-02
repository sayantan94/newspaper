"""Section: GitHub — notifications and PRs awaiting my review, via the gh CLI."""

from __future__ import annotations

import json
import shutil
import subprocess

from ..models import Section, SectionItem
from .base import PaperContext, SectionConnector

_GH_TIMEOUT = 10


def _gh(*args: str) -> str:
    result = subprocess.run(
        ["gh", *args], capture_output=True, text=True, timeout=_GH_TIMEOUT
    )
    return result.stdout if result.returncode == 0 else ""


class GitHubConnector(SectionConnector):
    name = "github"
    title = "GITHUB"
    timeout = 12.0

    def available(self) -> tuple[bool, str]:
        if shutil.which("gh"):
            return True, ""
        return False, "install the gh CLI for GitHub activity"

    def fetch(self, ctx: PaperContext) -> Section:
        items: list[SectionItem] = []
        out = _gh("api", "notifications")
        if out:
            try:
                for n in json.loads(out)[:10]:
                    repo = n.get("repository", {}).get("name", "?")
                    subject = n.get("subject", {})
                    items.append(
                        SectionItem(
                            title=f"{repo}: {subject.get('title', '')}",
                            meta=n.get("reason", ""),
                        )
                    )
            except json.JSONDecodeError:
                pass
        out = _gh(
            "search", "prs", "--review-requested=@me", "--state=open",
            "--json", "title,repository,url", "--limit", "10",
        )
        if out:
            try:
                for pr in json.loads(out):
                    repo = (pr.get("repository") or {}).get("name", "?")
                    items.append(
                        SectionItem(
                            title=f"review requested — {repo}: {pr.get('title', '')}",
                            url=pr.get("url", ""),
                        )
                    )
            except json.JSONDecodeError:
                pass
        return Section(name=self.name, title=self.title, items=items)
