"""NOMI's own settings by voice: Jarvis's voice on/off and speed, the wake word, and undo."""
from __future__ import annotations


def set_voice(parameters: dict, store, voice):
    on = bool(parameters.get("on", True))
    store.set_setting("voice_on", on)
    if not on:
        voice.stop()
    return "Voice on." if on else "Voice off."


def set_speech_rate(parameters: dict, store):
    try:
        rate = max(0.7, min(1.4, float(parameters.get("rate", 1.0))))
    except (TypeError, ValueError):
        return "Rate must be a number between 0.7 and 1.4."
    store.set_setting("rate", round(rate, 2))
    return f"Speaking speed set to {rate:.2f}×."


def set_wake_word(parameters: dict, host):
    on = host.set_wake(bool(parameters.get("on", True)))
    return "Listening for “Hey Jarvis”." if on else "Wake word off (or no microphone available)."


def undo_last(undo):
    return undo.undo()


TOOLS = [
    {"name": "set_voice", "description": "Turn Jarvis's spoken replies on or off.",
     "parameters": {"type": "object", "properties": {"on": {"type": "boolean"}}, "required": ["on"]}, "handler": set_voice},
    {"name": "set_speech_rate", "description": "Change how fast Jarvis speaks (0.7 slow to 1.4 fast, 1.0 normal).",
     "parameters": {"type": "object", "properties": {"rate": {"type": "number"}}, "required": ["rate"]}, "handler": set_speech_rate},
    {"name": "set_wake_word", "description": "Turn the background “Hey Jarvis” wake word on or off.",
     "parameters": {"type": "object", "properties": {"on": {"type": "boolean"}}, "required": ["on"]}, "handler": set_wake_word},
    {"name": "undo", "description": "Take back the last change made to tasks, notes, routines, skills or reminders.",
     "parameters": {"type": "object", "properties": {}}, "handler": undo_last},
]
