"""Status lines like `[JARVIS] Connected.` to the terminal and to ~/.nomi/nomi.log."""
from __future__ import annotations

import sys
import threading
from datetime import datetime

from config import DATA_DIR, DEBUG, LOG_FILE

_lock = threading.Lock()


def log(msg: str, tag: str = "JARVIS", debug: bool = False) -> None:
    if debug and not DEBUG:
        return
    line = f"[{tag}] {msg}"
    with _lock:
        try:
            print(line, flush=True)
        except Exception:  # pythonw / closed console: never fatal
            pass
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")
        except Exception:
            pass


def error(msg: str, tag: str = "JARVIS") -> None:
    log(f"⚠ {msg}", tag)
    try:
        sys.stderr.flush()
    except Exception:
        pass
