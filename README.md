# paper

**Wake up. Pour coffee. Read yesterday's you.**

`paper` is a personal morning newspaper for your terminal. Every morning it
reads what you actually did yesterday — your Claude Code sessions, your Codex
sessions, your git commits — and an AI editorial desk writes you a front page:
where you left off, what's unfinished, what's happening in your world, and the
three things worth doing today.

No manual journaling. No "what was I doing again?" Just run `paper`.

```text
“All the code that's fit to print.”                          price: one coffee ☕
════════════════════════════════════════════════════════════════════════════════
                          T H E   D A I L Y   Y O U
Vol. I, No. 1 — Wednesday, July 1, 2026 — 59°F clear, 51–63°F, 1% rain · Seattle
════════════════════════════════════════════════════════════════════════════════
                      LATE CITY FINAL — THE MORNING EDITION

         AGENTIC PREP MARATHON LANDS; JOBS-CLI STALLS AT LINKEDIN'S GATE
      YOU left off mid-scope on jobs-cli, staring at the one constraint
      that decides the whole design: LinkedIn has no public jobs API and
      scraping breaks their ToS. Behind you sits a finished monument —
      the CAD-4/CAD-5 prep set, all committed to main. Today is two
      clean, high-leverage decisions before any code.
                                        ❦
────────────────────────────────────────────────────────────────────────────────
Y E S T E R D A Y   — where you left off

  AGENTICSYSDESIGN  —  You shipped a massive interview-prep set — CAD-4 with
five dimension deep-dives, plus CAD-5 data-recovery and SSE+Redis Streams —
landing it in one push to main (22dbb1e, 35 files, ~24.7k insertions).
  JOBS-CLI  —  You opened a fresh project to automate a LinkedIn job search
and hit the wall immediately: no official public jobs API.

────────────────────────────────────────────────────────────────────────────────
O P E N   L O O P S   — the unfinished business desk

  ◦ jobs-cli: decide the data-access strategy — this choice shapes the design
  ◦ Culture interview (Round 6): prep is written but never rehearsed
  ◦ Verify the draft in /tmp/cad5/part3.md actually merged — it may be orphaned

                                                ╷
   T E C H   W I R E                            │   G I T H U B
╶───────────────────────────────────────────────┼──────────────────────────────╴
   • Ask HN: Who is hiring? (July 2026)         │   • rowboat now at v0.6.1 —
       167 pts — a clean, structured job feed   │     eight releases since
       for jobs-cli — and live leads for your   │     v0.4.2
       own search                               │
```

That headline, that lead, those "why this matters to *you*" annotations on the
news — all written fresh each morning by the editorial desk, grounded in your
real work.

## How it works

```
   your raw activity                      the outside world
┌──────────────────────┐            ┌─────────────────────────────┐
│ Claude Code sessions │            │ Hacker News + your RSS      │
│ Codex sessions       │            │ GitHub notifications & PRs  │
│ git commits          │            │ today's calendar · weather  │
└──────────┬───────────┘            └──────────────┬──────────────┘
           │  work connectors                      │  section connectors
           ▼                                       │
   INGEST — one LLM call per day                   │
   distills evidence into a journal                │
   ~/.paper/ledger/YYYY-MM-DD.json                 │
           │                                       │
           └────────────────┬──────────────────────┘
                            ▼
              COMPOSE — the editorial desk
              one LLM call writes the edition
                            ▼
              RENDER — terminal broadsheet · PDF
```

Three properties worth knowing:

- **It builds a real journal.** Each day is distilled once into a permanent
  first-person record (`paper journal` to read it). Skip a weekend and Monday's
  paper covers everything since Friday.
- **Everything degrades gracefully.** No `gh`? That section hides with a hint.
  A feed is down? One dim line in the colophon. LLM unreachable? You get the
  raw-feed edition instead of an error.
- **Editions are cached.** The first `paper` of the day does the work; every
  rerun is instant.

## Install

You need Python ≥ 3.11, [uv](https://docs.astral.sh/uv/), and **either** the
[Claude Code CLI](https://claude.com/claude-code) or the
[Codex CLI](https://github.com/openai/codex) — `paper` drives them headlessly,
so there are **no API keys to manage**.

```bash
git clone <this repo> && cd newspaper
uv tool install --editable .
paper        # first run: names your paper, sets your city, backfills your journal
```

The first run backfills up to 14 days of journal (a minute or two, narrated).
Every morning after that is seconds.

Optional, for more sections: `gh` (GitHub), `gcalcli` or `icalBuddy`
(calendar), Google Chrome (PDF printing).

## The commands

| Command | What it does |
|---|---|
| `paper` | Today's edition — ingests anything unprocessed, composes, prints |
| `paper --refresh` | Refetch the world + rewrite the editorial |
| `paper 2026-06-30` | Re-read a past edition |
| `paper pdf` | Newspaper-styled **PDF print edition** (opens it, ready for real paper) |
| `paper journal` | Yesterday's journal entry (`paper journal 2026-06-28` for any day) |
| `paper ingest` | Update the journal only — cron-friendly |
| `paper connectors` | Every connector and its status |
| `paper config` | Show configuration |
| `paper --plain` | Markdown-ish plain text (automatic when piping) |

## Choosing your engine: Claude or Codex

The writing is done by whichever agent CLI you already use, in headless mode:

```toml
# ~/.paper/config.toml
[llm]
engine = "claude"   # claude -p --output-format json
# or
engine = "codex"    # codex exec -s read-only (sandboxed, read-only)

model = ""          # optional override, e.g. "claude-sonnet-5" or "o5"
```

Both engines read your work through the same connectors — Claude Code *and*
Codex sessions feed the journal regardless of which engine writes the paper.

## Configuration

`~/.paper/config.toml`, created interactively on first run
(see [config.example.toml](config.example.toml) for the annotated version):

```toml
masthead = "THE DAILY YOU"                    # your paper's name — make it yours
workspace_roots = ["~/Documents/Workspace"]   # where your repos live
lookback_days = 14                            # journal backfill horizon
markdown_mirror = ""                          # optional: Obsidian folder for journal copies

[connectors]
disabled = []                                 # e.g. ["calendar"]

[technews]
rss_feeds = []                                # your feeds join the tech wire
hn_count = 15

[weather]
location = "Seattle"
```

All state lives under `~/.paper/` (override with `$PAPER_HOME`):
`ledger/` (your journal), `editions/` (each day's paper + HTML + PDF),
`cache/`, `connectors/` (your plugins).

## Write your own connector

Every source is a plugin. Drop a file in `~/.paper/connectors/` — no core
changes, and a broken plugin can never take down the paper:

```python
# ~/.paper/connectors/stocks.py — a new section
from paper.connectors.base import SectionConnector
from paper.models import Section, SectionItem

class StocksConnector(SectionConnector):
    name = "stocks"
    title = "MARKETS"

    def fetch(self, ctx):
        # ctx.recent_themes tells you what the reader is working on
        return Section(name=self.name, title=self.title,
                       items=[SectionItem(title="NVDA +2.1%")])
```

To feed the **journal** from a new source (Cursor, shell history, Slack…),
subclass `WorkConnector` instead and implement `collect(date) -> list[Evidence]`.

## Automate the morning

The paper builds itself on demand, but you can pre-bake the slow part so the
first `paper` of the day is instant:

```cron
30 6 * * * PATH=$HOME/.local/bin:$PATH paper ingest
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| "editorial desk unavailable" in the colophon | The engine timed out or isn't authed — check `claude -p "hi"` (or `codex exec "hi"`), then `paper --refresh` |
| A section is missing | `paper connectors` shows why (usually a missing CLI + install hint) |
| Wrong city weather | Edit `[weather] location` in `~/.paper/config.toml` |
| Want a different name on the masthead | Edit `masthead`, or delete `~/.paper/config.toml` and run `paper` to be asked again |
| PDF says Chrome not found | Install Chrome/Chromium, or open the `.html` it printed and ⌘P |

## Development

```bash
uv sync && uv run pytest        # 58 tests, no network required
```

The design doc lives in [`docs/superpowers/specs/`](docs/superpowers/specs/),
the implementation plan in [`docs/superpowers/plans/`](docs/superpowers/plans/).
