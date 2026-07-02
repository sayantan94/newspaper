import pytest


@pytest.fixture(autouse=True)
def paper_home_tmp(tmp_path, monkeypatch):
    home = tmp_path / "paperhome"
    monkeypatch.setenv("PAPER_HOME", str(home))
    return home


class FakeEditor:
    """Stands in for llm.ClaudeEditor in tests."""

    def __init__(self, response=None, responses=None):
        self.prompts = []
        self.response = response
        self.responses = list(responses) if responses is not None else None

    def complete_json(self, prompt):
        self.prompts.append(prompt)
        if self.responses is not None:
            return self.responses.pop(0) if self.responses else None
        return self.response


@pytest.fixture
def fake_editor():
    return FakeEditor
