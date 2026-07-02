"""The `paper` command."""

from __future__ import annotations

import argparse
import datetime as dt
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from .compose import compose
from .config import (
    DEFAULT_CONFIG_TEMPLATE,
    DEFAULT_MASTHEAD,
    config_path,
    load_config,
)
from .ingest import ingest_date, unprocessed_dates
from .llm import make_editor
from .render import render_edition
from .store import Store

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SUBCOMMANDS = ("journal", "ingest", "pdf", "connectors", "config")

_CHROME_CANDIDATES = [
    "google-chrome",
    "chromium",
    "chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def _first_run(console: Console) -> None:
    if config_path().exists():
        return
    masthead, location = DEFAULT_MASTHEAD, "Seattle"
    if sys.stdin.isatty() and sys.stdout.isatty():
        console.print("[bold]Welcome to paper — let's set up your morning edition.[/bold]")
        masthead = input(f"  Name your paper [{DEFAULT_MASTHEAD}]: ").strip() or DEFAULT_MASTHEAD
        location = input("  Weather location [Seattle]: ").strip() or "Seattle"
    text = DEFAULT_CONFIG_TEMPLATE.format(masthead=masthead).replace(
        'location = "Seattle"', f'location = "{location}"'
    )
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(text)
    console.print(f"[dim]Config written to {config_path()}[/dim]\n")


def _ingest_pending(config, store, editor, console: Console, verbose: bool) -> None:
    pending = unprocessed_dates(store, config, dt.date.today())
    if not pending:
        return
    if len(pending) > 1:
        console.print(
            f"[bold]Catching up:[/bold] journaling [bold]{len(pending)} day(s)[/bold] of your "
            "coding sessions and git history.\n"
            f"[dim]One-time backfill into {store.root / 'ledger'} — future mornings are fast.[/dim]\n"
        )
    for date in pending:
        with console.status(f"reading {date:%a, %b} {date.day} …"):
            day = ingest_date(date, config, store, editor, verbose=verbose)
        if day.projects:
            names = ", ".join(p.project for p in day.projects[:4])
            if len(day.projects) > 4:
                names += f" +{len(day.projects) - 4} more"
            console.print(f"  [green]✓[/green] {date:%a, %b} {date.day} — {names}")
        else:
            console.print(f"  [dim]· {date:%a, %b} {date.day} — quiet day[/dim]")
    console.print()


def _get_edition(date: dt.date, config, store, editor, console, refresh=False, verbose=False):
    with console.status("writing your edition (open loops · news · github · weather) …"):
        return compose(date, config, store, editor, refresh=refresh, verbose=verbose)


def _cmd_edition(args, config, store, editor, console) -> int:
    date = dt.date.fromisoformat(args.command) if args.command else dt.date.today()
    if not args.command:
        _ingest_pending(config, store, editor, console, args.verbose)
    edition = store.read_edition(date.isoformat())
    if edition is None or args.refresh or not args.command:
        edition = _get_edition(
            date, config, store, editor, console, refresh=args.refresh, verbose=args.verbose
        )
    issue = max(1, len(list((store.root / "editions").glob("*.json"))))
    render_edition(
        edition,
        plain=args.plain or not sys.stdout.isatty(),
        masthead=config.masthead,
        issue=issue,
    )
    return 0


def _cmd_journal(args, config, store, editor, console) -> int:
    date = args.arg or (dt.date.today() - dt.timedelta(days=1)).isoformat()
    day = store.read_ledger(date)
    if day is None:
        console.print(f"No journal for {date}. Run [bold]paper ingest[/bold] first.")
        return 1
    console.print(f"[bold]Journal — {date}[/bold]")
    if not day.projects:
        console.print("[dim]No meaningful work recorded.[/dim]")
    for p in day.projects:
        console.print(f"\n[bold cyan]{p.project}[/bold cyan] [dim]({', '.join(p.sources)})[/dim]")
        console.print(f"  {p.summary}")
        if p.where_left_off:
            console.print(f"  [yellow]left off:[/yellow] {p.where_left_off}")
        for step in p.next_steps:
            console.print(f"  [green]next:[/green] {step}")
    return 0


def _cmd_ingest(args, config, store, editor, console) -> int:
    if args.arg:
        date = dt.date.fromisoformat(args.arg)
        if args.rebuild:
            store.ledger_path(date.isoformat()).unlink(missing_ok=True)
        day = ingest_date(date, config, store, editor, verbose=args.verbose)
        console.print(f"journaled {date}: {len(day.projects)} project(s)")
    else:
        _ingest_pending(config, store, editor, console, args.verbose)
        console.print("journal up to date")
    return 0


def _find_chrome() -> str | None:
    for candidate in _CHROME_CANDIDATES:
        found = shutil.which(candidate) or (candidate if Path(candidate).exists() else None)
        if found:
            return found
    return None


def _cmd_pdf(args, config, store, editor, console) -> int:
    from .html import render_html

    date = dt.date.fromisoformat(args.arg) if args.arg else dt.date.today()
    edition = store.read_edition(date.isoformat())
    if edition is None:
        if date == dt.date.today():
            _ingest_pending(config, store, editor, console, args.verbose)
        edition = _get_edition(date, config, store, editor, console, verbose=args.verbose)
    html_path = store.root / "editions" / f"{edition.date}.html"
    html_path.write_text(render_html(edition, config.masthead))
    pdf_path = store.root / "editions" / f"{edition.date}.pdf"
    chrome = _find_chrome()
    if chrome:
        result = subprocess.run(
            [
                chrome,
                "--headless",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf_path}",
                html_path.as_uri(),
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode == 0 and pdf_path.exists():
            console.print(f"[bold green]✓[/bold green] print edition: {pdf_path}")
            if platform.system() == "Darwin" and sys.stdout.isatty():
                subprocess.run(["open", str(pdf_path)], check=False)
            return 0
    console.print(
        f"[yellow]Chrome not found for PDF conversion.[/yellow] "
        f"Open and print this instead: {html_path}"
    )
    return 0


def _cmd_connectors(args, config, store, editor, console) -> int:
    from .connectors import section_connectors, work_connectors

    console.print("[bold]Connectors[/bold]")
    for kind, connectors in (
        ("work", work_connectors(config)),
        ("section", section_connectors(config)),
    ):
        for c in connectors:
            ok, hint = c.available()
            status = "[green]ok[/green]" if ok else f"[yellow]off[/yellow] [dim]({hint})[/dim]"
            console.print(f"  {c.name:<12} {kind:<8} {status}")
    return 0


def _cmd_config(args, config, store, editor, console) -> int:
    console.print(f"[dim]{config_path()}[/dim]\n")
    console.print(config_path().read_text())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="paper",
        description="Your personal morning newspaper: yesterday's work, open loops, and the world.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="",
        help="a date (YYYY-MM-DD) for a past edition, or: journal | ingest | pdf | connectors | config",
    )
    parser.add_argument("arg", nargs="?", default="", help="date argument for subcommands")
    parser.add_argument("--refresh", action="store_true", help="refetch sections and rewrite editorial")
    parser.add_argument("--plain", action="store_true", help="plain text output")
    parser.add_argument("--rebuild", action="store_true", help="with ingest: re-distill the date")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    console = Console()
    if args.command and not _DATE_RE.match(args.command) and args.command not in _SUBCOMMANDS:
        parser.error(f"unknown command {args.command!r}")

    _first_run(console)
    config = load_config()
    store = Store()
    try:
        editor = make_editor(config)
    except ValueError as e:
        console.print(f"[red]config error:[/red] {e}")
        return 1

    handlers = {
        "journal": _cmd_journal,
        "ingest": _cmd_ingest,
        "pdf": _cmd_pdf,
        "connectors": _cmd_connectors,
        "config": _cmd_config,
    }
    handler = handlers.get(args.command, _cmd_edition)
    try:
        return handler(args, config, store, editor, console)
    except KeyboardInterrupt:
        console.print("\n[dim]stopped[/dim]")
        return 130


if __name__ == "__main__":
    sys.exit(main())
