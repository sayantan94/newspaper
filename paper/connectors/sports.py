"""Section: the sports page — headlines, yesterday's finals, and today's slate
via ESPN's public JSON endpoints (no API key)."""

from __future__ import annotations

import datetime as dt
from concurrent.futures import ThreadPoolExecutor

from ..models import Section, SectionItem
from .base import PaperContext, SectionConnector
from . import _http

_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard?dates={date}"
_NEWS = "https://site.api.espn.com/apis/site/v2/sports/{path}/news"
_CACHE_TTL = 30 * 60
_MAX_SCORES_PER_LEAGUE = 5
_MAX_NEWS_PER_LEAGUE = 3

LEAGUES = {
    "nba": "basketball/nba",
    "wnba": "basketball/wnba",
    "nfl": "football/nfl",
    "mlb": "baseball/mlb",
    "nhl": "hockey/nhl",
    "epl": "soccer/eng.1",
    "ucl": "soccer/uefa.champions",
    "mls": "soccer/usa.1",
}


def _resolve_leagues(configured: list[str]) -> tuple[list[str], list[str]]:
    """Expand "all"; return (valid leagues, unknown names)."""
    if "all" in configured:
        return list(LEAGUES), []
    valid = [name for name in configured if name in LEAGUES]
    unknown = [name for name in configured if name not in LEAGUES]
    return valid, unknown


def _event_line(event: dict) -> str | None:
    status = (event.get("status") or {}).get("type") or {}
    state = status.get("state", "")
    competitions = event.get("competitions") or [{}]
    competitors = competitions[0].get("competitors") or []
    if len(competitors) == 2:
        # ESPN order: [home, away]
        def side(c):
            return (c.get("team") or {}).get("abbreviation", "?"), c.get("score", "")

        (home, home_score), (away, away_score) = side(competitors[0]), side(competitors[1])
        if state == "post":
            return f"{away} {away_score} — {home} {home_score} · {status.get('shortDetail', 'Final')}"
        if state == "in":
            return f"{away} {away_score} — {home} {home_score} · live, {status.get('shortDetail', '')}"
        return f"{away} @ {home} · {status.get('shortDetail', '')}"
    return event.get("shortName") or event.get("name")


def _fetch_league(league: str, path: str, yesterday: str, today: str) -> list[SectionItem]:
    items: list[SectionItem] = []
    # news headlines first — that's the story of the day
    news = _http.get_json(_NEWS.format(path=path))
    for article in (news.get("articles") or [])[:_MAX_NEWS_PER_LEAGUE]:
        headline = article.get("headline") or ""
        if headline:
            url = ((article.get("links") or {}).get("web") or {}).get("href", "")
            items.append(SectionItem(title=headline, url=url, meta=league.upper()))
    # then the scoreboard: yesterday's finals + today's slate
    events = []
    for date in (yesterday, today):
        data = _http.get_json(_SCOREBOARD.format(path=path, date=date))
        events.extend(data.get("events") or [])
    for event in events[:_MAX_SCORES_PER_LEAGUE]:
        line = _event_line(event)
        if line:
            items.append(SectionItem(title=line, meta=f"{league.upper()} score"))
    return items


class SportsConnector(SectionConnector):
    name = "sports"
    title = "THE SPORTS PAGE"
    timeout = 20.0  # fans out across leagues

    def fetch(self, ctx: PaperContext) -> Section:
        leagues, unknown = _resolve_leagues(ctx.config.sports_leagues)
        failures = [f"unknown league '{name}'" for name in unknown]
        cache_key = "sports_" + "_".join(leagues)
        cached = ctx.store.cache_get(cache_key, _CACHE_TTL) if ctx.store else None
        if cached is not None:
            return Section(
                name=self.name,
                title=self.title,
                items=[SectionItem.from_dict(d) for d in cached],
            )
        yesterday = (ctx.date - dt.timedelta(days=1)).strftime("%Y%m%d")
        today = ctx.date.strftime("%Y%m%d")
        items: list[SectionItem] = []
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                league: pool.submit(_fetch_league, league, LEAGUES[league], yesterday, today)
                for league in leagues
            }
            for league, future in futures.items():
                try:
                    items.extend(future.result(timeout=self.timeout))
                except Exception:
                    failures.append(league)
        if ctx.store and items:
            ctx.store.cache_put(cache_key, [i.__dict__ for i in items])
        notice = f"unreachable: {', '.join(failures)}" if failures else ""
        return Section(name=self.name, title=self.title, items=items, notice=notice)
