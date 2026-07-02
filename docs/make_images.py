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
    headline="Midnight refactor pays off; orbit-cam finally spots the station",
    lead=(
        "You left off at 1am with orbit-cam's new tracking loop green and one "
        "glorious photo of the ISS streaking over the skyline. pantry-bot is "
        "still mid-fix on its rate-limit bug, and the streaming refactor you "
        "started is one test away from mergeable. Today writes itself."
    ),
    calendar=["9:30 AM  Standup", "12:30 PM  Lunch with Jeff", "6:00 PM  Rooftop BBQ"],
    inbox=[
        "PyCon — Your talk 'Newspapers for Robots' was accepted 🎉",
        "GitHub — [orbit-cam] nightly build failed on main",
    ],
    yesterday=[
        {
            "project": "orbit-cam",
            "story": "Rewrote the satellite-tracking loop to interpolate between TLE "
            "fixes — the Raspberry Pi caught its first clean ISS pass at 11:48pm.",
        },
        {
            "project": "pantry-bot",
            "story": "Taught the fridge-inventory bot to plan three dinners ahead; "
            "stopped mid-fix on the grocery API's rate-limit bug.",
        },
    ],
    open_loops=[
        "pantry-bot: rate-limit backoff is half-written — resume at retry_after",
        "orbit-cam: 2 uncommitted changes on main (the lens-cap detector)",
        "streaming refactor: one flaky test between you and the merge",
    ],
    tech_wire=[
        {
            "title": "Show HN: I built a terminal that prints on receipt paper",
            "url": "",
            "meta": "412 pts",
            "why": "your kind of beautiful nonsense",
        },
        {
            "title": "TLE accuracy and why your satellite is never where you think",
            "url": "",
            "meta": "268 pts",
            "why": "directly relevant to orbit-cam's new tracking loop",
        },
        {
            "title": "For first time, a cell built from scratch grows and divides",
            "url": "",
            "meta": "776 pts",
            "why": "top of the wire, pure research curiosity",
        },
    ],
    github=["orbit-cam — nightly build red", "review requested — pantry-bot: Add meal planner"],
    sports=[
        "Liberty hold off Aces 93–85; Collier back at practice for the red-hot Lynx.",
        "Tigers rout Yankees 9–3; Mets blank Blue Jays 3–0.",
        "Tonali picks Tottenham, citing De Zerbi.",
    ],
    actions=[
        "Finish pantry-bot's backoff and close the rate-limit loop",
        "Commit the lens-cap detector before it goes stale",
        "Fix the flaky test and merge the streaming refactor",
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
