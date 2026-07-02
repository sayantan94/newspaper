import datetime as dt
import subprocess
from pathlib import Path

import pytest

from paper.config import PaperConfig
from paper.connectors.git import GitConnector, discover_repos, repo_status


def run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "ws" / "myproj"
    repo.mkdir(parents=True)
    run(repo, "git", "init", "-q")
    run(repo, "git", "config", "user.email", "dev@example.com")
    run(repo, "git", "config", "user.name", "Dev")
    (repo / "a.txt").write_text("hello")
    run(repo, "git", "add", "-A")
    run(repo, "git", "commit", "-qm", "add a.txt")
    return repo


def test_discover_repos_and_maxdepth(repo, tmp_path):
    deep = tmp_path / "ws" / "l1" / "l2" / "l3" / "deeprepo"
    deep.mkdir(parents=True)
    run(deep, "git", "init", "-q")
    found = discover_repos([tmp_path / "ws"])
    assert repo in found
    assert deep not in found  # depth 4 > maxdepth 3


def test_collect_commits_for_date(repo, tmp_path, monkeypatch):
    import paper.connectors.git as gitmod

    monkeypatch.setattr(gitmod, "_author_email", lambda: "dev@example.com")
    cfg = PaperConfig(workspace_roots=[str(tmp_path / "ws")])
    ev = GitConnector(config=cfg).collect(dt.date.today())
    assert len(ev) == 1
    assert ev[0].project == "myproj"
    assert ev[0].kind == "commit"
    assert "add a.txt" in ev[0].text

    assert GitConnector(config=cfg).collect(dt.date.today() - dt.timedelta(days=5)) == []


def test_repo_status(repo):
    dirty, unpushed, branch = repo_status(repo)
    assert dirty == 0
    assert unpushed == 0  # no upstream -> 0, not an error
    assert branch in ("main", "master")

    (repo / "b.txt").write_text("dirty")
    dirty, _, _ = repo_status(repo)
    assert dirty == 1
