"""Loads drop-in plugins from plugins/.

A plugin is one .py file with a ``PLUGIN`` dict and a ``run()`` function (copy
plugins/_template.py). It joins the same registry as the bundled actions, so
Jarvis can use it on the next launch with no other file changed.

Files starting with "_" are skipped, and so is any plugin turned off in
~/.nomi/config.json ("plugins_disabled"). A plugin that fails to load is logged
and skipped; it never stops NOMI from starting.
"""
from __future__ import annotations

from pathlib import Path

from core.action_loader import ActionRecord, ActionRegistry, _load_module
from core.log import log
from memory import config_manager as cfg


def discover_plugins(registry: ActionRegistry, folder: Path) -> list[str]:
    loaded = []
    for path in sorted(folder.glob("*.py")):
        if path.name.startswith("_"):
            continue
        name = path.stem
        if not cfg.get_plugin_enabled(name):
            log(f"⏸ {name} is turned off", "PLUGINS")
            continue
        try:
            mod = _load_module(path, "plugins")
            spec = getattr(mod, "PLUGIN")
            run = getattr(mod, "run")
        except Exception as e:
            log(f"⚠ '{name}' failed to load: {e}", "PLUGINS")
            continue
        rec = ActionRecord(name=spec.get("name", name), description=spec.get("description", ""),
                           parameters=spec.get("parameters") or {"type": "object", "properties": {}},
                           handler=run, file=path.name, source="plugin", confirm=bool(spec.get("confirm")))
        if registry.add(rec):
            loaded.append(rec.name)
    if loaded:
        log(f"🧩 Loaded: {', '.join(loaded)}", "PLUGINS")
    return loaded
