"""Connector registry: built-ins plus user plugins from $PAPER_HOME/connectors/."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
import warnings

from ..config import PaperConfig, paper_home
from .base import PaperContext, SectionConnector, WorkConnector

__all__ = [
    "PaperContext",
    "SectionConnector",
    "WorkConnector",
    "work_connectors",
    "section_connectors",
]

# Paper order matters: this is the order sections appear in the edition flow.
_BUILTIN_WORK = ["claude_code", "codex", "git"]
_BUILTIN_SECTION = ["openloops", "technews", "github", "sports", "gmail", "weather", "calendar_"]


def _classes_from_module(module, base) -> list[type]:
    return [
        obj
        for _, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, base) and obj is not base and obj.__module__ == module.__name__
    ]


def _builtin_classes(names: list[str], base) -> list[type]:
    classes: list[type] = []
    for name in names:
        try:
            module = importlib.import_module(f".{name}", package=__name__)
        except ImportError:
            continue  # built-in not implemented yet / optional
        classes.extend(_classes_from_module(module, base))
    return classes


def _user_classes(base) -> list[type]:
    plugin_dir = paper_home() / "connectors"
    classes: list[type] = []
    if not plugin_dir.is_dir():
        return classes
    for path in sorted(plugin_dir.glob("*.py")):
        mod_name = f"paper_user_connector_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as e:  # a broken plugin must never break the paper
            warnings.warn(f"skipping connector plugin {path.name}: {e}")
            continue
        classes.extend(_classes_from_module(module, base))
    return classes


def _instantiate(classes: list[type], config: PaperConfig) -> list:
    out = []
    for cls in classes:
        try:
            instance = cls()
        except Exception as e:
            warnings.warn(f"skipping connector {cls.__name__}: {e}")
            continue
        if instance.name and instance.name not in config.disabled:
            out.append(instance)
    return out


def work_connectors(config: PaperConfig) -> list[WorkConnector]:
    classes = _builtin_classes(_BUILTIN_WORK, WorkConnector) + _user_classes(WorkConnector)
    return _instantiate(classes, config)


def section_connectors(config: PaperConfig) -> list[SectionConnector]:
    classes = _builtin_classes(_BUILTIN_SECTION, SectionConnector) + _user_classes(
        SectionConnector
    )
    return _instantiate(classes, config)
