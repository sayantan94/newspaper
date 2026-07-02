from rich.console import Console

from paper.models import Edition
from paper.render import render_edition


def sample_edition():
    return Edition(
        date="2026-07-01",
        headline="Parser lands; unicode fight continues",
        lead="You left off with red unicode tests in x-lens.",
        yesterday=[{"project": "x-lens", "story": "Built the parser."}],
        open_loops=["x-lens: unicode tests red"],
        tech_wire=[{"title": "Show HN: paper", "url": "", "meta": "412 pts", "why": "your beat"}],
        github=["livecv: CI failed"],
        calendar=["09:30  Standup"],
        actions=["Fix unicode tests"],
        weather="72°F partly cloudy · Seattle",
        notices=["calendar: install gcalcli"],
    )


def test_render_rich_contains_key_content():
    console = Console(record=True, width=96, force_terminal=True)
    render_edition(sample_edition(), console=console)
    text = console.export_text()
    assert "THE SAYANTAN TIMES" in text
    assert "Wednesday, July 1, 2026" in text
    assert "x-lens" in text
    assert "OPEN LOOPS" in text
    assert "Show HN: paper" in text
    assert "Fix unicode tests" in text
    assert "install gcalcli" in text


def test_render_plain_no_ansi(capsys):
    render_edition(sample_edition(), plain=True)
    out = capsys.readouterr().out
    assert "\x1b[" not in out
    assert "# Parser lands; unicode fight continues" in out
    assert "- x-lens: Built the parser." in out


def test_render_fallback_note():
    console = Console(record=True, width=96, force_terminal=True)
    ed = sample_edition()
    ed.fallback = True
    render_edition(ed, console=console)
    assert "editorial unavailable" in console.export_text()


def test_render_empty_edition_does_not_crash():
    console = Console(record=True, width=96, force_terminal=True)
    render_edition(Edition(date="2026-07-01"), console=console)
    assert "THE SAYANTAN TIMES" in console.export_text()
