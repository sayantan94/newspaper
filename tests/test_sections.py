import datetime as dt
import json
import subprocess
from pathlib import Path

import pytest

from paper.config import PaperConfig
from paper.connectors.base import PaperContext
from paper.connectors.calendar_ import CalendarConnector
from paper.connectors.github import GitHubConnector
from paper.connectors.openloops import OpenLoopsConnector
from paper.connectors.technews import TechNewsConnector, parse_feed
from paper.connectors.weather import WeatherConnector
from paper.models import LedgerDay, ProjectEntry
from paper.store import Store


def ctx(cfg=None, ledger=None, store=None):
    return PaperContext(
        config=cfg or PaperConfig(),
        date=dt.date(2026, 7, 1),
        recent_themes=["x-lens"],
        latest_ledger=ledger,
        store=store,
    )


# --- openloops ---

def test_openloops_reports_dirty_and_ledger_threads(tmp_path):
    repo = tmp_path / "ws" / "myproj"
    repo.mkdir(parents=True)
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "d@e.com"],
        ["git", "config", "user.name", "D"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("x")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "b.txt").write_text("dirty")

    ledger = LedgerDay(
        date="2026-06-30",
        projects=[
            ProjectEntry(
                project="x-lens",
                summary="s",
                where_left_off="unicode tests red",
                open_threads=["finish docs"],
            )
        ],
    )
    section = OpenLoopsConnector().fetch(
        ctx(cfg=PaperConfig(workspace_roots=[str(tmp_path / "ws")]), ledger=ledger)
    )
    titles = [i.title for i in section.items]
    assert any("myproj: 1 uncommitted" in t for t in titles)
    assert any("left off — unicode tests red" in t for t in titles)
    assert any("x-lens: finish docs" in t for t in titles)


# --- technews ---

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Post One</title><link>https://a.example/1</link></item>
<item><title>Post Two</title><link>https://a.example/2</link></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom Post</title><link href="https://b.example/1"/></entry>
</feed>"""


def test_parse_feed_rss_and_atom():
    assert [i.title for i in parse_feed(RSS)] == ["Post One", "Post Two"]
    atom = parse_feed(ATOM)
    assert atom[0].title == "Atom Post"
    assert atom[0].url == "https://b.example/1"
    assert parse_feed("not xml") == []


def test_technews_hn_plus_rss_and_cache(monkeypatch):
    import paper.connectors.technews as tn

    hn = {"hits": [{"title": "Show HN: paper", "url": "https://x.example", "points": 412, "objectID": "1"}]}
    calls = {"n": 0}

    def fake_get_json(url):
        calls["n"] += 1
        return hn

    monkeypatch.setattr(tn._http, "get_json", fake_get_json)
    monkeypatch.setattr(tn._http, "get_text", lambda url: RSS)

    store = Store()
    cfg = PaperConfig(rss_feeds=["https://feed.example/rss"])
    section = TechNewsConnector().fetch(ctx(cfg=cfg, store=store))
    titles = [i.title for i in section.items]
    assert "Show HN: paper" in titles and "Post One" in titles
    assert section.items[0].meta == "412 pts"

    # second fetch comes from cache — no new HTTP calls
    before = calls["n"]
    section2 = TechNewsConnector().fetch(ctx(cfg=cfg, store=store))
    assert calls["n"] == before
    assert [i.title for i in section2.items] == titles


def test_technews_hn_down_still_serves_rss(monkeypatch):
    import paper.connectors.technews as tn

    def boom(url):
        raise OSError("down")

    monkeypatch.setattr(tn._http, "get_json", boom)
    monkeypatch.setattr(tn._http, "get_text", lambda url: RSS)
    cfg = PaperConfig(rss_feeds=["https://feed.example/rss"])
    section = TechNewsConnector().fetch(ctx(cfg=cfg))
    assert [i.title for i in section.items] == ["Post One", "Post Two"]
    assert "hacker news" in section.notice


# --- github ---

def test_github_unavailable_without_gh(monkeypatch):
    import paper.connectors.github as gh

    monkeypatch.setattr(gh.shutil, "which", lambda name: None)
    ok, hint = GitHubConnector().available()
    assert not ok and "gh CLI" in hint


def test_github_parses_notifications_and_reviews(monkeypatch):
    import paper.connectors.github as gh

    notifications = json.dumps(
        [{"repository": {"name": "livecv"}, "subject": {"title": "CI failed"}, "reason": "ci_activity"}]
    )
    prs = json.dumps(
        [{"repository": {"name": "toolbelt"}, "title": "Add skill", "url": "https://gh.example/pr/1"}]
    )

    def fake_gh(*args):
        return notifications if args[0] == "api" else prs

    monkeypatch.setattr(gh, "_gh", fake_gh)
    section = GitHubConnector().fetch(ctx())
    titles = [i.title for i in section.items]
    assert "livecv: CI failed" in titles
    assert "review requested — toolbelt: Add skill" in titles


# --- weather ---

def test_weather_summary_and_geocode_cache(monkeypatch):
    import paper.connectors.weather as w

    geo = {"results": [{"latitude": 47.6, "longitude": -122.3}]}
    forecast = {
        "current_weather": {"temperature": 71.6, "weathercode": 2},
        "daily": {
            "temperature_2m_max": [75.0],
            "temperature_2m_min": [58.0],
            "precipitation_probability_max": [10],
        },
    }
    calls = []

    def fake_get_json(url):
        calls.append(url)
        return geo if "geocoding" in url else forecast

    monkeypatch.setattr(w._http, "get_json", fake_get_json)
    store = Store()
    section = WeatherConnector().fetch(ctx(store=store))
    assert "partly cloudy" in section.items[0].title
    assert "72°F" in section.items[0].title

    WeatherConnector().fetch(ctx(store=store))
    geocode_calls = [u for u in calls if "geocoding" in u]
    assert len(geocode_calls) == 1  # cached


# --- calendar ---

def test_calendar_unavailable_hint(monkeypatch):
    import paper.connectors.calendar_ as cal

    monkeypatch.setattr(cal.shutil, "which", lambda name: None)
    ok, hint = CalendarConnector().available()
    assert not ok and "gcalcli" in hint


def test_calendar_gcalcli_tsv(monkeypatch):
    import paper.connectors.calendar_ as cal

    monkeypatch.setattr(cal.shutil, "which", lambda name: "/usr/bin/gcalcli" if name == "gcalcli" else None)
    tsv = "2026-07-01\t09:30\t2026-07-01\t10:00\tStandup\n2026-07-01\t14:00\t2026-07-01\t15:00\t1:1 with Sam\n"
    monkeypatch.setattr(cal, "_run", lambda argv: tsv)
    section = CalendarConnector().fetch(ctx())
    assert [i.title for i in section.items] == ["Standup", "1:1 with Sam"]
    assert section.items[0].meta == "09:30"
