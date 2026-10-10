"""User preferences that change while NOMI runs, saved in ~/.nomi/config.json.

Small get_/save_ helpers so any file can read or change one setting without
knowing where or how it's stored.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading

from config import CONFIG_FILE, DATA_DIR

DEFAULTS = {
    "user_name": "Nominjin",
    "family_name": "Ts",
    "assistant_name": "Jarvis",
    "voice_on": True,
    "voice": "",            # OS voice name, "" = best English voice found
    "rate": 1.0,
    "wake_word": False,
    "push_to_talk_global": True,
    "dashboard": False,     # phone dashboard off until you turn it on
    "plugins_disabled": [],
}

_lock = threading.Lock()
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        data = dict(DEFAULTS)
        try:
            data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
        _cache = data
    return _cache


def _save() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(_load(), f, ensure_ascii=False, indent=1)
    os.replace(tmp, CONFIG_FILE)


def get(key: str, default=None):
    return _load().get(key, DEFAULTS.get(key, default))


def save(key: str, value) -> None:
    with _lock:
        _load()[key] = value
        _save()


def all_settings() -> dict:
    return _load()


def reset() -> None:
    global _cache
    with _lock:
        _cache = dict(DEFAULTS)
        _save()


# ── named helpers ─────────────────────────────────────────────────────────────
def get_user_name() -> str: return get("user_name") or "Nominjin"
def get_family_name() -> str: return get("family_name") or ""
def get_assistant_name() -> str: return get("assistant_name") or "Jarvis"
def save_user_name(v: str) -> None: save("user_name", v.strip() or "Nominjin")
def save_family_name(v: str) -> None: save("family_name", v.strip())

def get_voice_on() -> bool: return bool(get("voice_on"))
def save_voice_on(v: bool) -> None: save("voice_on", bool(v))
def get_voice() -> str: return get("voice") or ""
def save_voice(v: str) -> None: save("voice", v)
def get_rate() -> float: return float(get("rate") or 1.0)
def save_rate(v: float) -> None: save("rate", round(float(v), 2))

def get_wake_word_enabled() -> bool: return bool(get("wake_word"))
def save_wake_word_enabled(v: bool) -> None: save("wake_word", bool(v))
def get_push_to_talk_global() -> bool: return bool(get("push_to_talk_global"))

def get_dashboard_enabled() -> bool: return bool(get("dashboard"))
def save_dashboard_enabled(v: bool) -> None: save("dashboard", bool(v))

def get_plugin_enabled(name: str) -> bool: return name not in (get("plugins_disabled") or [])
