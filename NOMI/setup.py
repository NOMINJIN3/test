"""
NOMI setup — run once:   python setup.py

1. installs the Python packages in requirements.txt
2. creates .env and asks for your Claude API key
3. checks for a speech engine and a microphone, and says how to add what's missing

Then start NOMI with:    python main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    if sys.version_info < (3, 10):
        print(f"NOMI needs Python 3.10 or newer (this is {sys.version.split()[0]}).")
        return 1

    from core import installer  # noqa: E402  (imports config, which is stdlib-only)

    print("╔══════════════════════════════╗\n║   NOMI · Agentic OS · setup  ║\n╚══════════════════════════════╝\n")
    installer.install()

    env = installer.ensure_env_file(ask_key=True)
    print(f"\n✔ Settings file: {env}")
    if "sk-ant-..." in env.read_text(encoding="utf-8") or "ANTHROPIC_API_KEY=\n" in env.read_text(encoding="utf-8"):
        print("  ⚠ No API key yet. Open .env and set ANTHROPIC_API_KEY (from https://console.anthropic.com).")

    missing, extras = installer.check()
    if missing:
        print(f"\n✖ Still missing: {', '.join(missing)}. Check the pip output above.")
        return 1
    for line in extras:
        print(f"  · optional, not installed: {line}")
    hint = installer.voice_engine_hint()
    if hint:
        print(f"  · Jarvis needs a voice on Linux:  {hint}")
    pa = installer.portaudio_hint()
    if any(e.startswith("PyAudio") for e in extras) and pa:
        print(f"  · For the microphone, install PortAudio first:  {pa}   then  pip install pyaudio")

    print("\n✔ Done. Start NOMI with:  python main.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
