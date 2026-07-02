# `paper` Daily Digest CLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. (This run: user said "just do it" — inline execution in-session.)

**Goal:** A `paper` CLI that builds a per-day work journal from raw Claude Code/Codex/git data and renders a full terminal newspaper (yesterday's work, open loops, tech news, GitHub, weather, calendar).

**Architecture:** Connector plugins feed two layers: work connectors → evidence → one `claude -p` distillation per day → `~/.paper/ledger/YYYY-MM-DD.json`; section connectors fetch live items in parallel; compose merges ledger + sections through one editorial `claude -p` call into a cached edition; a deterministic `rich` renderer draws the paper.

**Tech Stack:** Python 3.11, uv, rich (only runtime dep), stdlib urllib/xml/tomllib, subprocess for `claude`/`gh`/`git`, pytest.

## Global Constraints

- Python ≥ 3.11 (tomllib). Single runtime dependency: `rich`. Dev: `pytest`.
- All state under `$PAPER_HOME` (default `~/.paper`): `config.toml`, `ledger/`, `editions/`, `cache/`, `connectors/`. Tests always set `PAPER_HOME` to a tmpdir.
- Every connector isolated: hard timeout (sections: 5s network/subprocess), failure → `Section.notice` one-liner, never an exception out of the registry loop.
- LLM calls: `claude -p` via subprocess, 120s timeout, one retry on unparseable JSON, then heuristic fallback. `CLAUDE*`/`CLAUDECODE*` env vars stripped from the child env.
- Today is never distilled into the ledger; the paper covers yesterday + any older unprocessed days (lookback default 14).
- Dataclasses + `asdict` for all persisted JSON; tolerate unknown keys when loading.

## File Structure

```
pyproject.toml               # project + console script: paper = "paper.cli:main"
paper/
  __init__.py                # __version__
  config.py                  # PaperConfig, load_config(), paper_home(), default config writer
  models.py                  # Evidence, ProjectEntry, LedgerDay, SectionItem, Section, Edition
  store.py                   # Store: ledger/edition/cache IO under paper_home()
  llm.py                     # ClaudeEditor.complete_json(prompt) via `claude -p`
  ingest.py                  # unprocessed_dates(), ingest_date(): evidence → ledger (+md mirror)
  compose.py                 # run sections in parallel, editorial call, fallback edition
  render.py                  # render_edition(edition, plain=False) with rich
  cli.py                     # argparse: default flow, date, journal, ingest, connectors, config
  connectors/
    __init__.py              # registry: built-ins + ~/.paper/connectors/*.py discovery
    base.py                  # WorkConnector, SectionConnector, PaperContext
    claude_code.py           # work: ~/.claude/projects/*/*.jsonl
    codex.py                 # work: ~/.codex/sessions/Y/M/D/rollout-*.jsonl
    git.py                   # work: commits; + discover_repos(), repo_status() helpers
    openloops.py             # section: dirty/unpushed repos + ledger open threads
    technews.py              # section: HN Algolia + RSS (xml.etree)
    github.py                # section: gh api notifications + review requests
    weather.py               # section: Open-Meteo geocode+forecast
    calendar_.py             # section: gcalcli | icalBuddy | unavailable hint
tests/
  conftest.py                # PAPER_HOME tmpdir fixture, FakeEditor
  fixtures/claude_session.jsonl, codex_rollout.jsonl
  test_config.py test_models_store.py test_registry.py
  test_claude_code.py test_codex.py test_git.py
  test_llm.py test_ingest.py test_sections.py test_compose.py
  test_render.py test_cli.py
```

## Key Interfaces (single source of truth)

```python
# models.py
@dataclass
class Evidence:
    project: str      # short name, e.g. "x-lens"
    source: str       # connector name: "claude-code" | "codex" | "git" | ...
    kind: str         # "prompt" | "response" | "commit" | "files"
    text: str
    timestamp: str    # ISO 8601

@dataclass
class ProjectEntry:
    project: str
    summary: str
    where_left_off: str = ""
    open_threads: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

@dataclass
class LedgerDay:
    date: str                       # "YYYY-MM-DD"
    projects: list[ProjectEntry]
    @classmethod
    def from_dict(cls, d) -> "LedgerDay"   # tolerant of unknown keys

@dataclass
class SectionItem:
    title: str
    detail: str = ""
    url: str = ""
    meta: str = ""     # e.g. "412 pts", "9:30 AM"

@dataclass
class Section:
    name: str
    title: str
    items: list[SectionItem] = field(default_factory=list)
    notice: str = ""   # setup hint / failure note; rendered as one dim line

@dataclass
class Edition:
    date: str
    headline: str = ""
    lead: str = ""                                  # 2-4 sentence lead story
    yesterday: list[dict] = ...                     # [{"project","story"}]
    open_loops: list[str] = ...
    tech_wire: list[dict] = ...                     # [{"title","url","meta","why"}]
    github: list[str] = ...
    calendar: list[str] = ...
    actions: list[str] = ...                        # top-3 for today
    weather: str = ""
    notices: list[str] = ...
    fallback: bool = False                          # True when editorial LLM failed
    @classmethod
    def from_dict(cls, d) -> "Edition"

# connectors/base.py
@dataclass
class PaperContext:
    config: PaperConfig
    date: dt.date                    # edition date (today)
    recent_themes: list[str]         # project names + tags from latest ledgers
    latest_ledger: LedgerDay | None

class WorkConnector:
    name: str
    def available(self) -> tuple[bool, str]: return (True, "")
    def collect(self, date: dt.date) -> list[Evidence]: raise NotImplementedError

class SectionConnector:
    name: str
    title: str
    timeout: float = 5.0
    def available(self) -> tuple[bool, str]: return (True, "")
    def fetch(self, ctx: PaperContext) -> Section: raise NotImplementedError

# connectors/__init__.py
def work_connectors(config) -> list[WorkConnector]
def section_connectors(config) -> list[SectionConnector]   # order = paper order
# both: built-ins + user classes found in ~/.paper/connectors/*.py, minus config.disabled

# store.py
class Store:                      # root = paper_home()
    def ledger_dates(self) -> list[str]
    def read_ledger(self, date) -> LedgerDay | None
    def write_ledger(self, day: LedgerDay) -> Path
    def read_edition(self, date) -> Edition | None
    def write_edition(self, ed: Edition) -> Path
    def cache_get(self, key: str, ttl_seconds: int) -> Any | None
    def cache_put(self, key: str, value: Any) -> None

# llm.py
class ClaudeEditor:
    def __init__(self, command="claude", model="", timeout=120)
    def complete_json(self, prompt: str) -> dict | None   # None = gave up (after 1 retry)

# ingest.py
def unprocessed_dates(store, config, today: dt.date) -> list[dt.date]
def ingest_date(date, config, store, editor, connectors=None, verbose=False) -> LedgerDay

# compose.py
def compose(date, config, store, editor, refresh=False, verbose=False) -> Edition

# render.py
def render_edition(edition: Edition, plain: bool = False) -> None
```

## LLM Prompts (design content — verbatim)

**Ingest distillation** (one call per day; evidence compacted to ≤12 prompts×300 chars + last response×500 chars + commit subjects per project):

```
You are distilling one day of a developer's work into a journal.
Date: {date}. Evidence below is grouped by project, from coding-agent
sessions (user prompts, final assistant notes) and git commits.

Return ONLY a JSON object, no prose, shaped exactly like:
{"date": "{date}", "projects": [{"project": str, "summary": str,
"where_left_off": str, "open_threads": [str], "next_steps": [str],
"tags": [str], "sources": [str]}]}

Rules: first person ("I built..."). One entry per project. summary = what
was accomplished and outcome, 1-3 sentences. where_left_off = the last
thing in flight when the day ended. tags from: feature, bugfix, refactor,
research, docs, review, deploy, design. Omit projects with no meaningful
work (pure chat, trivial questions).

EVIDENCE:
{evidence_block}
```

**Editorial compose** (one call per edition):

```
You are the editor of a one-page personal morning newspaper for a
software engineer. Write tight, warm, newspaper-style copy. First
person is for his work ("you left off..." style is fine for addressing him).

Return ONLY a JSON object shaped exactly like:
{"headline": str, "lead": str, "yesterday": [{"project": str, "story": str}],
"open_loops": [str], "tech_wire": [{"title": str, "url": str, "meta": str,
"why": str}], "github": [str], "calendar": [str], "actions": [str]}

Rules: headline = the day's most significant work thread, punchy.
lead = 2-4 sentences on where he left off and what today looks like.
yesterday = one 1-2 sentence story per project worked on. open_loops =
merge the scanner findings and ledger open threads, dedupe, most
important first, max 8. tech_wire = pick the 6 most relevant items for
his current work themes ({themes}); "why" = one clause on relevance.
github/calendar = terse lines. actions = top 3 concrete suggestions
for today based on open loops and next steps.

WORK LEDGER (days since last edition):
{ledger_json}
OPEN LOOPS SCAN:
{openloops_json}
SECTION DATA (news/github/weather/calendar):
{sections_json}
```

## Parsing Rules (from real data inspection)

**claude-code:** files `~/.claude/projects/*/*.jsonl`; skip file if `mtime < start of target date` (fast prune). Per line: keep `type=="user"` where not `isSidechain`/`isMeta`, `message.content` string or blocks (`{"type":"text"}`) — skip texts starting with `<` (caveats/command tags/system-reminders); keep `type=="assistant"` text blocks (track last per session); collect `tool_use` blocks named Edit/Write/NotebookEdit → `input.file_path` set. Date filter on `timestamp` (UTC ISO → local date). Project = basename of `cwd` field.

**codex:** files `~/.codex/sessions/{Y}/{M}/{D}/rollout-*.jsonl` for target date. `session_meta.payload.cwd` → project. `response_item.payload` where `type=="message"`: role `user` → content `input_text` texts (skip starting with `<`), role `assistant` → `output_text` (keep last). Timestamps from line `timestamp`.

**git:** repos = dirs with `.git` under config roots, maxdepth 3. Commits: `git log --all --since/--until --author=<git config user.email> --pretty=%h %aI %s`. `repo_status(repo)` → `(dirty_count, unpushed_count, branch)` via `git status --porcelain`, `git log @{u}..HEAD --oneline` (0 on no upstream), `git branch --show-current`.

---

### Task 1: Scaffold + config
**Files:** `pyproject.toml`, `paper/__init__.py`, `paper/config.py`, `tests/conftest.py`, `tests/test_config.py`
**Produces:** `paper_home() -> Path` (respects `$PAPER_HOME`), `PaperConfig` (fields: `workspace_roots: list[str]`, `lookback_days=14`, `markdown_mirror=""`, `disabled: list[str]`, `rss_feeds: list[str]`, `hn_count=15`, `location="Seattle"`, `llm_command="claude"`, `llm_model=""`), `load_config() -> PaperConfig` — writes commented default `config.toml` on first call.
- [ ] Failing tests: default config file created on first load; `PAPER_HOME` respected; toml values override defaults; unknown keys ignored.
- [ ] Implement; `uv init`-style pyproject with `[project.scripts] paper = "paper.cli:main"`, deps `rich`, dev `pytest`.
- [ ] `uv run pytest` green → commit "feat: scaffold paper package with config layer".

### Task 2: Models + store
**Files:** `paper/models.py`, `paper/store.py`, `tests/test_models_store.py`
**Produces:** interfaces above. Store writes pretty JSON; `cache_get` checks file mtime vs TTL.
- [ ] Failing tests: ledger round-trip via `from_dict` (with an extra unknown key), edition round-trip, `ledger_dates()` sorted, cache TTL expiry (mtime manipulation via `os.utime`).
- [ ] Implement → green → commit "feat: models and on-disk store".

### Task 3: Connector base + registry
**Files:** `paper/connectors/base.py`, `paper/connectors/__init__.py`, `tests/test_registry.py`
**Produces:** `work_connectors()`, `section_connectors()`; user-plugin discovery: for each `~/.paper/connectors/*.py`, `importlib` load, register subclasses of the two bases; `config.disabled` filters by `name`; a plugin that raises on import → skipped with warning, never crashes.
- [ ] Failing tests: built-ins present and ordered (openloops, technews, github, weather, calendar); user plugin dropped into `$PAPER_HOME/connectors/` is discovered; disabled filter works; broken plugin skipped.
- [ ] Implement → green → commit "feat: connector registry with user plugin discovery".

### Task 4: claude-code work connector
**Files:** `paper/connectors/claude_code.py`, `tests/fixtures/claude_session.jsonl`, `tests/test_claude_code.py`
Fixture: hand-built 12-line file with user (incl. one sidechain, one `<command-name>` meta), assistant (thinking+text), tool_use Edit/Write, mixed dates. Connector takes `projects_dir` kwarg (default `~/.claude/projects`) for testability.
- [ ] Failing tests: only real prompts collected for target date; last assistant text captured; files-touched evidence built; other-date lines excluded; corrupt line skipped.
- [ ] Implement per Parsing Rules → green → commit "feat: claude-code session connector".

### Task 5: codex work connector
**Files:** `paper/connectors/codex.py`, `tests/fixtures/codex_rollout.jsonl`, `tests/test_codex.py` (mirror of Task 4; `sessions_dir` kwarg).
- [ ] Failing tests → implement → green → commit "feat: codex session connector".

### Task 6: git work connector + status helpers
**Files:** `paper/connectors/git.py`, `tests/test_git.py`
Test builds a temp repo (subprocess git init/config/commit), sets config root to tmpdir.
- [ ] Failing tests: `discover_repos` finds it (maxdepth honored); `collect(date)` returns commit evidence only for that date; `repo_status` reports dirty count after touching a file; no-upstream unpushed = 0.
- [ ] Implement → green → commit "feat: git connector and repo status helpers".

### Task 7: ClaudeEditor
**Files:** `paper/llm.py`, `tests/test_llm.py`
Subprocess runs `[command, "-p", "--output-format", "json"]` (+`--model` if set), prompt on stdin, env without `CLAUDE*` keys. Outer wrapper `{"result": "..."}` (fall back to raw stdout); extract first `{`→last `}` slice, `json.loads`; on failure retry once with `"\n\nReturn ONLY valid JSON."` appended; then None. Tests fake the CLI with a tiny `command=sys.executable -c ...` script (echoes canned wrapper; second variant emits garbage then valid to exercise retry).
- [ ] Failing tests: happy path; fenced-JSON result; garbage → retry → success; total failure → None; timeout → None.
- [ ] Implement → green → commit "feat: claude -p JSON editor wrapper".

### Task 8: Ingest
**Files:** `paper/ingest.py`, `tests/test_ingest.py`
`unprocessed_dates`: yesterday backward `lookback_days`, minus existing ledger dates. `ingest_date`: collect from given work connectors (default registry) → group/compact evidence (caps per Global Constraints) → no evidence: write empty LedgerDay; else editor prompt (verbatim above) → `LedgerDay.from_dict` → write; editor None → **heuristic fallback**: per project, summary = "; ".join(commit subjects) or first prompt, tags [], `fallback` noted in verbose only. Markdown mirror when `config.markdown_mirror`: `# {date}` + `## {project}` sections.
FakeEditor in conftest: records prompts, returns canned dict.
- [ ] Failing tests: unprocessed date math; distillation path writes ledger from FakeEditor; empty-evidence day writes empty ledger; fallback on editor None; mirror file written.
- [ ] Implement → green → commit "feat: ingest pipeline building the daily ledger".

### Task 9: Section connectors
**Files:** `paper/connectors/{openloops,technews,github,weather,calendar_}.py`, `tests/test_sections.py`
All network via a module-level `_get_json(url)`/`_get_text(url)` monkeypatchable seam; subprocess connectors check `shutil.which` in `available()`.
- **openloops**: repos with recent activity (HEAD mtime ≤14d) → `repo_status`; items "repo: N uncommitted changes on branch", "repo: N unpushed commits"; plus `ctx.latest_ledger` open_threads/where_left_off items.
- **technews**: HN `https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={hn_count}` → title/url/points; each RSS feed → `xml.etree` parse of `<item><title><link>` (and Atom `<entry>`), cap 10/feed; results cached 30 min via `store.cache` (cache handle passed via ctx.config? No — fetch functions take optional `cache`; compose passes Store).
- **github**: `gh api notifications` → "repo: title (reason)"; `gh search prs --review-requested=@me --state=open --json title,repository,url --limit 10`; unavailable if no `gh`.
- **weather**: Open-Meteo geocoding (name→lat/lon, cached forever) + forecast `current_weather=true&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max` → one-line summary string in `Section.items[0].title`; weather-code→text dict for common codes.
- **calendar_**: `gcalcli agenda --nocolor --tsv today tomorrow` if present, else `icalBuddy -nc eventsToday`, else `available()=(False, "install gcalcli or icalBuddy for calendar")`; parse lines → "9:30 AM  Standup".
- [ ] Failing tests per connector (monkeypatched seams; temp repo reuse from Task 6 helpers; fake `gh` via PATH shim script).
- [ ] Implement → green → commit "feat: live section connectors".

### Task 10: Compose
**Files:** `paper/compose.py`, `tests/test_compose.py`
Flow: cached edition and not refresh → return it. Else: ensure ingest ran (caller does); ledger days = dates after last edition date (cap 3, at least yesterday's if exists); build PaperContext (themes = project names+tags from those days); run section connectors in `ThreadPoolExecutor`, each wrapped: `available()` false → Section(notice=hint); exception/timeout (`future.result(timeout=connector.timeout+1)`) → Section(notice="…unavailable: <err>"). Editorial prompt (verbatim above) → Edition; editor None → fallback Edition assembled directly from ledger bullets + raw section items, `fallback=True`. Weather string lifted into `edition.weather`; connector notices → `edition.notices`. Write edition.
- [ ] Failing tests: FakeEditor path; cache hit skips fetch; failing connector → notice not crash; fallback edition content.
- [ ] Implement → green → commit "feat: compose editions with editorial layer".

### Task 11: Render
**Files:** `paper/render.py`, `tests/test_render.py`
Rich layout: masthead Panel "THE SAYANTAN TIMES" (config could override title later — use fixed for v1) + date/weather rule; lead (headline bold + lead text); "YESTERDAY" per-project bold-name stories; "OPEN LOOPS" bullets; `Columns`/`Table` two-col TECH WIRE | GITHUB (tech items: title, dim meta+why); "TODAY": calendar lines + numbered actions; dim notices footer. `plain=True` (or not `Console().is_terminal`): plain text sections. Fallback editions get a dim "(raw edition — editorial unavailable)" note.
- [ ] Failing test: capture output via `rich.console.Console(record=True)` injected — `render_edition(ed, console=...)`; assert masthead, a project name, an action present; plain mode contains no ANSI.
- [ ] Implement → green → commit "feat: terminal newspaper renderer".

### Task 12: CLI + wiring + README
**Files:** `paper/cli.py`, `tests/test_cli.py`, `README.md`
argparse: positional optional `date` (YYYY-MM-DD); flags `--refresh --plain --verbose --rebuild`; subcommands `journal [date]`, `ingest [--date --rebuild]`, `connectors`, `config`. Default flow: `load_config` → `Store` → `ClaudeEditor` → for d in `unprocessed_dates`: `ingest_date` (spinner via rich.status) → `compose(today)` → `render_edition`. `journal` prints ledger markdown-ish. `connectors` table: name, kind, available, hint. `config` prints path + contents. Exit 0 even with notices.
- [ ] Failing tests: `paper` end-to-end in tmp PAPER_HOME with FakeEditor injected via monkeypatched `ClaudeEditor` and all-fake connectors → renders edition, writes ledger+edition files; `journal` prints; `connectors` lists.
- [ ] Implement; README: what it is, install (`uv tool install --editable .`), commands, config reference, writing a custom connector (10-line example), cron note (`paper ingest`).
- [ ] Full `uv run pytest` green → commit "feat: paper CLI wiring + docs".

### Task 13: Live smoke + install
- [ ] `uv tool install --editable .`; run `paper connectors`, `paper ingest --verbose` (real data, real `claude -p`), `paper` — eyeball the edition; fix rough edges found (each fix its own commit).
- [ ] Commit any fixes; final commit "chore: v0.1.0".

## Self-Review Notes
- Spec coverage: connectors framework (T3), all 3 work sources (T4-6), journal+mirror (T8), all 5 sections (T9), editorial+fallback (T10), newspaper render (T11), full CLI surface (T12), first-run config (T1), error isolation (T3/T9/T10). Out-of-scope items untouched. ✓
- Types consistent with Key Interfaces block; all tasks reference it. ✓
- No TBDs; prompts and parsing rules written verbatim above. ✓
