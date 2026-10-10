"""LLM client: Jarvis's brain.

Talks to Claude through the Anthropic API, streams the answer sentence by sentence
(so Jarvis can start speaking at once), and runs the tool loop over the action
registry (actions/ + plugins/). The system prompt is core/prompt.txt.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

try:
    import anthropic
except ImportError:
    anthropic = None

from pathlib import Path

from config import ANTHROPIC_API_KEY, DEFAULT_MODEL, MAX_ROUNDS, MAX_TOKENS, THINKING_BUDGET
from core.log import log
from memory import config_manager as cfg
from memory.memory_manager import Store

PROMPT_FILE = Path(__file__).with_name("prompt.txt")


class _MainThread(QObject):
    """Runs a function on the Qt main thread and hands the result back to a worker."""

    _call = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._call.connect(lambda job: job())

    def run(self, fn: Callable[[], Any]) -> Any:
        done = threading.Event()
        box: dict = {}

        def job():
            try:
                box["value"] = fn()
            except Exception as e:  # reported back to Claude as a tool error
                box["error"] = e
            finally:
                done.set()

        self._call.emit(job)
        done.wait(30)
        if "error" in box:
            raise box["error"]
        return box.get("value")


class Jarvis(QObject):
    started = Signal(str)          # label shown above the answer
    text = Signal(str)             # whole answer so far (streams)
    finished = Signal(str, str)    # answer, note
    failed = Signal(str, str)      # message, partial answer
    busy_changed = Signal(bool)

    def __init__(self, store: Store, voice, host, registry) -> None:
        super().__init__()
        self.store, self.voice, self.host = store, voice, host
        self.main = _MainThread()
        self.busy = False
        self._cancel = threading.Event()
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if (anthropic and ANTHROPIC_API_KEY) else None
        self.registry = registry
        log("Connected." if self.client else f"⚠ Offline: {self.problem()}")

    def problem(self) -> str | None:
        if anthropic is None:
            return "The anthropic package isn't installed. Run: pip install -r requirements.txt"
        if self.client is None:
            return "Add your ANTHROPIC_API_KEY to the .env file next to main.py (or run python setup.py), then restart NOMI."
        return None

    # ------------------------------------------------------------------ prompt
    def system_prompt(self) -> str:
        """core/prompt.txt with {placeholders} filled from the live system, so renaming
        yourself, adding a plugin or changing apps is known to Jarvis immediately."""
        st = self.store
        try:
            template = PROMPT_FILE.read_text(encoding="utf-8")
        except Exception:
            template = "You are {assistant}, the assistant running {app}. Be concise."
        values = {
            "assistant": cfg.get_assistant_name(),
            "app": "NOMI",
            "user": cfg.get_user_name(),
            "family": cfg.get_family_name(),
            "now": datetime.now().astimezone().strftime("%A %d %B %Y, %H:%M %Z"),
            "apps": ", ".join(self.host.app_names()),
            "tools": ", ".join(self.registry.names()),
            "open_tasks": sum(not t["done"] for t in st.todos),
            "notes": len(st.notes),
            "routines": len(st.data["routines"]),
            "skills": len(st.skills),
        }
        for k, v in values.items():
            template = template.replace("{" + k + "}", str(v))
        return template.strip()

    # ------------------------------------------------------------------ tools
    def tool_specs(self) -> list[dict]:
        return self.registry.declarations()

    def run_tool(self, name: str, args: dict):
        log(f"🛠 {name} {args if args else ''}".rstrip())
        return self.registry.run(name, args)

    # ------------------------------------------------------------------ talking
    def send(self, text: str, label: str | None = None, skill: dict | None = None) -> None:
        text = (text or "").strip()
        if not text or self.busy:
            return
        if self.problem():
            self.started.emit(label or text)
            self.failed.emit(self.problem(), "")
            self.voice.say(self.problem(), interrupt=True)
            return
        self.busy = True
        self._cancel.clear()
        self.voice.stop()
        shown = label or text
        if skill:
            m, e = self.store.skill_cfg(skill)
            shown += f" · {m['label']} · {e}"
        self.store.push_turn("user", text)
        self.store.bump()
        self.started.emit(shown)
        self.busy_changed.emit(True)
        log(f"🧠 Thinking: {shown[:60]}")
        threading.Thread(target=self._work, args=(skill,), daemon=True).start()

    def stop(self) -> None:
        self._cancel.set()
        self.voice.stop()

    def _messages(self) -> list[dict]:
        out: list[dict] = []
        for t in self.store.turns[-20:]:
            if out and out[-1]["role"] == t["role"]:
                out[-1]["content"] += "\n\n" + t["content"]
            else:
                out.append({"role": t["role"], "content": t["content"]})
        while out and out[0]["role"] != "user":
            out.pop(0)
        return out

    def _work(self, skill: dict | None) -> None:
        model, effort, note = DEFAULT_MODEL, "medium", ""
        if skill:
            m, effort = self.store.skill_cfg(skill)
            model = m["id"]
        messages = self._messages()
        full, spoken = "", 0
        use_thinking = effort in THINKING_BUDGET
        try:
            for _ in range(MAX_ROUNDS):
                kwargs: dict = {"model": model, "max_tokens": MAX_TOKENS, "system": self.system_prompt(),
                                "messages": messages, "tools": self.tool_specs()}
                if use_thinking:
                    budget = THINKING_BUDGET[effort]
                    kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
                    kwargs["max_tokens"] = budget + MAX_TOKENS
                try:
                    final, full, spoken = self._stream(kwargs, full, spoken)
                except anthropic.NotFoundError:
                    if model == DEFAULT_MODEL:
                        raise
                    note = f"{model} isn't available on this API key, so I used {DEFAULT_MODEL}."
                    model = DEFAULT_MODEL
                    continue
                except anthropic.BadRequestError as e:
                    if use_thinking and "thinking" in str(e).lower():
                        use_thinking = False  # this model doesn't take extended thinking
                        continue
                    raise
                if final is None:  # stopped
                    break
                if final.stop_reason != "tool_use":
                    break
                messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in final.content]})
                results = []
                for b in final.content:
                    if b.type != "tool_use":
                        continue
                    try:
                        out = self.main.run(lambda b=b: self.run_tool(b.name, dict(b.input or {})))
                        results.append({"type": "tool_result", "tool_use_id": b.id,
                                        "content": out if isinstance(out, str) else json.dumps(out, ensure_ascii=False, default=str)})
                    except Exception as e:
                        results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"Error: {e}", "is_error": True})
                messages.append({"role": "user", "content": results})
            if self._cancel.is_set():
                self._finish_fail("Stopped.", full)
                return
            if not full.strip():
                full = "Done."
                self.text.emit(full)
            if full[spoken:].strip():
                self.voice.say(full[spoken:])
            self.store_turn(full)
            log(f"💬 Answered ({len(full)} chars)")
            self.finished.emit(full, note)
        except Exception as e:
            self._finish_fail(self._error_text(e), full)
        finally:
            self.busy = False
            self.busy_changed.emit(False)

    def _stream(self, kwargs: dict, full: str, spoken: int):
        """One API round, streamed. Speaks finished sentences as they arrive."""
        prefix = "\n\n" if full.strip() else ""
        first = True
        with self.client.messages.stream(**kwargs) as stream:
            for chunk in stream.text_stream:
                if self._cancel.is_set():
                    return None, full, spoken
                if first and chunk:
                    full += prefix
                    first = False
                full += chunk
                self.text.emit(full)
                m = re.match(r"^[\s\S]*[.!?](?=\s)", full[spoken:])
                if m and m.group(0).strip():
                    self.voice.say(m.group(0))
                    spoken += len(m.group(0))
            return stream.get_final_message(), full, spoken

    def store_turn(self, text: str) -> None:
        self.main.run(lambda: self.store.push_turn("assistant", text))

    def _finish_fail(self, message: str, partial: str) -> None:
        if partial.strip():
            self.store_turn(partial)
        else:  # drop the unanswered question so the conversation stays balanced
            def pop():
                if self.store.turns and self.store.turns[-1]["role"] == "user":
                    self.store.turns.pop()
                    self.store.touch("turns")
            self.main.run(pop)
        if message != "Stopped.":
            log(f"⚠ {message}")
            self.voice.say(message)
        self.failed.emit(message, partial)

    @staticmethod
    def _error_text(e: Exception) -> str:
        if anthropic is not None:
            if isinstance(e, anthropic.AuthenticationError):
                return "Your API key was rejected. Check ANTHROPIC_API_KEY in .env."
            if isinstance(e, anthropic.PermissionDeniedError):
                return "This API key isn't allowed to use that model."
            if isinstance(e, anthropic.RateLimitError):
                return "I'm being rate limited. Try again in a moment."
            if isinstance(e, anthropic.APIConnectionError):
                return "I can't reach Claude. Check your internet connection."
            if isinstance(e, anthropic.APIStatusError):
                return f"Claude returned an error ({e.status_code})."
        return f"Something went wrong: {e}"
