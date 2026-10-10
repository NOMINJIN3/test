"""Text-to-speech: Jarvis speaks one sentence at a time with the operating system's
voices — `say` on macOS, System.Speech on Windows, espeak-ng / espeak / spd-say on Linux.
"""
from __future__ import annotations

import os
import platform
import queue
import re
import shutil
import subprocess
import threading
import time

from PySide6.QtCore import QObject, Signal

from core.log import log
from memory import config_manager as cfg


# --------------------------------------------------------------------------- speaking
class Speaker:
    """Speaks one sentence at a time with the operating system's voices:
    `say` on macOS, System.Speech on Windows, espeak-ng / espeak / spd-say on Linux."""

    def __init__(self) -> None:
        self.system = platform.system()
        self._proc: subprocess.Popen | None = None

    def engine(self) -> str | None:
        if self.system == "Darwin" and shutil.which("say"):
            return "say"
        if self.system == "Windows" and shutil.which("powershell"):
            return "powershell"
        for name in ("espeak-ng", "espeak", "spd-say"):
            if shutil.which(name):
                return name
        return None

    def voices(self) -> list[dict]:
        eng = self.engine()
        try:
            if eng == "say":
                out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
                res = []
                for line in out.splitlines():
                    m = re.match(r"^(.+?)\s{2,}([a-z]{2,3}[_-][A-Za-z0-9]+)", line)
                    if m:
                        res.append({"name": m.group(1).strip(), "lang": m.group(2).replace("_", "-")})
                return res
            if eng == "powershell":
                ps = ("Add-Type -AssemblyName System.Speech;"
                      "(New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() |"
                      " ForEach-Object { $_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture.Name }")
                out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=15).stdout
                return [{"name": n, "lang": l} for n, _, l in (x.strip().partition("|") for x in out.splitlines()) if n]
            if eng in ("espeak-ng", "espeak"):
                out = subprocess.run([eng, "--voices=en"], capture_output=True, text=True, timeout=10).stdout
                res = []
                for line in out.splitlines()[1:]:
                    parts = line.split()
                    if len(parts) >= 4:
                        res.append({"name": parts[4] if len(parts) > 4 else parts[3], "lang": parts[1]})
                return res
        except Exception:
            pass
        return []

    @staticmethod
    def default_voice(voices: list[dict]) -> str:
        prefer = [v for v in voices if v["lang"].lower().startswith("en-gb")]
        for v in prefer:
            if re.search(r"daniel|arthur|george|ryan|male", v["name"], re.I):
                return v["name"]
        if prefer:
            return prefer[0]["name"]
        en = [v for v in voices if v["lang"].lower().startswith("en")]
        return en[0]["name"] if en else ""

    def speak(self, text: str, voice: str = "", rate: float = 1.0) -> None:
        """Blocks until spoken or stopped."""
        eng = self.engine()
        text = text.strip()
        if not eng or not text:
            return
        rate = max(0.5, min(2.0, float(rate or 1.0)))
        stdin_text = None
        if eng == "say":
            cmd = ["say", "-r", str(int(185 * rate))] + (["-v", voice] if voice else []) + [text]
        elif eng == "powershell":
            v = (voice or "").replace("'", "''")
            ps = ("Add-Type -AssemblyName System.Speech;"
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                  f"if ('{v}') {{ try {{ $s.SelectVoice('{v}') }} catch {{}} }};"
                  f"$s.Rate = {int(round((rate - 1) * 10))};"
                  "$s.Speak([Console]::In.ReadToEnd())")
            cmd, stdin_text = ["powershell", "-NoProfile", "-Command", ps], text
        elif eng == "spd-say":
            cmd = ["spd-say", "-w", "-r", str(int((rate - 1) * 100)), text]
        else:
            cmd = [eng, "-s", str(int(170 * rate))] + (["-v", voice] if voice else []) + [text]
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE if stdin_text else None,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
            self._proc.communicate(stdin_text, timeout=120)
        except Exception:
            self.stop()
        finally:
            self._proc = None

    def stop(self) -> None:
        p = self._proc
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass


def clean_for_speech(text: str) -> str:
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"[*_#`>|~]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    parts = re.findall(r"[^.!?;:]+[.!?;:]*|[.!?;:]+", clean_for_speech(text))
    out, buf = [], ""
    for p in parts:
        buf += p
        if len(buf) > 60 or re.search(r"[.!?]\s*$", buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


class Voice(QObject):
    """Sentence queue on a background thread. `speaking(bool)` drives the core animation."""

    speaking = Signal(bool)

    def __init__(self, store) -> None:
        super().__init__()
        self.store = store
        self.speaker = Speaker()
        self.available = self.speaker.engine() is not None
        self.voices: list[dict] = []
        self._q: queue.Queue[str | None] = queue.Queue()
        self._gen = 0  # bumps on stop() so stale sentences are skipped
        self.busy = False
        threading.Thread(target=self._run, daemon=True).start()
        threading.Thread(target=self._load_voices, daemon=True).start()
        log(f"🔊 Voice engine: {self.speaker.engine()}" if self.available else "⚠ No speech engine found (Jarvis will stay silent)")

    def _load_voices(self) -> None:
        self.voices = self.speaker.voices()
        log(f"🔊 {len(self.voices)} voices available", debug=True)
        if not cfg.get_voice():
            cfg.all_settings()["voice"] = Speaker.default_voice(self.voices)  # used now, not saved

    def say(self, text: str, interrupt: bool = False) -> None:
        if not text or not self.available or not cfg.get_voice_on():
            return
        if interrupt:
            self.stop()
        for s in split_sentences(text):
            self._q.put((self._gen, s))

    def stop(self) -> None:
        self._gen += 1
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        self.speaker.stop()

    def _run(self) -> None:
        while True:
            gen, text = self._q.get()
            if gen != self._gen:
                continue
            if not self.busy:
                self.busy = True
                self.speaking.emit(True)
            self.speaker.speak(text, cfg.get_voice(), cfg.get_rate())
            if self._q.empty():
                self.busy = False
                self.speaking.emit(False)
