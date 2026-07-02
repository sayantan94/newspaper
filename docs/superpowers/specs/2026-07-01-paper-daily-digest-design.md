# `paper` — Personal Daily Digest CLI (Design)

**Date:** 2026-07-01
**Status:** Approved design, pending implementation plan

## Purpose

A morning "personal newspaper" for the terminal. Running `paper` catches Sayantan up on
where he left off: what he did yesterday across Claude Code, Codex, and git; what's
unfinished; plus external context (tech news, GitHub activity, calendar, weather).
The tool builds and owns its own journal from raw session data — it does not depend on
any agent skill having logged anything.

## Decisions (locked with user)

| Decision | Choice |
|---|---|
| Delivery | CLI on demand (`paper`), cron-able later via `paper ingest` |
| Content | Full paper: work catch-up + open loops + news + GitHub + calendar + weather/misc |
| LLM engine | `claude -p` (headless Claude Code CLI); no API key management |
| Stack | Python 3.11, managed with `uv`, installed via `uv tool install --editable .` |
| Reading UX | Newspaper-styled terminal output (rich): masthead, sections, columns |
| Architecture | Approach A: persistent per-day ledger + composed cached editions |
| Extensibility | All sources are **connectors** — pluggable, user can add new ones without touching core |

## Architecture

```
                      ┌────────────────────────────────────────┐
                      │              CONNECTORS                │
                      │                                        │
  work connectors     │  claude-code   codex    git            │  ← evidence for ledger
  (collect(date))     │                                        │
  section connectors  │  technews  github  weather  calendar   │  ← live items for paper
  (fetch())           │  + user connectors in ~/.paper/connectors/
                      └───────┬───────────────────┬────────────┘
                              │                   │
                     ┌────────▼────────┐          │
                     │  INGEST (daily) │          │
                     │  evidence → one │          │
                     │  claude -p call │          │
                     │  → ledger JSON  │          │
                     └────────┬────────┘          │
                              │                   │
                   ~/.paper/ledger/YYYY-MM-DD.json│
                              │                   │
                     ┌────────▼───────────────────▼───────┐
                     │  COMPOSE: ledger + open loops +    │
                     │  section items → one claude -p     │
                     │  editorial call → edition JSON     │
                     └────────────────┬───────────────────┘
                                      │
                        ~/.paper/editions/YYYY-MM-DD.json
                                      │
                            ┌─────────▼─────────┐
                            │  RENDER (rich)    │  deterministic, no LLM
                            └───────────────────┘
```

## Components

### 1. Connector framework

Every source is a connector. A connector is a Python class declaring:

- `name`, `kind` (`work` | `section` | both)
- Work connectors: `collect(date) -> list[Evidence]` — evidence of work done on a date.
  `Evidence` = `{project, source, kind, summary_text, detail, timestamp}` (e.g., a user
  prompt, a final assistant message, a commit, files touched).
- Section connectors: `fetch(context) -> Section` — items for a live section of the
  paper. `context` includes recent ledger themes so a connector can rank for relevance.
- `available() -> bool | reason` — self-check (e.g., `gh` not installed → section hides
  itself with a one-line setup hint).

Discovery: built-ins in `paper/connectors/`, user connectors auto-discovered from
`~/.paper/connectors/*.py`. Enabled/disabled and configured per-connector in
`~/.paper/config.toml`. Every connector runs with a hard timeout (default 5s for
sections) and independent failure — a broken connector yields a one-line notice in the
paper, never a crash.

**Built-in work connectors:**

- **claude-code** — parses `~/.claude/projects/*/*.jsonl` transcripts; extracts per
  session: project (from dir name), user prompts, final assistant message, files
  edited/written (tool calls), timestamps. Handles unknown line types tolerantly.
- **codex** — parses `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` +
  `session_index.jsonl` thread names; same evidence shape.
- **git** — discovers repos under configured roots (default
  `~/Documents/Workspace`, maxdepth 3); collects the user's commits for the date
  (author match on git config email), branch names, repos touched.

**Built-in section connectors:**

- **technews** — HN top stories via Algolia API + RSS feeds from config; passes items
  to editorial for relevance ranking against current work themes.
- **github** — via `gh api`: unread notifications, PRs awaiting my review, CI status on
  recently-active repos.
- **weather** — Open-Meteo (no key), location from config.
- **calendar** — today's events: `gcalcli` if installed, else macOS Calendar via
  `icalBuddy`/AppleScript, else `available() = false` with setup hint.
- **openloops** — special section connector that needs no network: uncommitted/untracked
  changes and unpushed branches per repo (reuses git discovery), merged with
  `where_left_off` threads from the latest ledger.

### 2. Ingest (the journal)

- `paper ingest [--date D] [--rebuild]` — for every day with evidence that has no
  ledger file yet (bounded lookback, default 14 days), gather evidence from all work
  connectors, compact it (truncate long texts, cap items per project), and make **one
  `claude -p` call per day** to distill it.
- Ledger schema `~/.paper/ledger/YYYY-MM-DD.json`:
  ```json
  {
    "date": "2026-06-30",
    "projects": [
      {
        "project": "x-lens",
        "summary": "first-person summary of what was done",
        "where_left_off": "the last thing in flight",
        "open_threads": ["..."],
        "next_steps": ["..."],
        "tags": ["feature"],
        "sources": ["claude-code", "git"]
      }
    ]
  }
  ```
- Idempotent: a day is distilled exactly once; `--rebuild` forces. Today is never
  distilled (still in progress) — the paper covers yesterday and any older unprocessed days.
- Optional markdown mirror: if `journal.markdown_mirror` is set to a directory (e.g.,
  the Obsidian vault), write a human-readable `YYYY-MM-DD.md` alongside the JSON.

### 3. Compose (editorial)

- Inputs: all unread-by-paper ledger days since the last edition (typically just
  yesterday; after a weekend, Fri–Sun), open-loops scan, all section connector results.
- One `claude -p` call with a strict JSON-out prompt returns the edition:
  headlines, lead story (the most significant work thread), per-section editorial copy,
  ranked tech-wire items, and "today: top 3 suggested actions".
- Cached at `~/.paper/editions/YYYY-MM-DD.json`. `paper` re-renders from cache
  instantly; `--refresh` refetches sections and rewrites editorial.
- Fallback: if `claude -p` fails or returns unparseable JSON (one retry), render the
  raw ledger bullets + section items without editorial polish, with a notice.

### 4. Render

Deterministic `rich`-based layout, no LLM: masthead ("THE SAYANTAN TIMES"), date +
weather bar, YESTERDAY (per-project stories), OPEN LOOPS, two-column TECH WIRE |
GITHUB, TODAY (calendar + top-3 actions), footer garnish. Degrades to plain text when
not a TTY (`--plain`).

### 5. CLI

```
paper                  # ingest anything unprocessed → compose → render today's edition
paper --refresh        # refetch sections + rewrite editorial for today
paper 2026-06-30       # render a past edition (compose if ledger exists but edition doesn't)
paper journal [date]   # print the ledger/journal for a date (default yesterday)
paper ingest [--rebuild] [--date D]
paper connectors       # list connectors, availability, last status
paper config           # open/print config; first run writes a commented default
```

First-run experience: `paper` with no config writes a default `~/.paper/config.toml`
(workspace roots guessed, weather location prompt), then proceeds.

## Error handling

- Per-connector timeouts and isolation; failures render as one-line notices.
- `claude -p` invocations: timeout (120s ingest / 120s compose), one retry on invalid
  JSON, then fallback rendering. Never block the paper on editorial.
- Missing tools (`gh`, `gcalcli`) → connector reports unavailable with a setup hint.
- Corrupt/unknown JSONL lines are skipped, counted, and reported in `--verbose`.

## Testing

- pytest; fixtures with real-shaped sample JSONL for claude-code and codex parsers.
- Git connector tested against a temp repo built in the test.
- Section connectors mocked at the HTTP/subprocess boundary.
- LLM behind an `Editor` interface with a fake in tests (returns canned edition JSON).
- Renderer smoke test: edition JSON fixture → renders without error, key strings present.

## Out of scope (v1)

- Scheduled generation/push delivery (cron/launchd wiring documented, not automated).
- Email/Slack/news-beyond-RSS integrations (add later as connectors).
- Web/HTML edition.
