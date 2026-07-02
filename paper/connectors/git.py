"""Work connector: git commits across workspace repos, plus status helpers
reused by the open-loops section."""

from __future__ import annotations

import datetime as dt
import functools
import subprocess
from pathlib import Path

from ..config import PaperConfig, load_config
from ..models import Evidence
from .base import WorkConnector

_GIT_TIMEOUT = 10


def _git(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def discover_repos(roots: list[Path], maxdepth: int = 3) -> list[Path]:
    """Directories containing .git under any root, up to maxdepth levels down."""
    repos: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        if (root / ".git").exists():
            repos.append(root)
        stack = [(root, 0)]
        while stack:
            current, depth = stack.pop()
            if depth >= maxdepth:
                continue
            try:
                children = [c for c in current.iterdir() if c.is_dir() and not c.name.startswith(".")]
            except OSError:
                continue
            for child in children:
                if (child / ".git").exists():
                    repos.append(child)
                else:
                    stack.append((child, depth + 1))
    return sorted(set(repos))


def repo_status(repo: Path) -> tuple[int, int, str]:
    """(dirty_file_count, unpushed_commit_count, current_branch)."""
    porcelain = _git(repo, "status", "--porcelain")
    dirty = len([line for line in porcelain.splitlines() if line.strip()])
    unpushed_out = _git(repo, "log", "@{u}..HEAD", "--oneline")
    unpushed = len(unpushed_out.splitlines()) if unpushed_out else 0
    branch = _git(repo, "branch", "--show-current")
    return dirty, unpushed, branch


def recently_active(repo: Path, days: int = 14) -> bool:
    head = repo / ".git" / "HEAD"
    try:
        age = dt.datetime.now().timestamp() - head.stat().st_mtime
    except OSError:
        return False
    return age <= days * 86400


@functools.lru_cache(maxsize=1)
def _author_email() -> str:
    try:
        result = subprocess.run(
            ["git", "config", "user.email"], capture_output=True, text=True, timeout=_GIT_TIMEOUT
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


class GitConnector(WorkConnector):
    name = "git"

    def __init__(self, config: PaperConfig | None = None):
        self.config = config or load_config()

    def collect(self, date: dt.date) -> list[Evidence]:
        since = dt.datetime.combine(date, dt.time.min).astimezone().isoformat()
        until = dt.datetime.combine(date + dt.timedelta(days=1), dt.time.min).astimezone().isoformat()
        author = _author_email()
        evidence: list[Evidence] = []
        for repo in discover_repos(self.config.roots):
            args = ["log", "--all", f"--since={since}", f"--until={until}", "--pretty=%h %aI %s"]
            if author:
                args.append(f"--author={author}")
            out = _git(repo, *args)
            if not out:
                continue
            subjects = [line.split(" ", 2)[2] for line in out.splitlines() if len(line.split(" ", 2)) == 3]
            if subjects:
                evidence.append(
                    Evidence(
                        project=repo.name,
                        source=self.name,
                        kind="commit",
                        text="commits: " + "; ".join(subjects),
                        timestamp=out.splitlines()[0].split(" ", 2)[1],
                    )
                )
        return evidence
