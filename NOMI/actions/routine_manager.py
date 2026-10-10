"""Routines (daily, at a set time) and skills (reusable instructions in the Skills Deck)."""
from __future__ import annotations

import re


def list_routines(store):
    return store.routines


def add_routine(parameters: dict, store, undo):
    t = str(parameters.get("time", ""))
    if not re.match(r"^\d{1,2}:\d{2}$", t):
        return "The time must be HH:MM in 24-hour form, like 07:30."
    r = store.add_routine(t, str(parameters.get("name") or "Routine"), str(parameters.get("prompt") or ""))
    undo.push(f"adding the routine “{r['name']}”", lambda: store.remove_routine(r["id"]))
    return r


def run_routine(parameters: dict, store, host):
    name = str(parameters.get("name", "")).lower()
    r = next((x for x in store.routines if x["name"].lower() == name), None) \
        or next((x for x in store.routines if name and name in x["name"].lower()), None)
    if not r:
        return "I couldn't find that routine."
    store.mark_routine_run(r["id"])
    return f"Routine “{r['name']}”. Do this now: {r['prompt'] or r['name']}"


def list_skills(store):
    return [{"name": s["name"], "model": s.get("model"), "effort": s.get("effort"), "prompt": s["prompt"]} for s in store.skills]


def add_skill(parameters: dict, store, undo):
    s = store.add_skill(str(parameters.get("name") or "skill"), str(parameters.get("prompt") or ""))
    undo.push(f"adding the skill /{s['name']}", lambda: store.remove_skill(s["id"]))
    return s


TOOLS = [
    {"name": "list_routines", "description": "Daily routines as [{id, time, name, prompt}].",
     "parameters": {"type": "object", "properties": {}}, "handler": list_routines},
    {"name": "add_routine", "description": "Add a daily routine at HH:MM (24h) with a name and what Jarvis should do.",
     "parameters": {"type": "object", "properties": {"time": {"type": "string"}, "name": {"type": "string"}, "prompt": {"type": "string"}},
                    "required": ["time", "name"]}, "handler": add_routine},
    {"name": "run_routine", "description": "Run a routine now by its name; returns its instructions for you to carry out.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}, "handler": run_routine},
    {"name": "list_skills", "description": "Skills in the Skills Deck with their model and effort.",
     "parameters": {"type": "object", "properties": {}}, "handler": list_skills},
    {"name": "add_skill", "description": "Add a reusable skill to the Skills Deck: a short name and the instructions to run.",
     "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["name", "prompt"]},
     "handler": add_skill},
]
