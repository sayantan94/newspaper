import datetime as dt

from paper.config import PaperConfig
from paper.connectors.base import PaperContext
from paper.connectors.calendar_ import ics_events_today
from paper.connectors.gmail import GmailConnector
from paper.connectors.sports import LEAGUES, SportsConnector, _resolve_leagues
from paper.store import Store
from paper.util import daypart


def ctx(cfg=None, store=None):
    return PaperContext(
        config=cfg or PaperConfig(),
        date=dt.date(2026, 7, 1),
        recent_themes=[],
        latest_ledger=None,
        store=store,
    )


# --- daypart ---

def test_daypart_boundaries():
    def at(hour):
        return daypart(dt.datetime(2026, 7, 1, hour, 0))

    assert at(6) == "morning"
    assert at(13) == "afternoon"
    assert at(19) == "evening"
    assert at(23) == "late night"
    assert at(2) == "late night"


# --- sports ---

ESPN_SCOREBOARD = {
    "events": [
        {
            "status": {"type": {"state": "post", "shortDetail": "Final"}},
            "competitions": [
                {
                    "competitors": [
                        {"team": {"abbreviation": "SEA"}, "score": "5"},
                        {"team": {"abbreviation": "NYY"}, "score": "3"},
                    ]
                }
            ],
        }
    ]
}
ESPN_NEWS = {"articles": [{"headline": "Mariners walk it off", "links": {"web": {"href": "https://e.com/1"}}}]}


def test_resolve_leagues_all_and_unknown():
    all_leagues, unknown = _resolve_leagues(["all"])
    assert all_leagues == list(LEAGUES) and unknown == []
    valid, unknown = _resolve_leagues(["nba", "curling"])
    assert valid == ["nba"] and unknown == ["curling"]


def test_sports_fetch_news_and_scores(monkeypatch):
    import paper.connectors.sports as sp

    def fake_get_json(url):
        return sp._NEWS.split("{")[0] in url and ESPN_NEWS or (ESPN_NEWS if "news" in url else ESPN_SCOREBOARD)

    monkeypatch.setattr(sp._http, "get_json", lambda url: ESPN_NEWS if "news" in url else ESPN_SCOREBOARD)
    cfg = PaperConfig(sports_leagues=["mlb"])
    section = SportsConnector().fetch(ctx(cfg=cfg, store=Store()))
    titles = [i.title for i in section.items]
    assert "Mariners walk it off" in titles
    assert any("NYY 3 — SEA 5" in t for t in titles)
    assert section.notice == ""


def test_sports_unknown_league_notice(monkeypatch):
    import paper.connectors.sports as sp

    monkeypatch.setattr(sp._http, "get_json", lambda url: ESPN_NEWS if "news" in url else ESPN_SCOREBOARD)
    section = SportsConnector().fetch(ctx(cfg=PaperConfig(sports_leagues=["curling"])))
    assert "unknown league" in section.notice


# --- gmail ---

def test_gmail_unconfigured_notice():
    section = GmailConnector().fetch(ctx(cfg=PaperConfig()))
    assert "paper auth gmail" in section.notice
    assert section.items == []


def test_gmail_fetch_items(monkeypatch):
    import paper.connectors.gmail as gm

    monkeypatch.setattr(gm, "get_secret", lambda service, account: "app-pass")
    monkeypatch.setattr(
        gm, "fetch_unread", lambda address, password: [("Jane Doe", "Offer letter"), ("CI", "Build failed")]
    )
    cfg = PaperConfig(gmail_address="me@gmail.com")
    section = GmailConnector().fetch(ctx(cfg=cfg))
    assert section.items[0].title == "Offer letter"
    assert section.items[0].meta == "Jane Doe"


# --- calendar via ICS ---

ICS = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:One-off sync
DTSTART:20260701T163000Z
END:VEVENT
BEGIN:VEVENT
SUMMARY:Weekly standup
DTSTART;TZID=America/Los_Angeles:20260401T093000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR
END:VEVENT
BEGIN:VEVENT
SUMMARY:Not today
DTSTART:20260702T090000Z
END:VEVENT
END:VCALENDAR
"""


def test_ics_events_today():
    # 2026-07-01 is a Wednesday → weekly MO,WE,FR standup hits
    items = ics_events_today(ICS, dt.date(2026, 7, 1))
    titles = [i.title for i in items]
    assert "One-off sync" in titles
    assert "Weekly standup" in titles
    assert "Not today" not in titles
