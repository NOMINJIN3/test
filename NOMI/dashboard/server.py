"""
dashboard/server.py — control NOMI from your phone.

A small web server on your local network (port 8000). Open the address NOMI
shows in Settings on your phone, type the 6-digit access code, and you can talk
to Jarvis, run skills and routines, and tick off tasks — the desktop app does the
work and speaks the answers.

Python standard library only: nothing extra to install. Off until you turn it
on in Settings → Phone dashboard. The code changes every time it starts, wrong
codes are rate-limited, and sessions live only in memory.
"""
from __future__ import annotations

import json
import secrets
import socket
import threading
import time
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from config import APP_NAME, DASHBOARD_PORT
from core import undo as undo_stack
from core.log import log
from memory import config_manager as cfg

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY = 16 * 1024


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent; just picks the outgoing interface
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class Dashboard:
    def __init__(self, port: int = DASHBOARD_PORT) -> None:
        self.port = port
        self.host = None           # NomiUI, set by attach()
        self.code = ""
        self.sessions: dict[str, float] = {}
        self.failures: dict[str, list[float]] = {}
        self.live = {"q": "", "a": "", "err": "", "busy": False}
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ---- wiring to the app
    def attach(self, host) -> None:
        self.host = host
        j = host.jarvis
        j.started.connect(lambda q: self.live.update(q=q, a="", err="", busy=True))
        j.text.connect(lambda t: self.live.update(a=t))
        j.finished.connect(lambda t, note: self.live.update(a=t, busy=False))
        j.failed.connect(lambda msg, partial: self.live.update(a=partial, err="" if msg == "Stopped." else msg, busy=False))

    def on_main(self, fn):
        """Run fn on the Qt main thread (where all NOMI state lives) and return its result."""
        return self.host.jarvis.main.run(fn)

    # ---- lifecycle
    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def url(self) -> str:
        return f"http://{lan_ip()}:{self.port}"

    def start(self) -> bool:
        if self.running:
            return True
        self.code = f"{secrets.randbelow(1_000_000):06d}"
        self.sessions.clear()
        dash = self

        class Handler(_Handler):
            dashboard = dash

        try:
            self._server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as e:
            log(f"⚠ Port {self.port} is busy ({e}). Set NOMI_DASHBOARD_PORT in .env to use another.", "DASHBOARD")
            self._server = None
            return False
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        log(f"📱 {self.url} — access code {self.code}", "DASHBOARD")
        return True

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
            self.sessions.clear()
            log("📱 Stopped", "DASHBOARD")

    # ---- auth
    def check_code(self, ip: str, code: str) -> str | None:
        now = time.time()
        recent = [t for t in self.failures.get(ip, []) if now - t < 60]
        if len(recent) >= 5:
            return None
        if secrets.compare_digest(code.strip(), self.code):
            token = secrets.token_urlsafe(24)
            self.sessions[token] = now
            self.failures.pop(ip, None)
            log(f"📱 Phone connected from {ip}", "DASHBOARD")
            return token
        self.failures[ip] = recent + [now]
        return None

    def locked_out(self, ip: str) -> bool:
        now = time.time()
        return len([t for t in self.failures.get(ip, []) if now - t < 60]) >= 5

    # ---- what the phone sees
    def state(self) -> dict:
        def snap():
            s = self.host.store
            return {
                "app": APP_NAME, "user": cfg.get_user_name(), "family": cfg.get_family_name(),
                "online": self.host.jarvis.problem() is None, "problem": self.host.jarvis.problem(),
                "tasks": [{"id": t["id"], "text": t["text"], "done": t["done"]} for t in s.todos[:40]],
                "skills": [{"id": k["id"], "name": k["name"], "model": k.get("model", ""), "effort": k.get("effort", "")} for k in s.skills],
                "routines": [{"id": r["id"], "time": r["time"], "name": r["name"]} for r in s.routines],
                "notes": [{"id": n["id"], "title": n["title"]} for n in s.notes[:20]],
                "can_undo": undo_stack.can_undo(), "undo_label": undo_stack.peek(),
            }
        data = self.on_main(snap)
        data["live"] = dict(self.live, busy=self.host.jarvis.busy)
        return data

    def act(self, path: str, body: dict) -> dict:
        h = self.host
        if path == "/api/send":
            text = str(body.get("text", "")).strip()[:2000]
            if not text:
                return {"ok": False, "error": "Type a message first."}
            if h.jarvis.busy:
                return {"ok": False, "error": "Jarvis is still answering."}
            self.on_main(lambda: h.jarvis.send(text, f"📱 {text}"))
            return {"ok": True}
        if path == "/api/stop":
            self.on_main(h.jarvis.stop)
            return {"ok": True}
        if path == "/api/skill":
            sk = self.on_main(lambda: next((x for x in h.store.skills if x["id"] == body.get("id")), None))
            if not sk:
                return {"ok": False, "error": "No such skill."}
            self.on_main(lambda: h.run_skill(sk))
            return {"ok": True}
        if path == "/api/routine":
            r = self.on_main(lambda: next((x for x in h.store.routines if x["id"] == body.get("id")), None))
            if not r:
                return {"ok": False, "error": "No such routine."}
            self.on_main(lambda: h.run_routine(r))
            return {"ok": True}
        if path == "/api/task":
            text = str(body.get("text", "")).strip()[:300]
            if not text:
                return {"ok": False, "error": "Type the task first."}
            self.on_main(lambda: h.store.add_task(text))
            return {"ok": True}
        if path == "/api/task/toggle":
            ok = self.on_main(lambda: (lambda t: t and h.store.set_task_done(t["id"], not t["done"]))(h.store.find_task(body.get("id"))))
            return {"ok": bool(ok)}
        if path == "/api/undo":
            return {"ok": True, "message": self.on_main(undo_stack.undo)}
        return {"ok": False, "error": "Unknown action."}


class _Handler(BaseHTTPRequestHandler):
    dashboard: Dashboard
    server_version = "NOMI"
    sys_version = ""

    def log_message(self, *args) -> None:  # keep the terminal quiet
        pass

    # ---- helpers
    def _ip(self) -> str:
        return self.client_address[0]

    def _token(self) -> str | None:
        c = SimpleCookie(self.headers.get("Cookie", ""))
        t = c.get("nomi")
        return t.value if t and t.value in self.dashboard.sessions else None

    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict, status: int = 200, extra: dict | None = None) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False, default=str).encode(), "application/json; charset=utf-8", extra)

    def _page(self, name: str) -> None:
        try:
            body = (STATIC_DIR / name).read_bytes()
        except OSError:
            self._send(404, b"Not found", "text/plain")
            return
        self._send(200, body, "text/html; charset=utf-8",
                   {"Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data:"})

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > MAX_BODY:
            return {}
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    # ---- routes
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", "/app"):
            return self._page("app.html") if self._token() else self._redirect("/login")
        if path == "/login":
            return self._page("login.html")
        if path == "/api/state":
            if not self._token():
                return self._json({"error": "login"}, 401)
            return self._json(self.dashboard.state())
        self._send(404, b"Not found", "text/plain")

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        # simple same-origin check against cross-site form posts
        origin = self.headers.get("Origin")
        if origin and origin.split("://", 1)[-1] != self.headers.get("Host", ""):
            return self._json({"error": "Bad origin"}, 403)
        if path == "/api/login":
            if self.dashboard.locked_out(self._ip()):
                return self._json({"ok": False, "error": "Too many tries. Wait a minute."}, 429)
            token = self.dashboard.check_code(self._ip(), str(self._body().get("code", "")))
            if not token:
                return self._json({"ok": False, "error": "That code isn't right. It's shown in NOMI → Settings."}, 401)
            return self._json({"ok": True}, extra={"Set-Cookie": f"nomi={token}; HttpOnly; SameSite=Strict; Path=/"})
        if path == "/api/logout":
            t = self._token()
            if t:
                self.dashboard.sessions.pop(t, None)
            return self._json({"ok": True}, extra={"Set-Cookie": "nomi=; Max-Age=0; Path=/"})
        if not self._token():
            return self._json({"error": "login"}, 401)
        try:
            return self._json(self.dashboard.act(path, self._body()))
        except Exception as e:
            log(f"⚠ {path}: {e}", "DASHBOARD")
            return self._json({"ok": False, "error": "Something went wrong."}, 500)

    def _redirect(self, to: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", to)
        self.send_header("Content-Length", "0")
        self.end_headers()
