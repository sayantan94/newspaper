"""Ingest: raw work evidence → one distilled ledger day (the journal)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from .config import PaperConfig
from .models import Evidence, LedgerDay, ProjectEntry
from .store import Store

_MAX_PROMPTS_PER_PROJECT = 12
_MAX_PROMPT_CHARS = 300
_MAX_RESPONSE_CHARS = 500

DISTILL_PROMPT = """\
You are distilling one day of a developer's work into a journal.
Date: {date}. Evidence below is grouped by project, from coding-agent
sessions (user prompts, final assistant notes) and git commits.

Return ONLY a JSON object, no prose, shaped exactly like:
{{"date": "{date}", "projects": [{{"project": str, "summary": str,
"where_left_off": str, "open_threads": [str], "next_steps": [str],
"tags": [str], "sources": [str]}}]}}

Rules: first person ("I built..."). One entry per project. summary = what
was accomplished and outcome, 1-3 sentences. where_left_off = the last
thing in flight when the day ended. tags from: feature, bugfix, refactor,
research, docs, review, deploy, design. Omit projects with no meaningful
work (pure chat, trivial questions).

EVIDENCE:
{evidence_block}
"""


def unprocessed_dates(store: Store, config: PaperConfig, today: dt.date) -> list[dt.date]:
    """Days before today, within lookback, that have no ledger file yet."""
    have = set(store.ledger_dates())
    out = []
    for delta in range(config.lookback_days, 0, -1):
        d = today - dt.timedelta(days=delta)
        if d.isoformat() not in have:
            out.append(d)
    return out


def _group_and_compact(evidence: list[Evidence]) -> dict[str, list[Evidence]]:
    by_project: dict[str, list[Evidence]] = {}
    for e in evidence:
        by_project.setdefault(e.project, []).append(e)
    for project, items in by_project.items():
        prompts = [e for e in items if e.kind == "prompt"][:_MAX_PROMPTS_PER_PROJECT]
        for e in prompts:
            e.text = e.text[:_MAX_PROMPT_CHARS]
        others = [e for e in items if e.kind != "prompt"]
        for e in others:
            if e.kind == "response":
                e.text = e.text[:_MAX_RESPONSE_CHARS]
        by_project[project] = prompts + others
    return by_project


def _evidence_block(by_project: dict[str, list[Evidence]]) -> str:
    parts = []
    for project, items in sorted(by_project.items()):
        lines = [f"### {project}"]
        for e in items:
            lines.append(f"- [{e.source}/{e.kind}] {e.text}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _fallback_day(date: dt.date, by_project: dict[str, list[Evidence]]) -> LedgerDay:
    """No LLM available: raw but useful entries straight from evidence."""
    projects = []
    for project, items in sorted(by_project.items()):
        commits = [e.text for e in items if e.kind == "commit"]
        prompts = [e.text for e in items if e.kind == "prompt"]
        summary = commits[0] if commits else (prompts[0] if prompts else "")
        if not summary:
            continue
        projects.append(
            ProjectEntry(
                project=project,
                summary=summary,
                sources=sorted({e.source for e in items}),
            )
        )
    return LedgerDay(date=date.isoformat(), projects=projects)


def _write_mirror(day: LedgerDay, mirror_dir: str) -> None:
    directory = Path(mirror_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    lines = [f"# {day.date}", ""]
    for p in day.projects:
        lines.append(f"## {p.project}")
        lines.append(p.summary)
        if p.where_left_off:
            lines.append(f"**Left off:** {p.where_left_off}")
        if p.next_steps:
            lines.append("**Next:** " + "; ".join(p.next_steps))
        if p.tags:
            lines.append(" ".join(f"#{t}" for t in p.tags))
        lines.append("")
    (directory / f"{day.date}.md").write_text("\n".join(lines))


def ingest_date(
    date: dt.date,
    config: PaperConfig,
    store: Store,
    editor,
    connectors: list | None = None,
    verbose: bool = False,
) -> LedgerDay:
    if connectors is None:
        from .connectors import work_connectors

        connectors = work_connectors(config)

    evidence: list[Evidence] = []
    for connector in connectors:
        ok, _ = connector.available()
        if not ok:
            continue
        try:
            evidence.extend(connector.collect(date))
        except Exception as e:
            if verbose:
                print(f"  ! {connector.name} failed: {e}")

    if not evidence:
        day = LedgerDay(date=date.isoformat(), projects=[])
        store.write_ledger(day)
        return day

    by_project = _group_and_compact(evidence)
    prompt = DISTILL_PROMPT.format(date=date.isoformat(), evidence_block=_evidence_block(by_project))
    raw = editor.complete_json(prompt)
    if raw:
        day = LedgerDay.from_dict(raw)
        day.date = date.isoformat()  # never trust the model with the key
        # keep sources honest if the model dropped them
        real_sources = {p: sorted({e.source for e in items}) for p, items in by_project.items()}
        for entry in day.projects:
            if not entry.sources:
                entry.sources = real_sources.get(entry.project, [])
    else:
        if verbose:
            print("  ! editor unavailable, writing fallback ledger")
        day = _fallback_day(date, by_project)

    store.write_ledger(day)
    if config.markdown_mirror and day.projects:
        _write_mirror(day, config.markdown_mirror)
    return day
