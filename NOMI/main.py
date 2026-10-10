import platform as _platform
import subprocess as _subprocess

# ── No console flashes on Windows ───────────────────────────────────────────
# Jarvis speaks through PowerShell on Windows. Without this, every sentence
# would pop a black console window for a split second. Patching Popen once
# here covers every subprocess call in the app, so no file needs its own flag.
if _platform.system() == "Windows":
    _OrigPopen = _subprocess.Popen

    class _Popen(_OrigPopen):
        def __init__(self, args, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _subprocess.CREATE_NO_WINDOW
            kw.pop("startupinfo", None)   # drop any stale/shared STARTUPINFO
            super().__init__(args, **kw)

    _subprocess.Popen = _Popen


# ── Console must survive non-UTF-8 code pages ───────────────────────────────
# Every status line carries an emoji (🎤 🔊 🧠). On a legacy Windows console the
# active code page is the system one — cp1251 in Russia and Mongolia, cp932 in
# Japan — and printing an emoji there raises UnicodeEncodeError. Reconfiguring
# to UTF-8 with a replacement fallback costs nothing and makes NOMI start the
# same way in every locale.
import sys as _sys

for _stream in ("stdout", "stderr"):
    try:
        _s = getattr(_sys, _stream, None)
        if _s is not None and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass          # pythonw / redirected pipes / anything exotic — never fatal

# ─────────────────────────────────────────────────────────────────────────────

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))  # run from anywhere

from config import APP_NAME, DATA_DIR, VERSION, migrate_legacy_data  # noqa: E402  (loads .env)
from core import installer  # noqa: E402
from core.log import log  # noqa: E402


def main() -> int:
    log(f"{APP_NAME} {VERSION} starting on {_platform.system()} · Python {_platform.python_version()}", "BOOT")

    missing, extras = installer.check()
    if missing:
        log(f"⚠ Missing packages: {', '.join(missing)}. Run:  python setup.py", "BOOT")
        return 1
    for line in extras:
        log(f"optional, not installed: {line}", "BOOT")
    hint = installer.voice_engine_hint()
    if hint:
        log(f"⚠ No speech engine — Jarvis will stay silent. Install one with:  {hint}", "BOOT")

    if migrate_legacy_data():
        log("💾 Brought over your notes and tasks from the earlier My OS build (~/.myos)", "MEMORY")
    log(f"Data folder: {DATA_DIR}", "BOOT")

    from core.action_loader import ActionRegistry, discover_actions
    from core.plugin_loader import discover_plugins
    from core import audio_devices

    registry = ActionRegistry()
    n = discover_actions(registry, BASE_DIR / "actions")
    discover_plugins(registry, BASE_DIR / "plugins")
    log(f"🛠 {n} actions + {len(registry.records) - n} plugin tools ready", "BOOT")
    audio_devices.report()

    from PySide6.QtWidgets import QApplication

    import ui
    from dashboard.server import Dashboard
    from memory import config_manager as cfg

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    ui.Fonts.init()
    app.setFont(ui.font("body", 10))
    app.setStyleSheet(ui.stylesheet())

    dashboard = Dashboard()
    window = ui.NomiUI(registry, dashboard)
    dashboard.attach(window)
    if cfg.get_dashboard_enabled():
        dashboard.start()
    window.show()

    code = app.exec()
    log(f"Exited with code {code}", "BOOT")
    return code


if __name__ == "__main__":
    sys.exit(main())
