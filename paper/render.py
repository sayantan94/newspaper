"""Render an Edition as a terminal newspaper. Deterministic — no LLM here."""

from __future__ import annotations

import datetime as dt

from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .config import DEFAULT_MASTHEAD
from .models import Edition

_WIDTH = 96


def _pretty_date(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%A, %B %-d, %Y")
    except ValueError:
        return iso


def _section_rule(title: str) -> Rule:
    return Rule(Text(f" {title} ", style="bold"), style="grey50", characters="─")


def _bullets(lines: list[str], style: str = "") -> Group:
    return Group(*[Text(f"  • {line}", style=style) for line in lines])


def render_edition(
    edition: Edition,
    plain: bool = False,
    console: Console | None = None,
    masthead: str = DEFAULT_MASTHEAD,
) -> None:
    if plain:
        _render_plain(edition, masthead)
        return
    console = console or Console()
    width = min(console.width or _WIDTH, _WIDTH)

    # Masthead
    dateline = Text(justify="center", style="grey62")
    dateline.append(f"Vol. I · {_pretty_date(edition.date)}")
    if edition.weather:
        dateline.append(f" · {edition.weather}")
    head = Group(
        Align.center(Text(masthead, style="bold white")),
        dateline,
    )
    console.print(Panel(head, box=box.DOUBLE, width=width))

    # Lead story
    if edition.headline:
        console.print(Align.center(Text(edition.headline, style="bold underline"), width=width))
    if edition.lead:
        console.print(Padding(Text(edition.lead, style="italic"), (0, 4)))
    if edition.fallback:
        console.print(Text("  (raw edition — editorial unavailable)", style="dim"))
    console.print()

    # Yesterday
    if edition.yesterday:
        console.print(_section_rule("YESTERDAY — WHERE YOU LEFT OFF"))
        for entry in edition.yesterday:
            line = Text("  ")
            line.append(entry.get("project", ""), style="bold cyan")
            line.append(" — ")
            line.append(entry.get("story", ""))
            console.print(line)
        console.print()

    # Open loops
    if edition.open_loops:
        console.print(_section_rule("OPEN LOOPS"))
        console.print(_bullets(edition.open_loops, style="yellow"))
        console.print()

    # Two-column: tech wire | github
    if edition.tech_wire or edition.github:
        grid = Table.grid(expand=True, padding=(0, 2))
        grid.add_column(ratio=3)
        grid.add_column(ratio=2)
        left_lines = []
        for item in edition.tech_wire:
            t = Text()
            t.append("• ", style="grey50")
            t.append(item.get("title", ""))
            meta_bits = [b for b in (item.get("meta", ""), item.get("why", "")) if b]
            if meta_bits:
                t.append(f"\n   {' — '.join(meta_bits)}", style="dim")
            left_lines.append(t)
        right_lines = [Text(f"• {line}") for line in edition.github] or [
            Text("all quiet", style="dim")
        ]
        grid.add_row(
            Group(_section_rule("TECH WIRE"), *left_lines),
            Group(_section_rule("GITHUB"), *right_lines),
        )
        console.print(grid)
        console.print()

    # Today
    if edition.calendar or edition.actions:
        console.print(_section_rule("TODAY"))
        for line in edition.calendar:
            console.print(Text(f"  {line}", style="magenta"))
        for i, action in enumerate(edition.actions, 1):
            console.print(Text(f"  {i}. {action}", style="bold green"))
        console.print()

    # Footer
    for notice in edition.notices:
        console.print(Text(f"  · {notice}", style="dim"))
    console.print(Rule(Text(" end of edition ", style="dim"), style="grey30", characters="═"))


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
