"""Render an Edition as a terminal broadsheet. Deterministic — no LLM here.

Design notes: real newspapers are monochrome ink on paper. So: no rainbow
colors — only weight (bold), voice (italic), and ink density (dim), with
rules and whitespace doing the layout work.
"""

from __future__ import annotations

import datetime as dt

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.padding import Padding
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .config import DEFAULT_MASTHEAD
from .models import Edition

_WIDTH = 100


def spaced_caps(s: str) -> str:
    """T H E   D A I L Y   Y O U — the letterspaced masthead look."""
    return " ".join(s.upper()).replace("   ", "     ")


def _pretty_date(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%A, %B %-d, %Y")
    except ValueError:
        return iso


def _roman(n: int) -> str:
    pairs = [(100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for value, numeral in pairs:
        while n >= value:
            out += numeral
            n -= value
    return out or "I"


def _kicker(title: str, byline: str = "") -> Group:
    head = Text()
    head.append(spaced_caps(title), style="bold")
    if byline:
        head.append(f"   — {byline}", style="dim italic")
    return Group(Rule(style="grey35", characters="─"), head, Text())


def render_edition(
    edition: Edition,
    plain: bool = False,
    console: Console | None = None,
    masthead: str = DEFAULT_MASTHEAD,
    issue: int = 1,
) -> None:
    if plain:
        _render_plain(edition, masthead)
        return
    console = console or Console()
    width = min(console.width or _WIDTH, _WIDTH)

    def rule(char: str, style: str = "white") -> None:
        console.print(Rule(style=style, characters=char))

    # ── Masthead ───────────────────────────────────────────────
    console.print()
    rule("═")
    console.print(Align.center(Text(spaced_caps(masthead), style="bold white")))
    dateline = Text(justify="center", style="grey62")
    dateline.append(f"Vol. {_roman(1 + (issue - 1) // 100)}, No. {issue} — {_pretty_date(edition.date)}")
    if edition.weather:
        dateline.append(f" — {edition.weather}")
    console.print(dateline)
    rule("═")
    ear = Table.grid(expand=True)
    ear.add_column(justify="left")
    ear.add_column(justify="right")
    ear.add_row(
        Text("THE MORNING EDITION", style="dim"),
        Text("your day, printed daily", style="dim italic"),
    )
    console.print(ear)
    console.print()

    # ── Front page ─────────────────────────────────────────────
    if edition.headline:
        console.print(Align.center(Text(edition.headline.upper(), style="bold")))
    if edition.lead:
        console.print(Padding(Text(edition.lead, style="italic", justify="center"), (0, 10)))
    if edition.fallback:
        console.print(Align.center(Text("· raw edition — the editorial desk is out ·", style="dim")))
    console.print()

    # ── Yesterday ──────────────────────────────────────────────
    if edition.yesterday:
        console.print(_kicker("Yesterday", "where you left off"))
        for entry in edition.yesterday:
            story = Text("  ")
            story.append(entry.get("project", "").upper(), style="bold")
            story.append("  —  ", style="dim")
            story.append(entry.get("story", ""))
            console.print(story)
        console.print()

    # ── Open loops ─────────────────────────────────────────────
    if edition.open_loops:
        console.print(_kicker("Open Loops", "the unfinished business desk"))
        for loop in edition.open_loops:
            line = Text("  ◦ ", style="dim")
            line.append(loop)
            console.print(line)
        console.print()

    # ── The wire: two columns ──────────────────────────────────
    if edition.tech_wire or edition.github:
        columns = Table(
            box=box.MINIMAL,
            expand=True,
            show_header=True,
            header_style="bold",
            border_style="grey35",
            padding=(0, 2),
        )
        columns.add_column(spaced_caps("Tech Wire"), ratio=3)
        columns.add_column(spaced_caps("GitHub"), ratio=2)
        left = []
        for item in edition.tech_wire:
            t = Text()
            t.append("• ", style="dim")
            t.append(item.get("title", ""))
            meta_bits = [b for b in (item.get("meta", ""), item.get("why", "")) if b]
            if meta_bits:
                t.append(f"\n  {' — '.join(meta_bits)}", style="dim italic")
            left.append(t)
        right = [Text(f"• {line}") for line in edition.github] or [Text("all quiet on the remote front", style="dim italic")]
        columns.add_row(Group(*left), Group(*right))
        console.print(columns)
        console.print()

    # ── Today ──────────────────────────────────────────────────
    if edition.calendar or edition.actions:
        console.print(_kicker("Today", "the forward desk"))
        for line in edition.calendar:
            console.print(Text(f"  {line}"))
        if edition.calendar and edition.actions:
            console.print()
        for i, action in enumerate(edition.actions, 1):
            item = Text(f"  {i}. ", style="dim")
            item.append(action, style="bold")
            console.print(item)
        console.print()

    # ── Colophon ───────────────────────────────────────────────
    if edition.notices:
        console.print(Text("  " + "  ·  ".join(edition.notices), style="dim"))
    rule("═")
    console.print(Align.center(Text(spaced_caps("end of edition"), style="dim")))
    console.print()


def _render_plain(edition: Edition, masthead: str) -> None:
    out = [f"{masthead} — {_pretty_date(edition.date)}"]
    if edition.weather:
        out.append(edition.weather)
    out.append("")
    if edition.headline:
        out.append(f"# {edition.headline}")
    if edition.lead:
        out.append(edition.lead)
    if edition.fallback:
        out.append("(raw edition — editorial unavailable)")
    if edition.yesterday:
        out.append("\n## Yesterday")
        out += [f"- {e.get('project', '')}: {e.get('story', '')}" for e in edition.yesterday]
    if edition.open_loops:
        out.append("\n## Open loops")
        out += [f"- {line}" for line in edition.open_loops]
    if edition.tech_wire:
        out.append("\n## Tech wire")
        out += [f"- {i.get('title', '')} ({i.get('meta', '')})" for i in edition.tech_wire]
    if edition.github:
        out.append("\n## GitHub")
        out += [f"- {line}" for line in edition.github]
    if edition.calendar or edition.actions:
        out.append("\n## Today")
        out += [f"- {line}" for line in edition.calendar]
        out += [f"{i}. {a}" for i, a in enumerate(edition.actions, 1)]
    out += [f"({n})" for n in edition.notices]
    print("\n".join(out))
