"""Section: tech wire — Hacker News front page + configured RSS/Atom feeds."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..models import Section, SectionItem
from .base import PaperContext, SectionConnector
from . import _http

_HN_URL = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={n}"
_CACHE_TTL = 30 * 60
_MAX_PER_FEED = 10


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(xml_text: str) -> list[SectionItem]:
    """Minimal RSS 2.0 / Atom parsing: title + link per entry."""
    items: list[SectionItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    for node in root.iter():
        if _strip_ns(node.tag) not in ("item", "entry"):
            continue
        title, link = "", ""
        for child in node:
            tag = _strip_ns(child.tag)
            if tag == "title":
                title = (child.text or "").strip()
            elif tag == "link":
                link = (child.text or "").strip() or child.attrib.get("href", "")
        if title:
            items.append(SectionItem(title=title, url=link))
        if len(items) >= _MAX_PER_FEED:
            break
    return items


class TechNewsConnector(SectionConnector):
    name = "technews"
    title = "TECH WIRE"

    def fetch(self, ctx: PaperContext) -> Section:
        cached = ctx.store.cache_get("technews", _CACHE_TTL) if ctx.store else None
        if cached is not None:
            return Section(
                name=self.name,
                title=self.title,
                items=[SectionItem.from_dict(d) for d in cached],
            )
        items: list[SectionItem] = []
        failures: list[str] = []
        try:
            data = _http.get_json(_HN_URL.format(n=ctx.config.hn_count))
            for hit in data.get("hits", []):
                title = hit.get("title") or ""
                if not title:
                    continue
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                items.append(SectionItem(title=title, url=url, meta=f"{hit.get('points', 0)} pts"))
        except Exception:
            failures.append("hacker news")
        for feed in ctx.config.rss_feeds:
            try:
                items.extend(parse_feed(_http.get_text(feed)))
            except Exception:
                failures.append(feed)
        if ctx.store and items:
            ctx.store.cache_put("technews", [i.__dict__ for i in items])
        notice = f"unreachable: {', '.join(failures)}" if failures else ""
        return Section(name=self.name, title=self.title, items=items, notice=notice)
