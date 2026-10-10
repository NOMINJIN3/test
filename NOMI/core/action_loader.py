"""Finds every skill Jarvis can use and runs it when Claude asks.

Each actions/*.py file declares its skill(s) with a module-level ``TOOL`` dict
(or a ``TOOLS`` list of them); plugins/*.py declare ``PLUGIN`` + ``run()`` (see
plugin_loader.py). Both end up in one registry, so adding a skill is always a
one-file change and nothing else needs editing.

    TOOL = {
        "name":        "add_task",                       # ^[a-zA-Z_][a-zA-Z0-9_]{0,63}$
        "description": "Add a task to the to-do list.",  # what Claude reads to pick it
        "parameters":  {"type": "object", "properties": {...}, "required": [...]},
        "handler":     add_task,                         # the function to run
        "confirm":     False,                            # True → ask the user first
    }

A handler receives ``parameters`` plus any of these it declares by name:
``store`` (memory), ``host`` (the main window), ``voice`` (text-to-speech),
``speak`` (say something now), ``confirm`` (ask yes/no), ``undo`` (the undo stack).

Discovery never raises: a broken file is logged and skipped.
"""
from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from core.log import log

_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$")
_CTX_KEYS = ("store", "host", "voice", "speak", "confirm", "undo")


@dataclass
class ActionRecord:
    name: str
    description: str = ""
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})
    handler: Callable | None = None
    file: str = ""
    source: str = "action"   # "action" | "plugin"
    confirm: bool = False

    def declaration(self) -> dict:
        p = dict(self.parameters or {})
        p.setdefault("type", "object")
        p.setdefault("properties", {})
        return {"name": self.name, "description": self.description, "input_schema": p}


class ActionRegistry:
    def __init__(self) -> None:
        self.records: dict[str, ActionRecord] = {}
        self.context: dict[str, Any] = {}

    # ---- registration
    def add(self, rec: ActionRecord) -> bool:
        if not _NAME_RE.match(rec.name or ""):
            log(f"⚠ {rec.file}: invalid tool name {rec.name!r} — skipped", "ACTIONS")
            return False
        if not callable(rec.handler):
            log(f"⚠ {rec.file}: '{rec.name}' has no handler — skipped", "ACTIONS")
            return False
        if rec.name in self.records:
            log(f"⚠ {rec.file}: '{rec.name}' already defined in {self.records[rec.name].file} — skipped", "ACTIONS")
            return False
        self.records[rec.name] = rec
        return True

    def bind(self, **ctx) -> None:
        """Give handlers access to the running app (store, host, voice …)."""
        self.context.update(ctx)

    # ---- for the LLM
    def declarations(self) -> list[dict]:
        return [r.declaration() for r in self.records.values()]

    def names(self) -> list[str]:
        return list(self.records)

    # ---- dispatch
    def run(self, name: str, parameters: dict | None) -> Any:
        rec = self.records.get(name)
        if not rec:
            raise ValueError(f"unknown tool {name}")
        params = dict(parameters or {})
        if rec.confirm:
            ask = self.context.get("confirm")
            if ask and not ask(f"Jarvis wants to run “{name}”", _summary(params)):
                return "The user declined. Nothing was changed."
        sig = inspect.signature(rec.handler)
        kwargs = {}
        for key in _CTX_KEYS:
            if key in sig.parameters and key in self.context:
                kwargs[key] = self.context[key]
        first = next(iter(sig.parameters), None)
        if first and first not in _CTX_KEYS:
            return rec.handler(params, **kwargs)
        return rec.handler(**kwargs)


def _summary(params: dict) -> str:
    return ", ".join(f"{k}: {v}" for k, v in params.items()) or "no details"


def _load_module(path: Path, package: str):
    name = f"{package}.{path.stem}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def discover_actions(registry: ActionRegistry, folder: Path) -> int:
    """Load every actions/*.py that exposes TOOL or TOOLS."""
    n = 0
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            mod = _load_module(path, "actions")
        except Exception as e:
            log(f"⚠ {path.name} failed to import: {e}", "ACTIONS")
            continue
        tools = getattr(mod, "TOOLS", None) or ([mod.TOOL] if hasattr(mod, "TOOL") else [])
        for t in tools:
            try:
                rec = ActionRecord(name=t["name"], description=t.get("description", ""),
                                   parameters=t.get("parameters") or {"type": "object", "properties": {}},
                                   handler=t.get("handler"), file=path.name, confirm=bool(t.get("confirm")))
            except Exception as e:
                log(f"⚠ {path.name}: bad TOOL ({e}) — skipped", "ACTIONS")
                continue
            n += registry.add(rec)
    return n
