"""Opens and closes NOMI's own apps (Jarvis chat, notes, tasks, calculator, terminal,
settings, system map)."""
from __future__ import annotations


def open_app(parameters: dict, host):
    app = str(parameters.get("app", "")).strip()
    if not host.open_app(app):
        return f"There's no app called {app}. Apps: {', '.join(host.app_names())}."
    return f"Opened {app}."


def close_app(parameters: dict, host):
    app = str(parameters.get("app", "")).strip() or "all"
    host.close_app(app)
    return f"Closed {app}."


TOOLS = [
    {"name": "open_app",
     "description": "Open a NOMI app window: jarvis (full conversation), notes, tasks, calc, term (terminal), settings, or map (System Map).",
     "parameters": {"type": "object", "properties": {"app": {"type": "string"}}, "required": ["app"]}, "handler": open_app},
    {"name": "close_app", "description": "Close a NOMI app window, or 'all'.",
     "parameters": {"type": "object", "properties": {"app": {"type": "string"}}, "required": ["app"]}, "handler": close_app},
]
