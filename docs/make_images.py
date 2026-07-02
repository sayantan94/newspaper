"""Regenerate the README hero images from a demo edition.

Usage: uv run python docs/make_images.py
Writes docs/edition.svg (terminal) and docs/print-edition.png (via Chrome).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from rich.console import Console

from paper.html import render_html
from paper.models import Edition
from paper.render import render_edition

DOCS = Path(__file__).parent

DEMO = Edition(
    date="2026-07-01",
    headline="Agentic prep marathon lands; jobs-cli stalls at LinkedIn's gate",
    lead=(
        "You left off mid-scope on jobs-cli, staring at the one constraint that "
        "decides the whole design: LinkedIn has no public jobs API. Behind you "
        "sits a finished monument — the CAD-4/CAD-5 prep set, committed to main. "
        "Today is two clean, high-leverage decisions before any code."
    ),
    calendar=["9:30 AM  Standup", "2:00 PM  1:1 with Sam"],
    inbox=[
        "GitHub — [sayantan94/newspaper] CI failed on main",
        "Jane Doe — Re: system design interview loop",
    ],
    yesterday=[
        {
            "project": "AgenticSysDesign",
            "story": "Shipped a massive interview-prep set — CAD-4 with five dimension "
            "deep-dives plus CAD-5 data-recovery — in one push to main (35 files).",
        },
        {
            "project": "jobs-cli",
            "story": "Opened a fresh project to automate a LinkedIn job search and hit "
            "the wall immediately: no official public jobs API.",
        },
    ],
    open_loops=[
        "jobs-cli: decide the data-access strategy — this choice shapes the design",
        "Culture interview (Round 6): prep is written but never rehearsed",
        "x-lens: 2 uncommitted changes on main",
    ],
    tech_wire=[
        {
            "title": "Ask HN: Who is hiring? (July 2026)",
            "url": "",
            "meta": "167 pts",
            "why": "fresh, structured hiring data to point jobs-cli at",
        },
        {
            "title": "ZCode — Harness for GLM-5.2",
            "url": "",
            "meta": "280 pts",
            "why": "an agent coding harness worth dissecting",
        },
        {
            "title": "For first time, a cell built from scratch grows and divides",
            "url": "",
            "meta": "776 pts",
            "why": "top of the wire, pure research curiosity",
        },
    ],
    github=["rowboat — v0.6.1 shipped", "review requested — toolbelt: Add skill"],
    sports=[
        "Liberty hold off Aces 93–85; Collier back at practice for the red-hot Lynx.",
        "Tigers rout Yankees 9–3; Mets blank Blue Jays 3–0.",
        "Tonali picks Tottenham, citing De Zerbi.",
    ],
    actions=[
        "Make the jobs-cli data-access call, then scaffold the project",
        "Rehearse the Round-6 culture answers out loud — time one full pass",
        "Commit the x-lens changes before they go stale",
    ],
    weather="72°F partly cloudy · Seattle",
)


def main() -> None:
    console = Console(record=True, width=100, force_terminal=True)
    render_edition(DEMO, console=console, masthead="THE DAILY YOU", issue=1)
    svg_path = DOCS / "edition.svg"
    svg_path.write_text(console.export_svg(title="paper"))
    print(f"wrote {svg_path}")

    html_path = DOCS / "_print.html"
    html_path.write_text(render_html(DEMO, masthead="THE DAILY YOU"))
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    png_path = DOCS / "print-edition.png"
    subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            f"--screenshot={png_path}",
            "--window-size=1000,905",
            "--hide-scrollbars",
            html_path.as_uri(),
        ],
        check=True,
        capture_output=True,
    )
    html_path.unlink()
    print(f"wrote {png_path}")


if __name__ == "__main__":
    main()
