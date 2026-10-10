"""Undo: take back what Jarvis (or you) just did.

Actions that change your data push a small "how to reverse this" function here.
"Jarvis, undo that", the `undo` terminal command or Ctrl+Z on the dashboard pops
the newest one and runs it.
"""
from __future__ import annotations

from collections import deque
from typing import Callable

from core.log import log

_stack: deque[tuple[str, Callable[[], None]]] = deque(maxlen=50)


def push(label: str, revert: Callable[[], None]) -> None:
    _stack.append((label, revert))


def can_undo() -> bool:
    return bool(_stack)


def peek() -> str | None:
    return _stack[-1][0] if _stack else None


def undo() -> str:
    if not _stack:
        return "There's nothing to undo."
    label, revert = _stack.pop()
    try:
        revert()
    except Exception as e:
        log(f"⚠ Undo failed for '{label}': {e}")
        return f"I couldn't undo {label}: {e}"
    log(f"↩ Undid: {label}")
    return f"Undone: {label}."
