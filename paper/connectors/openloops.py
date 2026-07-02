"""Section: unfinished business — dirty repos, unpushed work, open ledger threads."""

from __future__ import annotations

from ..models import Section, SectionItem
from .base import PaperContext, SectionConnector
from .git import discover_repos, recently_active, repo_status


class OpenLoopsConnector(SectionConnector):
    name = "openloops"
    title = "OPEN LOOPS"
    timeout = 15.0  # local git, but many repos

    def fetch(self, ctx: PaperContext) -> Section:
        items: list[SectionItem] = []
        for repo in discover_repos(ctx.config.roots):
            if not recently_active(repo, days=14):
                continue
            dirty, unpushed, branch = repo_status(repo)
            where = f" on {branch}" if branch else ""
            if dirty:
                items.append(
                    SectionItem(title=f"{repo.name}: {dirty} uncommitted change(s){where}")
                )
            if unpushed:
                items.append(
                    SectionItem(title=f"{repo.name}: {unpushed} unpushed commit(s){where}")
                )
        if ctx.latest_ledger:
            for p in ctx.latest_ledger.projects:
                if p.where_left_off:
                    items.append(SectionItem(title=f"{p.project}: left off — {p.where_left_off}"))
                for thread in p.open_threads:
                    items.append(SectionItem(title=f"{p.project}: {thread}"))
        return Section(name=self.name, title=self.title, items=items)
