# config/__init__.py
"""NOMI settings. Values come from the environment / the .env file next to main.py.

User preferences that change at runtime (name, voice, wake word …) live in
memory/config_manager.py instead; this file is for things fixed at launch.
"""
from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent
ICON_PATH = CONFIG_DIR / "nomi.ico"

try:  # .env next to main.py
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

APP_NAME = "NOMI"
VERSION = "4.0"

# ── where data lives ──────────────────────────────────────────────────────────
DATA_DIR = Path(os.environ.get("NOMI_HOME", Path.home() / ".nomi")).expanduser()
LEGACY_DATA_DIR = Path.home() / ".myos"          # earlier builds; migrated once
STATE_FILE = DATA_DIR / "memory.json"
CONFIG_FILE = DATA_DIR / "config.json"
LOG_FILE = DATA_DIR / "nomi.log"

# ── Jarvis (Claude API) ───────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_MODEL = os.environ.get("JARVIS_MODEL", "claude-sonnet-5-5")
MAX_TOKENS = int(os.environ.get("JARVIS_MAX_TOKENS", "2048"))
MAX_ROUNDS = 8                                   # tool rounds per message
THINKING_BUDGET = {"high": 2048, "xhigh": 6000, "max": 12000}

MODELS = [  # key, label, API model id, tier
    ("haiku", "Haiku", "claude-haiku-5-5", "quick"),
    ("sonnet", "Sonnet", "claude-sonnet-5-5", "default"),
    ("opus", "Opus", "claude-opus-5-5", "complex"),
    ("fable", "Fable", "claude-fable-5-1", "complex"),
]
EFFORTS = ["low", "medium", "high", "xhigh", "max"]

# ── voice ─────────────────────────────────────────────────────────────────────
SPEECH_LANG = os.environ.get("JARVIS_LANG", "en-US")
WAKE_WORDS = ("hey jarvis", "ok jarvis", "okay jarvis", "jarvis")

# ── remote dashboard ──────────────────────────────────────────────────────────
DASHBOARD_PORT = int(os.environ.get("NOMI_DASHBOARD_PORT", "8000"))

DEBUG = os.environ.get("NOMI_DEBUG") == "1"


def _platform_os() -> str:
    return {"Windows": "windows", "Darwin": "mac", "Linux": "linux"}.get(platform.system(), "linux")


def get_os() -> str:
    """'windows' | 'mac' | 'linux'"""
    return os.environ.get("NOMI_OS", _platform_os()).lower()


def is_windows() -> bool: return get_os() == "windows"
def is_mac() -> bool: return get_os() == "mac"
def is_linux() -> bool: return get_os() == "linux"


def migrate_legacy_data() -> bool:
    """Copy ~/.myos (earlier My OS builds) into ~/.nomi the first time NOMI runs."""
    old = LEGACY_DATA_DIR / "state.json"
    if STATE_FILE.exists() or not old.exists():
        return False
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(old, STATE_FILE)
    return True
