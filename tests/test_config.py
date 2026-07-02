from pathlib import Path

from paper.config import DEFAULT_CONFIG, config_path, load_config, paper_home


def test_paper_home_respects_env(paper_home_tmp):
    assert paper_home() == paper_home_tmp


def test_first_load_writes_default_config(paper_home_tmp):
    cfg = load_config()
    assert config_path().exists()
    assert config_path().read_text() == DEFAULT_CONFIG
    assert cfg.lookback_days == 14
    assert cfg.llm_engine == "claude"
    assert cfg.llm_command == ""


def test_toml_values_override_defaults(paper_home_tmp):
    paper_home_tmp.mkdir(parents=True)
    config_path().write_text(
        """
workspace_roots = ["~/code"]
lookback_days = 3
markdown_mirror = "/tmp/vault"

[connectors]
disabled = ["calendar"]

[technews]
rss_feeds = ["https://example.com/feed.xml"]
hn_count = 5

[weather]
location = "Portland"

[llm]
engine = "codex"
command = "claude-x"
model = "sonnet"
"""
    )
    cfg = load_config()
    assert cfg.workspace_roots == ["~/code"]
    assert cfg.roots == [Path("~/code").expanduser()]
    assert cfg.lookback_days == 3
    assert cfg.markdown_mirror == "/tmp/vault"
    assert cfg.disabled == ["calendar"]
    assert cfg.rss_feeds == ["https://example.com/feed.xml"]
    assert cfg.hn_count == 5
    assert cfg.location == "Portland"
    assert cfg.llm_engine == "codex"
    assert cfg.llm_command == "claude-x"
    assert cfg.llm_model == "sonnet"


def test_unknown_keys_ignored(paper_home_tmp):
    paper_home_tmp.mkdir(parents=True)
    config_path().write_text("mystery = true\nlookback_days = 2\n")
    cfg = load_config()
    assert cfg.lookback_days == 2
