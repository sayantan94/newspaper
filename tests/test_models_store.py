import os
import time

from paper.models import Edition, LedgerDay, ProjectEntry
from paper.store import Store


def make_day(date="2026-06-30"):
    return LedgerDay(
        date=date,
        projects=[
            ProjectEntry(
                project="x-lens",
                summary="I built the lens parser.",
                where_left_off="tests failing on unicode",
                open_threads=["unicode bug"],
                next_steps=["fix tests"],
                tags=["feature"],
                sources=["claude-code", "git"],
            )
        ],
    )


def test_ledger_roundtrip_tolerates_unknown_keys():
    day = make_day()
    d = day.to_dict()
    d["projects"][0]["mystery"] = 42
    d["totally_new"] = "ignored"
    loaded = LedgerDay.from_dict(d)
    assert loaded.projects[0].project == "x-lens"
    assert loaded.projects[0].where_left_off == "tests failing on unicode"


def test_store_ledger_and_dates():
    store = Store()
    store.write_ledger(make_day("2026-06-29"))
    store.write_ledger(make_day("2026-06-30"))
    assert store.ledger_dates() == ["2026-06-29", "2026-06-30"]
    assert store.read_ledger("2026-06-30").projects[0].summary
    assert store.read_ledger("2026-01-01") is None


def test_edition_roundtrip():
    store = Store()
    ed = Edition(date="2026-07-01", headline="Big day", actions=["ship it"])
    store.write_edition(ed)
    loaded = store.read_edition("2026-07-01")
    assert loaded.headline == "Big day"
    assert loaded.actions == ["ship it"]
    assert loaded.fallback is False


def test_cache_ttl():
    store = Store()
    store.cache_put("hn:top", {"a": 1})
    assert store.cache_get("hn:top", ttl_seconds=60) == {"a": 1}
    old = time.time() - 3600
    os.utime(store._cache_path("hn:top"), (old, old))
    assert store.cache_get("hn:top", ttl_seconds=60) is None
