"""
Drop-in NOMI plugin template.

Copy this file, rename it (no leading underscore), fill in PLUGIN and run().
No other file needs to change: NOMI finds it at the next launch and Jarvis can
use it straight away. Turn a plugin off by adding its file name (without .py)
to "plugins_disabled" in ~/.nomi/config.json.
"""

PLUGIN = {
    "name": "my_plugin",                  # snake_case, unique, ^[a-zA-Z_][a-zA-Z0-9_]{0,63}$
    "description": (
        "One or two sentences Claude reads to decide when to use this tool. "
        "Say what it does and the kind of request that should trigger it."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "example_arg": {"type": "string", "description": "What this argument means"},
        },
        "required": [],                    # leave empty for a tool with no arguments
    },
    # "confirm": True,                     # ask the user on screen before running
}


def run(parameters: dict, store=None, host=None, speak=None) -> str:
    """
    parameters: the arguments Claude chose, shaped like PLUGIN["parameters"].
    Declare any of these by name to receive them:
      store  — NOMI's memory (store.todos, store.notes, store.add_task(...), …)
      host   — the main window (host.open_app("notes"), …)
      speak  — speak(text) says something out loud right now
      voice, confirm, undo — see core/action_loader.py
    Return a short string (or plain data): Claude reads it and answers the user.
    Don't raise: catch your own errors and return what went wrong.
    """
    example_arg = parameters.get("example_arg", "")
    try:
        return f"Did the thing with {example_arg}."
    except Exception as e:
        return f"my_plugin failed: {e}"
