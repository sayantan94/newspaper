"""Core data shapes persisted to disk and passed between layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


def _pick(cls, d: dict) -> dict:
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in known}


@dataclass
class Evidence:
    project: str
    source: str  # connector name: "claude-code" | "codex" | "git" | ...
    kind: str  # "prompt" | "response" | "commit" | "files"
    text: str
    timestamp: str  # ISO 8601


@dataclass
class ProjectEntry:
    project: str
    summary: str
    where_left_off: str = ""
    open_threads: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectEntry":
        return cls(**_pick(cls, d))


@dataclass
class LedgerDay:
    date: str  # "YYYY-MM-DD"
    projects: list[ProjectEntry] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "LedgerDay":
        return cls(
            date=d.get("date", ""),
            projects=[
                ProjectEntry.from_dict(p)
                for p in d.get("projects", [])
                if isinstance(p, dict) and p.get("project")
            ],
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SectionItem:
    title: str
    detail: str = ""
    url: str = ""
    meta: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "SectionItem":
        return cls(**_pick(cls, d))


@dataclass
class Section:
    name: str
    title: str
    items: list[SectionItem] = field(default_factory=list)
    notice: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Edition:
    date: str
    headline: str = ""
    lead: str = ""
    yesterday: list[dict] = field(default_factory=list)  # [{"project","story"}]
    open_loops: list[str] = field(default_factory=list)
    tech_wire: list[dict] = field(default_factory=list)  # [{"title","url","meta","why"}]
    github: list[str] = field(default_factory=list)
    sports: list[str] = field(default_factory=list)
    inbox: list[str] = field(default_factory=list)
    calendar: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    weather: str = ""
    notices: list[str] = field(default_factory=list)
    fallback: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Edition":
        data = _pick(cls, d)
        data.setdefault("date", "")
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)
