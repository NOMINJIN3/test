"""Everything NOMI remembers: notes, tasks, skills, routines, reminders, activity
and the conversation with Jarvis. Saved as JSON in ~/.nomi/memory.json.

Preferences (name, voice, wake word …) are in config_manager.py.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from config import DATA_DIR, EFFORTS, MODELS, STATE_FILE
from core.log import log
from memory import config_manager as cfg


def now_ms() -> int:
    return int(time.time() * 1000)


def day_key(d: date | None = None) -> str:
    return (d or date.today()).isoformat()


def _defaults() -> dict:
    t = now_ms()
    return {
        "version": 1,
        "notes": [{"id": t, "title": "Welcome to NOMI", "t": t, "body": (
            "Welcome to NOMI, your Agentic OS.\n\n"
            "Type to Jarvis in the bottom bar (or press /), hold Ctrl+Space to talk, or turn on HEY J "
            "and say “Hey Jarvis”.\n\nEverything here is saved on this computer in ~/.nomi.")}],
        "todos": [
            {"id": t - 3_600_000, "text": "Say hello to Jarvis from the command bar", "done": False},
            {"id": t - 7_200_000, "text": "Run the briefing skill", "done": False},
            {"id": t - 9_000_000, "text": "Add a routine of your own", "done": False},
        ],
        "skills": [
            {"id": "s1", "name": "briefing", "model": "sonnet", "effort": "medium",
             "prompt": "Give me a briefing: check the time and my open tasks, then tell me the three things that matter most today."},
            {"id": "s2", "name": "plan-week", "model": "opus", "effort": "xhigh",
             "prompt": "Help me plan my week. Look at my tasks and notes and propose a realistic plan, day by day. Add any missing tasks you think I need."},
            {"id": "s3", "name": "clean-up", "model": "haiku", "effort": "low",
             "prompt": "Tidy my task list: complete or remove anything obviously finished or duplicated, and tell me what you changed."},
            {"id": "s4", "name": "brainstorm", "model": "fable", "effort": "high",
             "prompt": "Brainstorm 5 fresh ideas for what I could build or learn this month, based on my notes, and save the best one as a note."},
        ],
        "routines": [
            {"id": "r1", "time": "08:00", "name": "Morning briefing", "prompt": "Give me my morning briefing: tasks and one focus for the day."},
            {"id": "r2", "time": "09:00", "name": "Deep work block", "prompt": "Pick the single most important open task and help me start it."},
            {"id": "r3", "time": "13:00", "name": "Midday check-in", "prompt": "Midday check-in: what's done, what's left today, anything to reschedule?"},
            {"id": "r4", "time": "18:00", "name": "Inbox of ideas", "prompt": "Review my notes and turn any loose ideas into concrete tasks."},
            {"id": "r5", "time": "21:00", "name": "Evening review", "prompt": "Evening review: summarize what I completed today and set up tomorrow's top three tasks."},
            {"id": "r6", "time": "22:30", "name": "Tomorrow prep", "prompt": "Tell me what to prepare tonight for tomorrow."},
        ],
        "custom_apps": [],
        "activity": {},
        "routine_runs": {},
        "turns": [],
        "reminders": [],
    }


class Store(QObject):
    """Holds the data, emits `changed(section)` and saves shortly after each change."""

    changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.data = _defaults()
        self._load()
        self._save_timer = QTimer(self, singleShot=True, interval=400)
        self._save_timer.timeout.connect(self.save_now)

    # ---- persistence
    def _load(self) -> None:
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            old_settings = saved.pop("settings", None)
            for k, v in saved.items():
                self.data[k] = v
            if old_settings and not cfg.CONFIG_FILE.exists():  # earlier builds kept settings here
                for old, new in (("name", "user_name"), ("family", "family_name"), ("voice_on", "voice_on"),
                                 ("voice", "voice"), ("rate", "rate"), ("wake", "wake_word")):
                    if old in old_settings:
                        cfg.save(new, old_settings[old])
                if cfg.get("user_name") == "Commander":
                    cfg.save_user_name("Nominjin")
            log(f"💾 History restored ({len(self.data['notes'])} notes, {len(self.data['todos'])} tasks, {len(self.data['turns']) // 2} exchanges)", "MEMORY")
        except FileNotFoundError:
            log("💾 New memory created", "MEMORY")
        except Exception as e:  # keep a copy of a damaged file instead of losing it
            log(f"⚠ Couldn't read state.json, starting fresh: {e}", "MEMORY")
            try:
                STATE_FILE.rename(STATE_FILE.with_suffix(".broken.json"))
            except Exception:
                pass

    def save_now(self) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, STATE_FILE)

    def touch(self, section: str) -> None:
        self.changed.emit(section)
        self._save_timer.start()

    def reset(self) -> None:
        self.data = _defaults()
        cfg.reset()
        self.save_now()
        for s in ("settings", "notes", "todos", "skills", "routines", "apps", "activity", "turns"):
            self.changed.emit(s)

    # ---- shortcuts
    @property
    def settings(self) -> dict: return cfg.all_settings()
    @property
    def notes(self) -> list: return self.data["notes"]
    @property
    def todos(self) -> list: return self.data["todos"]
    @property
    def skills(self) -> list: return self.data["skills"]
    @property
    def routines(self) -> list: return sorted(self.data["routines"], key=lambda r: r["time"])
    @property
    def custom_apps(self) -> list: return self.data["custom_apps"]
    @property
    def turns(self) -> list: return self.data["turns"]

    def set_setting(self, key: str, value) -> None:
        cfg.save(key, value)
        self.changed.emit("settings")

    # ---- activity (Momentum panel)
    def bump(self) -> None:
        k = day_key()
        self.data["activity"][k] = self.data["activity"].get(k, 0) + 1
        self.touch("activity")

    # ---- tasks
    def add_task(self, text: str) -> dict:
        t = {"id": now_ms(), "text": text.strip()[:300], "done": False}
        self.todos.insert(0, t)
        self.touch("todos")
        return t

    def find_task(self, tid) -> dict | None:
        return next((t for t in self.todos if str(t["id"]) == str(tid)), None)

    def set_task_done(self, tid, done: bool = True) -> dict | None:
        t = self.find_task(tid)
        if t:
            if done and not t["done"]:
                self.bump()
            t["done"] = done
            self.touch("todos")
        return t

    def delete_task(self, tid) -> bool:
        n = len(self.todos)
        self.data["todos"] = [t for t in self.todos if str(t["id"]) != str(tid)]
        self.touch("todos")
        return len(self.todos) != n

    # ---- notes
    def add_note(self, title: str, body: str) -> dict:
        n = {"id": now_ms(), "title": (title or "Untitled")[:120], "body": body or "", "t": now_ms()}
        self.notes.insert(0, n)
        self.bump()
        self.touch("notes")
        return n

    def update_note(self, nid, body: str) -> None:
        n = next((x for x in self.notes if x["id"] == nid), None)
        if n:
            n["body"] = body
            first = next((l for l in body.splitlines() if l.strip()), "Untitled")
            n["title"] = first.strip()[:60]
            n["t"] = now_ms()
            self.touch("notes")

    def delete_note(self, nid) -> None:
        self.data["notes"] = [n for n in self.notes if n["id"] != nid]
        self.touch("notes")

    # ---- skills / routines / apps
    def skill_cfg(self, s: dict) -> tuple[dict, str]:
        m = next((x for x in MODELS if x[0] == s.get("model")), MODELS[1])
        e = s.get("effort") if s.get("effort") in EFFORTS else "medium"
        return {"key": m[0], "label": m[1], "id": m[2], "tier": m[3]}, e

    def add_skill(self, name: str, prompt: str, model: str = "sonnet", effort: str = "medium") -> dict:
        slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")[:30] or "skill"
        s = {"id": f"s{now_ms()}", "name": slug, "model": model, "effort": effort, "prompt": prompt}
        self.skills.append(s)
        self.touch("skills")
        return s

    def remove_skill(self, sid: str) -> None:
        self.data["skills"] = [s for s in self.skills if s["id"] != sid]
        self.touch("skills")

    def add_routine(self, time_s: str, name: str, prompt: str = "") -> dict:
        hh, mm = time_s.split(":")
        r = {"id": f"r{now_ms()}", "time": f"{int(hh):02d}:{int(mm):02d}", "name": name[:60], "prompt": prompt or name}
        self.data["routines"].append(r)
        self.touch("routines")
        return r

    def remove_routine(self, rid: str) -> None:
        self.data["routines"] = [r for r in self.data["routines"] if r["id"] != rid]
        self.touch("routines")

    def mark_routine_run(self, rid: str) -> None:
        self.data["routine_runs"][rid] = day_key()
        self.touch("routines")

    def add_custom_app(self, name: str, prompt: str) -> None:
        self.custom_apps.append({"id": f"a{now_ms()}", "name": name[:40], "prompt": prompt})
        self.touch("apps")

    # ---- reminders
    @property
    def reminders(self) -> list:
        self.data.setdefault("reminders", [])
        return self.data["reminders"]

    def add_reminder(self, due_ms: int, text: str) -> dict:
        r = {"id": f"m{now_ms()}", "due": int(due_ms), "text": text[:200]}
        self.reminders.append(r)
        self.touch("reminders")
        return r

    def remove_reminder(self, rid: str) -> None:
        self.data["reminders"] = [r for r in self.reminders if r["id"] != rid]
        self.touch("reminders")

    # ---- conversation
    def push_turn(self, role: str, content: str) -> None:
        self.turns.append({"role": role, "content": content})
        del self.turns[:-40]
        self.touch("turns")

    def clear_turns(self) -> None:
        self.turns.clear()
        self.touch("turns")


def greeting_word() -> str:
    h = datetime.now().hour
    return "morning" if h < 12 else "afternoon" if h < 18 else "evening"
