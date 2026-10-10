"""Notes (the Second Brain): list, read, create and delete notes."""
from __future__ import annotations

from datetime import datetime


def list_notes(store):
    return [{"id": n["id"], "title": n["title"], "updated": datetime.fromtimestamp(n["t"] / 1000).isoformat(timespec="minutes")}
            for n in store.notes]


def read_note(parameters: dict, store):
    n = next((x for x in store.notes if str(x["id"]) == str(parameters.get("id"))), None)
    return n["body"][:20000] if n else "There's no note with that id."


def create_note(parameters: dict, store, undo):
    n = store.add_note(str(parameters.get("title") or "Untitled"), str(parameters.get("body") or ""))
    undo.push(f"creating the note “{n['title']}”", lambda: store.delete_note(n["id"]))
    return {"id": n["id"], "title": n["title"]}


def delete_note(parameters: dict, store, undo):
    n = next((x for x in store.notes if str(x["id"]) == str(parameters.get("id"))), None)
    if not n:
        return "There's no note with that id."
    idx = store.notes.index(n)
    store.delete_note(n["id"])

    def restore():
        store.notes.insert(idx, n)
        store.touch("notes")
    undo.push(f"deleting the note “{n['title']}”", restore)
    return f"Deleted the note “{n['title']}”."


TOOLS = [
    {"name": "list_notes", "description": "The user's notes as [{id, title, updated}].",
     "parameters": {"type": "object", "properties": {}}, "handler": list_notes},
    {"name": "read_note", "description": "The full text of one note.",
     "parameters": {"type": "object", "properties": {"id": {"type": "number"}}, "required": ["id"]}, "handler": read_note},
    {"name": "create_note", "description": "Save a new note (ideas, drafts, plans, summaries).",
     "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "body": {"type": "string"}}, "required": ["title", "body"]},
     "handler": create_note},
    {"name": "delete_note", "description": "Delete a note by id. The user is asked to confirm on screen.",
     "parameters": {"type": "object", "properties": {"id": {"type": "number"}}, "required": ["id"]},
     "handler": delete_note, "confirm": True},
]
