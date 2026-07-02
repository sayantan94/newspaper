"""Print edition: render an Edition as a newspaper-styled HTML page (for PDF)."""

from __future__ import annotations

import datetime as dt
from html import escape

from .models import Edition

_STYLE = """
@page { size: letter; margin: 14mm; }
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; color: #1a1a1a;
       max-width: 7.5in; margin: 0 auto; padding: 24px; }
.masthead { text-align: center; border-top: 3px double #1a1a1a;
            border-bottom: 3px double #1a1a1a; padding: 10px 0; margin-bottom: 6px; }
.masthead h1 { font-size: 42px; margin: 0; letter-spacing: 4px;
               font-variant: small-caps; }
.dateline { text-align: center; font-size: 12px; color: #444;
            border-bottom: 1px solid #1a1a1a; padding: 4px 0 8px; margin-bottom: 18px; }
.headline { font-size: 28px; font-weight: bold; margin: 0 0 6px; line-height: 1.15; }
.lead { font-style: italic; font-size: 15px; color: #333; margin: 0 0 18px; }
.section { margin-bottom: 16px; break-inside: avoid; }
.section h2 { font-size: 13px; letter-spacing: 2px; text-transform: uppercase;
              border-bottom: 1px solid #999; padding-bottom: 3px; margin: 0 0 8px; }
.cols { column-count: 2; column-gap: 28px; column-rule: 1px solid #ddd; }
ul { margin: 0; padding-left: 18px; font-size: 13.5px; line-height: 1.45; }
li { margin-bottom: 5px; }
.story b { font-variant: small-caps; }
.meta { color: #666; font-size: 12px; }
ol.actions { font-size: 14px; font-weight: bold; }
.notices { margin-top: 20px; border-top: 1px solid #ccc; padding-top: 6px;
           font-size: 11px; color: #888; }
.endrule { text-align: center; margin-top: 18px; color: #888;
           border-top: 3px double #1a1a1a; padding-top: 6px; font-size: 11px;
           letter-spacing: 3px; font-variant: small-caps; }
"""


def _pretty_date(iso: str) -> str:
    try:
        return dt.date.fromisoformat(iso).strftime("%A, %B %-d, %Y")
    except ValueError:
        return iso


def _items(lines: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(line)}</li>" for line in lines) + "</ul>"


def render_html(edition: Edition, masthead: str) -> str:
    dateline = f"Vol. I · {escape(_pretty_date(edition.date))}"
    if edition.weather:
        dateline += f" · {escape(edition.weather)}"

    yesterday = "".join(
        f"<li class='story'><b>{escape(e.get('project', ''))}</b> — {escape(e.get('story', ''))}</li>"
        for e in edition.yesterday
    )
    wire = "".join(
        f"<li>{escape(i.get('title', ''))}"
        + (
            f" <span class='meta'>{escape(' — '.join(b for b in (i.get('meta', ''), i.get('why', '')) if b))}</span>"
            if (i.get("meta") or i.get("why"))
            else ""
        )
        + "</li>"
        for i in edition.tech_wire
    )
    actions = "".join(f"<li>{escape(a)}</li>" for a in edition.actions)
    notices = " · ".join(escape(n) for n in edition.notices)

    sections = []
    if yesterday:
        sections.append(
            f"<div class='section'><h2>Yesterday — where you left off</h2><ul>{yesterday}</ul></div>"
        )
    if edition.open_loops:
        sections.append(
            f"<div class='section'><h2>Open loops</h2>{_items(edition.open_loops)}</div>"
        )
    if edition.tech_wire:
        sections.append(f"<div class='section'><h2>Tech wire</h2><ul>{wire}</ul></div>")
    if edition.github:
        sections.append(f"<div class='section'><h2>GitHub</h2>{_items(edition.github)}</div>")
    if edition.calendar:
        sections.append(
            f"<div class='section'><h2>Today's calendar</h2>{_items(edition.calendar)}</div>"
        )
    if actions:
        sections.append(
            f"<div class='section'><h2>Today's top three</h2><ol class='actions'>{actions}</ol></div>"
        )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(masthead)} — {escape(edition.date)}</title>
<style>{_STYLE}</style></head>
<body>
<div class="masthead"><h1>{escape(masthead)}</h1></div>
<div class="dateline">{dateline}</div>
<div class="headline">{escape(edition.headline)}</div>
<p class="lead">{escape(edition.lead)}</p>
<div class="cols">
{''.join(sections)}
</div>
{f'<div class="notices">{notices}</div>' if notices else ''}
<div class="endrule">end of edition</div>
</body></html>
"""
