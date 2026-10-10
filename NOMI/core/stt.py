"""Speech-to-text: push-to-talk with the default microphone."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from config import SPEECH_LANG
from core.log import log

try:
    import speech_recognition as sr
except ImportError:
    sr = None


class Ears(QObject):
    """Push-to-talk: record one phrase from the default microphone and return it as text.
    Recognition uses Google's free web recognizer, so the audio is sent to Google."""

    heard = Signal(dict)       # {"text": ...} or {"error": code}
    listening = Signal(bool)

    def __init__(self, voice) -> None:
        super().__init__()
        self.voice = voice
        self._lock = threading.Lock()

    @staticmethod
    def available() -> bool:
        if sr is None:
            return False
        try:
            return len(sr.Microphone.list_microphone_names()) > 0
        except Exception:
            return False

    def listen_once(self) -> None:
        threading.Thread(target=self._listen_once, daemon=True).start()

    def _listen_once(self) -> None:
        if sr is None:
            self.heard.emit({"error": "no_mic"})
            return
        with self._lock:
            self.voice.stop()
            self.listening.emit(True)
            log("🎤 Listening…")
            r = sr.Recognizer()
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.4)
                    audio = r.listen(source, timeout=7, phrase_time_limit=15)
                text = r.recognize_google(audio, language=SPEECH_LANG)
                log(f"🎤 Heard: {text}")
                self.heard.emit({"text": text})
            except sr.WaitTimeoutError:
                self.heard.emit({"error": "timeout"})
            except sr.UnknownValueError:
                self.heard.emit({"error": "not_understood"})
            except sr.RequestError:
                self.heard.emit({"error": "offline"})
            except (OSError, AttributeError):
                self.heard.emit({"error": "no_mic"})
            finally:
                self.listening.emit(False)
