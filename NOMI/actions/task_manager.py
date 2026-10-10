"""Tasks: list, add, complete and delete items on the to-do list."""
from __future__ import annotations


def list_tasks(store):
    return [{"id": t["id"], "text": t["text"], "done": t["done"]} for t in store.todos]


def add_task(parameters: dict, store, undo):
    text = str(parameters.get("text", "")).strip()
    if not text:
        return "Tell me what the task is."
    t = store.add_task(text)
    undo.push(f"adding “{t['text']}”", lambda: store.delete_task(t["id"]))
    return t


def complete_task(parameters: dict, store, undo):
    tid, done = parameters.get("id"), parameters.get("done", True) is not False
    t = store.find_task(tid)
    if not t:
        return f"There's no task with id {tid}."
    before = t["done"]
    store.set_task_done(tid, done)
    undo.push(f"marking “{t['text']}” {'done' if done else 'open'}", lambda: store.set_task_done(tid, before))
    return t


def delete_task(parameters: dict, store, undo):
    tid = parameters.get("id")
    t = store.find_task(tid)
    if not t:
        return f"There's no task with id {tid}."
    idx = store.todos.index(t)
    store.delete_task(tid)

    def restore():
        store.todos.insert(idx, t)
        store.touch("todos")
    undo.push(f"deleting “{t['text']}”", restore)
    return f"Deleted “{t['text']}”."


TOOLS = [
    {"name": "list_tasks", "description": "The user's to-do list as [{id, text, done}].",
     "parameters": {"type": "object", "properties": {}}, "handler": list_tasks},
    {"name": "add_task", "description": "Add a task to the to-do list.",
     "parameters": {"type": "object", "properties": {"text": {"type": "string", "description": "What to do"}}, "required": ["text"]},
     "handler": add_task},
    {"name": "complete_task", "description": "Mark a task done by id (done=false reopens it).",
     "parameters": {"type": "object", "properties": {"id": {"type": "number"}, "done": {"type": "boolean"}}, "required": ["id"]},
     "handler": complete_task},
    {"name": "delete_task", "description": "Delete a task by id. The user is asked to confirm on screen.",
     "parameters": {"type": "object", "properties": {"id": {"type": "number"}}, "required": ["id"]},
     "handler": delete_task, "confirm": True},
]
