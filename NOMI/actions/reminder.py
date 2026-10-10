"""Reminders: "remind me in 20 minutes to stretch", "remind me at 18:30 to call mum".

Saved in memory, so they survive a restart; when one is due, Jarvis says it out
loud and shows it on screen (ui.py checks every few seconds).
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta


def set_reminder(parameters: dict, store, undo):
    text = str(parameters.get("text", "")).strip() or "Reminder"
    now = datetime.now()
    when = None
    if parameters.get("minutes") not in (None, ""):
        try:
            when = now + timedelta(minutes=float(parameters["minutes"]))
        except (TypeError, ValueError):
            return "Minutes must be a number."
    elif parameters.get("time"):
        m = re.match(r"^(\d{1,2}):(\d{2})$", str(parameters["time"]).strip())
        if not m:
            return "The time must be HH:MM, like 18:30."
        when = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if when <= now:
            when += timedelta(days=1)
    if when is None:
        return "Tell me when: minutes from now, or a time like 18:30."
    r = store.add_reminder(int(when.timestamp() * 1000), text)
    undo.push(f"the reminder “{text}”", lambda: store.remove_reminder(r["id"]))
    return {"id": r["id"], "text": text, "due": when.strftime("%A %H:%M")}


def list_reminders(store):
    return [{"id": r["id"], "text": r["text"], "due": datetime.fromtimestamp(r["due"] / 1000).strftime("%a %H:%M")}
            for r in sorted(store.reminders, key=lambda r: r["due"])]


def cancel_reminder(parameters: dict, store):
    rid = str(parameters.get("id", ""))
    if not any(r["id"] == rid for r in store.reminders):
        return "There's no reminder with that id."
    store.remove_reminder(rid)
    return "Cancelled."


TOOLS = [
    {"name": "set_reminder",
     "description": "Remind the user later: give either minutes from now, or a time HH:MM (today, or tomorrow if passed). Jarvis says it aloud when due.",
     "parameters": {"type": "object", "properties": {"text": {"type": "string"}, "minutes": {"type": "number"}, "time": {"type": "string"}},
                    "required": ["text"]}, "handler": set_reminder},
    {"name": "list_reminders", "description": "Upcoming reminders.",
     "parameters": {"type": "object", "properties": {}}, "handler": list_reminders},
    {"name": "cancel_reminder", "description": "Cancel a reminder by id.",
     "parameters": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}, "handler": cancel_reminder},
]
