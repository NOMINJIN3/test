# ⬡ NOMI · Agentic OS
### Your personal AI desktop with Jarvis — by Ts. Nominjin

NOMI is a desktop "operating system" for your day, run by **Jarvis**. Jarvis thinks
with Claude, speaks with your computer's voices, listens through your microphone
("Hey Jarvis"), and works for you: tasks, notes, reminders, skills, routines and apps.
Runs on Windows, macOS and Linux.

```
[BOOT] NOMI 4.0 starting on Linux · Python 3.12.3
[PLUGINS] 🧩 Loaded: roll
[BOOT] 🛠 24 actions + 1 plugin tools ready
[Audio] 6 input / 4 output devices found
[MEMORY] 💾 History restored (4 notes, 6 tasks, 12 exchanges)
[JARVIS] 🔊 Voice engine: espeak-ng
[JARVIS] Connected.
[JARVIS] ⌨ Global push-to-talk: Ctrl+Space
[UI] 🖥 Dashboard ready (7 apps, 4 skills, 6 routines)
[JARVIS] Briefing (greeting) sent.
```

---

## ✨ Features

| Feature | What it does |
|---|---|
| 🧠 Jarvis | Answers through Claude and streams his reply; acts on NOMI with tools, then confirms in one line |
| 🔊 Voice | Speaks each sentence the moment it's written, with your OS voices (pick voice and speed in Settings) |
| 🎙️ Push-to-talk | **Ctrl+Space** or the mic button. Global with `pynput`, inside the window without it |
| 👂 Wake word | Turn on **HEY J** and say *"Hey Jarvis, add a task to call mum"* — or just *"Hey Jarvis"* |
| ⚡ Skills Deck | One-click skills, each with its own **Model × Effort** (Haiku/Sonnet/Opus/Fable × Low…Max) |
| ◷ Routines | Daily schedule with NEXT / MISSED / DONE; click one to run it now |
| ⏰ Reminders | *"Remind me in 20 minutes to stretch"* — spoken aloud when due, kept across restarts |
| ⚠️ Real confirmation | Deleting a task or note waits for a button **you** press; Jarvis can't confirm for you |
| ↩️ Undo | *"Jarvis, undo that"*, `undo` in Terminal, or **Ctrl+Z** on the empty command bar |
| 📱 Phone dashboard | Control NOMI from your phone on the same Wi-Fi, with a 6-digit access code |
| 🗺️ System Map | Every app, routine, skill and memory drawn as rings around Jarvis, with search |
| 🧩 Plugins | Drop one `.py` into `plugins/` and Jarvis has a new skill at the next start |
| 💾 Memory | Notes, tasks, conversation and activity saved on your computer in `~/.nomi` |

---

## 📁 Project structure

```
NOMI/
├── actions/                 built-in skills — each file declares TOOL / TOOLS, found automatically
│   ├── computer_settings.py   voice on/off, speaking speed, wake word, undo
│   ├── note_manager.py        list / read / create / delete notes
│   ├── open_app.py            open and close NOMI's apps
│   ├── reminder.py            set / list / cancel reminders
│   ├── routine_manager.py     routines and Skills Deck skills
│   ├── system_monitor.py      time, CPU, memory, disk, battery
│   └── task_manager.py        list / add / complete / delete tasks
├── config/
│   ├── __init__.py            settings fixed at launch (from .env), paths, models, OS helpers
│   └── nomi.ico               app icon
├── core/
│   ├── action_loader.py       discovers actions/*.py, validates, runs tools
│   ├── audio_devices.py       lists microphones and speakers
│   ├── confirm.py             on-screen Yes / No for irreversible actions
│   ├── hotkey.py              Ctrl+Space push-to-talk (global with pynput)
│   ├── installer.py           checks and installs what NOMI needs
│   ├── llm_client.py          Claude: streaming, tool loop, model × effort, fallbacks
│   ├── log.py                 [JARVIS] status lines → terminal and ~/.nomi/nomi.log
│   ├── plugin_loader.py       discovers plugins/*.py
│   ├── prompt.txt             Jarvis's system prompt (filled from the live system)
│   ├── stt.py                 speech-to-text: push-to-talk
│   ├── tts.py                 text-to-speech: OS voices, sentence queue
│   ├── undo.py                undo stack
│   └── wake_word.py           "Hey Jarvis" in the background
├── dashboard/
│   ├── server.py              phone dashboard (standard library only)
│   └── static/                app.html, login.html
├── memory/
│   ├── config_manager.py      your preferences → ~/.nomi/config.json
│   └── memory_manager.py      notes, tasks, skills, routines, reminders, conversation → ~/.nomi/memory.json
├── plugins/
│   ├── _template.py           copy this to make a plugin
│   └── dice.py                example: "roll 2d6", coin flips, random picks
├── main.py                  start here
├── ui.py                    the whole interface (PySide6)
├── setup.py                 one-time setup: python setup.py
├── requirements.txt
├── .env.example
├── LICENSE
└── readme.md
```

---

## 🚀 Install

You need **Python 3.10+**.

```bash
git clone <this repo> NOMI
cd NOMI
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python setup.py                  # installs packages, creates .env, asks for your API key
python main.py
```

Get a Claude API key at https://console.anthropic.com. It goes in `.env` as
`ANTHROPIC_API_KEY=...` (setup.py asks for it).

**Microphone:** PyAudio needs PortAudio first —
macOS `brew install portaudio`, Linux `sudo apt install portaudio19-dev`, Windows nothing extra.
Without it NOMI runs normally; the mic and HEY J buttons just stay hidden.

**Voice on Linux:** `sudo apt install espeak-ng`. macOS and Windows already have voices.

---

## 🎮 Using NOMI

| Do this | How |
|---|---|
| Talk to Jarvis | Type in the bottom bar and press Enter. `/` jumps there from anywhere |
| Speak to Jarvis | Hold **Ctrl+Space** or click the mic |
| Wake word | **HEY J** in the bottom bar, then "Hey Jarvis, …" |
| Stop him | **STOP** (Send turns into Stop while he works) |
| Mute / unmute | Speaker button in the bottom bar |
| Skill level | ▶ on a skill card → pick model × effort → **Run** |
| Run a routine now | Click its name in Routines |
| Undo | "Jarvis, undo that", `undo` in Terminal, or Ctrl+Z on the empty command bar |
| System Map | Target icon under the title, or `map` in Terminal (Esc to go back) |
| Phone | Settings → **Phone dashboard**, then open the address on your phone and enter the code |
| See all skills | `actions` in Terminal |

---

## 🧩 Write a plugin

Copy `plugins/_template.py` to `plugins/hello.py`:

```python
PLUGIN = {
    "name": "say_hello",
    "description": "Greets someone by name.",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
}

def run(parameters, store=None, speak=None):
    return f"Hello, {parameters.get('name', 'friend')}!"
```

Restart NOMI and say "say hello to Ana". A plugin can also ask for `store`
(memory), `host` (the window), `voice`, `confirm` and `undo` by naming them.
Turn one off by adding its name to `"plugins_disabled"` in `~/.nomi/config.json`.

---

## 🔒 Good to know

- **Your data** stays on your computer in `~/.nomi` (`memory.json`, `config.json`, `nomi.log`).
  Data from the earlier My OS build (`~/.myos`) is brought over automatically once.
- **Cost:** each message is billed to your API key; every tool Jarvis uses is one more round trip.
- **Effort:** High, Xhigh and Max turn on Claude's extended thinking with growing budgets.
  A model your key can't use falls back to `JARVIS_MODEL`, with a note under the reply.
- **Speech recognition** uses Google's free recognizer, so your voice goes to Google.
  Typed messages go only to Claude.
- **Phone dashboard** is off until you turn it on. It listens on your local network,
  needs the 6-digit code (new each start), locks out after 5 wrong tries a minute,
  and stops when you close NOMI. Turn it off when you don't need it.
- **Windows:** `main.py` stops Jarvis's voice from flashing console windows, and
  switches the console to UTF-8 so the emoji status lines never crash it.

---

MIT License · © 2026 Ts. Nominjin
