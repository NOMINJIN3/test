"""Wake word: listens in the background for "Hey Jarvis".

Saying just "Hey Jarvis" emits `wake` (NOMI answers "Yes?" and listens);
"Hey Jarvis, add a task to call mum" emits `command` with the rest of the sentence.
It pauses while Jarvis is talking (so he never wakes himself) and during push-to-talk.
"""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QObject, Signal

from config import SPEECH_LANG, WAKE_WORDS
from core.log import log
from core.stt import sr


class WakeWord(QObject):
    wake = Signal()
    command = Signal(str)
    stopped = Signal(str)

    def __init__(self, ears, voice) -> None:
        super().__init__()
        self.ears, self.voice = ears, voice
        self._lock = ears._lock          # shared with push-to-talk: one user of the mic at a time
        self._wake_on = False
        self._wake_thread: threading.Thread | None = None

    @property
    def on(self) -> bool:
        return self._wake_on

    def available(self) -> bool:
        return self.ears.available()

    def set(self, on: bool) -> bool:
        self._wake_on = bool(on) and self.ears.available()
        if self._wake_on and not (self._wake_thread and self._wake_thread.is_alive()):
            self._wake_thread = threading.Thread(target=self._wake_loop, daemon=True)
            self._wake_thread.start()
        log("👂 Wake word on — say \"Hey Jarvis\"" if self._wake_on else "👂 Wake word off")
        return self._wake_on

    def _wake_loop(self) -> None:
        r = sr.Recognizer()
        r.dynamic_energy_threshold = True
        calibrated = False
        while self._wake_on:
            if self.voice.busy or not self._lock.acquire(timeout=0.2):
                time.sleep(0.3)  # don't listen to Jarvis himself, or during push-to-talk
                continue
            try:
                with sr.Microphone() as source:
                    if not calibrated:
                        r.adjust_for_ambient_noise(source, duration=0.8)
                        calibrated = True
                    audio = r.listen(source, timeout=1.5, phrase_time_limit=6)
                text = r.recognize_google(audio, language=SPEECH_LANG).strip()
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                continue
            except sr.RequestError:
                time.sleep(3)
                continue
            except (OSError, AttributeError):
                self._wake_on = False
                self.stopped.emit("no_mic")
                break
            finally:
                if self._lock.locked():
                    self._lock.release()
            low = text.lower()
            for w in WAKE_WORDS:
                i = low.find(w)
                if i != -1:
                    cmd = text[i + len(w):].strip(" ,.!?")
                    (self.command.emit(cmd) if cmd else self.wake.emit())
                    break
