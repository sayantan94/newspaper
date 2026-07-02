import warnings

from paper.config import PaperConfig
from paper.connectors import section_connectors, work_connectors

USER_PLUGIN = """
from paper.connectors.base import SectionConnector, WorkConnector
from paper.models import Evidence, Section

class SlackConnector(WorkConnector):
    name = "slack"
    def collect(self, date):
        return [Evidence("proj", "slack", "prompt", "hi", "2026-06-30T00:00:00Z")]

class StocksConnector(SectionConnector):
    name = "stocks"
    title = "MARKETS"
    def fetch(self, ctx):
        return Section(name="stocks", title="MARKETS")
"""


def _plugin_dir(home):
    d = home / "connectors"
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_user_plugin_discovered(paper_home_tmp):
    (_plugin_dir(paper_home_tmp) / "myplug.py").write_text(USER_PLUGIN)
    cfg = PaperConfig()
    assert "slack" in [c.name for c in work_connectors(cfg)]
    assert "stocks" in [c.name for c in section_connectors(cfg)]


def test_disabled_filter(paper_home_tmp):
    (_plugin_dir(paper_home_tmp) / "myplug.py").write_text(USER_PLUGIN)
    cfg = PaperConfig(disabled=["slack", "stocks"])
    assert "slack" not in [c.name for c in work_connectors(cfg)]
    assert "stocks" not in [c.name for c in section_connectors(cfg)]


def test_broken_plugin_skipped(paper_home_tmp):
    (_plugin_dir(paper_home_tmp) / "broken.py").write_text("raise RuntimeError('boom')")
    (_plugin_dir(paper_home_tmp) / "myplug.py").write_text(USER_PLUGIN)
    cfg = PaperConfig()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        names = [c.name for c in work_connectors(cfg)]
    assert "slack" in names
