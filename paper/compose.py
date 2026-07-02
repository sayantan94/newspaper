"""Compose an edition: ledger days + live sections → editorial → Edition."""

from __future__ import annotations

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor

from .config import PaperConfig
from .models import Edition, LedgerDay, Section, SectionItem
from .store import Store
from .util import daypart

_MAX_LEDGER_DAYS = 3

EDITORIAL_PROMPT = """\
You are the editor of a one-page personal newspaper for a software
engineer. It is {timeofday} — write for a reader sitting down right now
(morning coffee, afternoon check-in, evening wind-down, or a late-night
session), in tight, warm, newspaper-style copy, addressing him directly
("you left off...").

Return ONLY a JSON object shaped exactly like:
{{"headline": str, "lead": str, "yesterday": [{{"project": str, "story": str}}],
"open_loops": [str], "tech_wire": [{{"title": str, "url": str, "meta": str,
"why": str}}], "github": [str], "sports": [str], "inbox": [str],
"calendar": [str], "actions": [str]}}

Rules: headline = the day's most significant work thread, punchy.
lead = 2-4 sentences on where he left off and what today looks like.
yesterday = one 1-2 sentence story per project worked on. open_loops =
merge the scanner findings and ledger open threads, dedupe, most
important first, max 8. tech_wire = pick the 6 most relevant items for
his current work themes ({themes}); "why" = one clause on relevance.
github/calendar = terse lines, keep every calendar event. sports = up to
8 lines mixing the best headlines and results from the sports data,
sportswriter-terse. inbox = the unread emails worth his attention,
"sender — subject", skip obvious noise/newsletters. actions = top 3
concrete suggestions for today based on open loops and next steps.

WORK LEDGER (days since last edition):
{ledger_json}

OPEN LOOPS SCAN:
{openloops_json}

SECTION DATA (news/github/weather/calendar):
{sections_json}
"""


def _ledger_days_for_edition(store: Store, date: dt.date) -> list[LedgerDay]:
    """Most recent ledger days strictly before the edition date (newest last)."""
    days = []
    for iso in reversed(store.ledger_dates()):
        if iso >= date.isoformat():
            continue
        day = store.read_ledger(iso)
        if day and day.projects:
            days.append(day)
        if len(days) >= _MAX_LEDGER_DAYS:
            break
    return list(reversed(days))


def _fetch_sections(connectors, ctx) -> list[Section]:
    def run_one(connector) -> Section:
        ok, hint = connector.available()
        if not ok:
            return Section(name=connector.name, title=connector.title, notice=hint)
        try:
            return connector.fetch(ctx)
        except Exception as e:
            return Section(
                name=connector.name, title=connector.title, notice=f"unavailable: {e}"
            )

    sections: list[Section] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [(c, pool.submit(run_one, c)) for c in connectors]
        for connector, future in futures:
            try:
                sections.append(future.result(timeout=connector.timeout + 2))
            except Exception:
                sections.append(
                    Section(name=connector.name, title=connector.title, notice="timed out")
                )
    return sections


def _fallback_edition(date: dt.date, days: list[LedgerDay], sections: dict[str, Section]) -> Edition:
    yesterday = []
    open_loops = []
    for day in days:
        for p in day.projects:
            yesterday.append({"project": p.project, "story": p.summary})
    # the openloops section already carries where-left-off from the latest ledger
    loops_section = sections.get("openloops")
    if loops_section:
        open_loops.extend(i.title for i in loops_section.items)
    tech = sections.get("technews")
    github = sections.get("github")
    sports = sections.get("sports")
    gmail = sections.get("gmail")
    calendar = sections.get("calendar")
    return Edition(
        date=date.isoformat(),
        headline="Your day, uncut",
        lead="Editorial was unavailable — here is the raw feed.",
        yesterday=yesterday,
        open_loops=list(dict.fromkeys(open_loops))[:8],
        tech_wire=[
            {"title": i.title, "url": i.url, "meta": i.meta, "why": ""}
            for i in (tech.items if tech else [])[:6]
        ],
        github=[i.title for i in (github.items if github else [])[:8]],
        sports=[i.title for i in (sports.items if sports else [])[:8]],
        inbox=[
            (f"{i.meta} — {i.title}" if i.meta else i.title)
            for i in (gmail.items if gmail else [])[:8]
        ],
        calendar=[
            (f"{i.meta}  {i.title}".strip()) for i in (calendar.items if calendar else [])
        ],
        actions=[],
        fallback=True,
    )


def compose(
    date: dt.date,
    config: PaperConfig,
    store: Store,
    editor,
    section_conns: list | None = None,
    refresh: bool = False,
    verbose: bool = False,
) -> Edition:
    cached = store.read_edition(date.isoformat())
    if cached and not refresh:
        return cached

    if section_conns is None:
        from .connectors import section_connectors

        section_conns = section_connectors(config)

    days = _ledger_days_for_edition(store, date)
    latest = days[-1] if days else None
    themes = sorted(
        {p.project for d in days for p in d.projects}
        | {t for d in days for p in d.projects for t in p.tags}
    )

    from .connectors.base import PaperContext

    ctx = PaperContext(
        config=config, date=date, recent_themes=themes, latest_ledger=latest, store=store
    )
    sections = {s.name: s for s in _fetch_sections(section_conns, ctx)}

    openloops = sections.pop("openloops", Section(name="openloops", title="OPEN LOOPS"))
    weather = sections.pop("weather", None)
    weather_line = weather.items[0].title if weather and weather.items else ""

    prompt = EDITORIAL_PROMPT.format(
        timeofday=daypart(),
        themes=", ".join(themes) or "general software work",
        ledger_json=json.dumps([d.to_dict() for d in days], indent=1),
        openloops_json=json.dumps(openloops.to_dict(), indent=1),
        sections_json=json.dumps({k: s.to_dict() for k, s in sections.items()}, indent=1),
    )
    raw = editor.complete_json(prompt)
    if raw:
        edition = Edition.from_dict(raw)
        edition.date = date.isoformat()
        edition.fallback = False
    else:
        if verbose:
            print("  ! editorial unavailable, assembling raw edition")
        all_sections = dict(sections)
        all_sections["openloops"] = openloops
        edition = _fallback_edition(date, days, all_sections)

    edition.weather = weather_line
    notices = []
    if edition.fallback:
        notices.append("editorial desk unavailable (engine timeout/auth?) — retry with: paper --refresh")
    notices += [f"{s.title.lower() or s.name}: {s.notice}" for s in sections.values() if s.notice]
    if openloops.notice:
        notices.append(f"open loops: {openloops.notice}")
    if weather is not None and weather.notice:
        notices.append(f"weather: {weather.notice}")
    edition.notices = notices

    store.write_edition(edition)
    return edition
