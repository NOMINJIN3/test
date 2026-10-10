"""Checks what NOMI needs and installs it.

`python setup.py` runs install() for you. main.py calls check() at startup so a
missing package is explained in plain words instead of a traceback.
"""
from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR

REQUIRED = {  # import name -> pip name
    "PySide6": "PySide6",
    "anthropic": "anthropic",
    "dotenv": "python-dotenv",
}
OPTIONAL = {
    "speech_recognition": ("SpeechRecognition", "microphone and wake word"),
    "pyaudio": ("PyAudio", "microphone and wake word"),
    "pynput": ("pynput", "global Ctrl+Space push-to-talk"),
    "psutil": ("psutil", "CPU and memory readouts"),
}


def _has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def check() -> tuple[list[str], list[str]]:
    """(missing required pip names, missing optional 'name — feature' lines)"""
    missing = [pip for mod, pip in REQUIRED.items() if not _has(mod)]
    extras = [f"{pip} — {why}" for mod, (pip, why) in OPTIONAL.items() if not _has(mod)]
    return missing, extras


def voice_engine_hint() -> str | None:
    system = platform.system()
    if system == "Linux" and not any(shutil.which(x) for x in ("espeak-ng", "espeak", "spd-say")):
        return "sudo apt install espeak-ng"
    return None


def portaudio_hint() -> str:
    return {"Darwin": "brew install portaudio", "Linux": "sudo apt install portaudio19-dev"}.get(platform.system(), "")


def install(include_optional: bool = True) -> int:
    req = BASE_DIR / "requirements.txt"
    print(f"▶ Installing NOMI's packages from {req.name} …")
    code = subprocess.call([sys.executable, "-m", "pip", "install", "-r", str(req)])
    if code != 0 and include_optional:
        print("\n⚠ Some packages failed (usually PyAudio, which needs PortAudio).")
        hint = portaudio_hint()
        if hint:
            print(f"  Install PortAudio with:  {hint}   then run  python setup.py  again.")
        print("  NOMI still runs without them; only the microphone is turned off.\n")
    return code


def ensure_env_file(ask_key: bool = True) -> Path:
    env, example = BASE_DIR / ".env", BASE_DIR / ".env.example"
    if env.exists():
        return env
    text = example.read_text(encoding="utf-8") if example.exists() else "ANTHROPIC_API_KEY=\n"
    if ask_key and sys.stdin.isatty():
        key = input("Paste your Claude API key (from https://console.anthropic.com), or press Enter to skip: ").strip()
        if key:
            text = text.replace("ANTHROPIC_API_KEY=sk-ant-...", f"ANTHROPIC_API_KEY={key}")
    env.write_text(text, encoding="utf-8")
    return env
