"""Push-to-talk hotkey: Ctrl+Space.

With `pynput` installed the hotkey is global (works while NOMI is in the
background). Without it, Ctrl+Space works whenever the NOMI window has focus,
which ui.py sets up with a normal Qt shortcut. Either way, `pressed` fires.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.log import log

try:
    from pynput import keyboard as _kb
except Exception:  # not installed, or no display server access (e.g. Wayland)
    _kb = None


class Hotkey(QObject):
    pressed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._listener = None

    @property
    def is_global(self) -> bool:
        return self._listener is not None

    def start_global(self) -> bool:
        if _kb is None:
            log("⌨ Ctrl+Space works inside the NOMI window (pip install pynput for a global hotkey)")
            return False
        try:
            self._listener = _kb.GlobalHotKeys({"<ctrl>+<space>": self.pressed.emit})
            self._listener.daemon = True
            self._listener.start()
            log("⌨ Global push-to-talk: Ctrl+Space")
            return True
        except Exception as e:
            self._listener = None
            log(f"⌨ Global hotkey unavailable ({e}); Ctrl+Space works inside the window")
            return False

    def stop(self) -> None:
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
