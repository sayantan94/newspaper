# paper 🗞️

**Your personal morning newspaper, in the terminal.** `paper` catches you up on
where you left off: it reads your raw coding-agent sessions (Claude Code and
Codex), your git history, and the outside world — then writes and lays out a
one-page morning edition just for you.

```
╔══════════════════════════════════════════════════════════╗
║                      THE DAILY YOU                        ║
║        Vol. I · Wednesday, July 1, 2026 · 72°F clear      ║
╚══════════════════════════════════════════════════════════╝
                Parser lands; unicode fight continues
    You left off with red unicode tests in x-lens. Light calendar
    today — a good morning to close them out.

──────────────────── YESTERDAY — WHERE YOU LEFT OFF ────────────────────
  x-lens — Built the streaming parser; tests mostly green.

──────────────────────────── OPEN LOOPS ────────────────────────────────
  • x-lens: 2 uncommitted changes on main
  • newspaper: PR #14 awaiting your review

── TECH WIRE ───────────────────────────┬── GITHUB ──────────────────────
  • Show HN: terminal newspapers        │  • livecv: CI failed
     412 pts — your beat                │  • review requested — toolbelt
```

## What it does

- **Journals your work automatically.** No manual logging: it distills each
  day's Claude Code transcripts, Codex sessions, and git commits into a
  permanent per-day journal (`~/.paper/ledger/`), summarized by `claude -p`.
- **Surfaces open loops.** Uncommitted changes, unpushed branches, PRs waiting
  on you, and the threads you left dangling yesterday.
- **Brings the world in.** Hacker News + your RSS feeds (ranked by relevance to
  what you're building), GitHub notifications, today's calendar, the weather.
- **Prints beautifully.** `paper pdf` renders a real newspaper-styled print
  edition (via headless Chrome) you can put on actual paper.

## Install

Requires Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), and the
[Claude Code CLI](https://claude.com/claude-code) (used headlessly for the
writing — no API key needed).

```bash
cd newspaper
uv tool install --editable .
paper            # first run asks you to name your paper
```

Optional extras: `gh` (GitHub section), `gcalcli` or `icalBuddy` (calendar).
Missing tools just hide their section with a hint — nothing breaks.

## Daily use

```bash
paper                # this morning's edition (builds any missing journal days first)
paper --refresh      # refetch news/github/etc. and rewrite the editorial
paper --plain        # plain text (also automatic when piping)
paper 2026-06-30     # re-read a past edition
paper pdf            # print edition → ~/.paper/editions/<date>.pdf
paper journal        # yesterday's journal entry (or: paper journal 2026-06-28)
paper ingest         # just update the journal (cron-friendly)
paper connectors     # list connectors and their status
paper config         # show configuration
```

Editions are cached: the first `paper` of the day does the work, the rest are
instant.

## Configuration

`~/.paper/config.toml` (created on first run):

```toml
masthead = "THE DAILY YOU"                    # your paper's name
workspace_roots = ["~/Documents/Workspace"]   # where your repos live
lookback_days = 14                            # how far back ingest scans
markdown_mirror = ""                          # optional: Obsidian folder for journal copies

[connectors]
disabled = []                                 # e.g. ["calendar"]

[technews]
rss_feeds = []                                # extra feeds for the tech wire
hn_count = 15

[weather]
location = "Seattle"

[llm]
command = "claude"                            # any CLI supporting -p --output-format json
model = ""                                    # optional model override
```

Set `PAPER_HOME` to relocate all state (config, journal, editions, cache).

## Adding your own connector

Sources are plugins. Drop a file in `~/.paper/connectors/` and it appears in
your paper — no core changes:

```python
# ~/.paper/connectors/stocks.py
from paper.connectors.base import SectionConnector
from paper.models import Section, SectionItem

class StocksConnector(SectionConnector):
    name = "stocks"
    title = "MARKETS"

    def fetch(self, ctx):
        return Section(name=self.name, title=self.title,
                       items=[SectionItem(title="NVDA +2.1%")])
```

Subclass `WorkConnector` (with `collect(date) -> list[Evidence]`) instead to
feed the journal from a new source (Cursor, shell history, Slack…). Connectors
are isolated: if yours breaks, the paper still prints.

## Automating the morning

The journal builds itself whenever you run `paper`, but you can pre-bake it:

```cron
30 6 * * * PATH=$HOME/.local/bin:$PATH paper ingest
```

## How it works

```
work connectors (claude-code · codex · git)
        │ evidence
        ▼
ingest — one claude -p call per day ──► ~/.paper/ledger/YYYY-MM-DD.json   (your journal)
                                                  │
section connectors (openloops · technews · github · weather · calendar)
                                                  │
compose — one editorial claude -p call ──► ~/.paper/editions/YYYY-MM-DD.json
                                                  │
                                        render (terminal · pdf)
```

If the LLM is unavailable, every layer degrades to a raw-but-useful fallback.

## Development

```bash
uv sync
uv run pytest
```
