"""Lists the microphones and speakers NOMI can see, for the startup log and Settings."""
from __future__ import annotations

from core.log import log

try:
    import pyaudio
except Exception:
    pyaudio = None


def list_devices() -> dict:
    """{'inputs': [names], 'outputs': [names], 'default_input': name|None, 'default_output': name|None}"""
    out = {"inputs": [], "outputs": [], "default_input": None, "default_output": None}
    if pyaudio is None:
        return out
    pa = None
    try:
        pa = pyaudio.PyAudio()
        for i in range(pa.get_device_count()):
            d = pa.get_device_info_by_index(i)
            if d.get("maxInputChannels", 0) > 0:
                out["inputs"].append(d["name"])
            if d.get("maxOutputChannels", 0) > 0:
                out["outputs"].append(d["name"])
        try:
            out["default_input"] = pa.get_default_input_device_info()["name"]
        except Exception:
            pass
        try:
            out["default_output"] = pa.get_default_output_device_info()["name"]
        except Exception:
            pass
    except Exception as e:
        log(f"⚠ Couldn't list audio devices: {e}", "Audio")
    finally:
        if pa is not None:
            try:
                pa.terminate()
            except Exception:
                pass
    return out


def report() -> dict:
    d = list_devices()
    if pyaudio is None:
        log("No PyAudio — microphone off (see readme.md to enable it)", "Audio")
    else:
        log(f"{len(d['inputs'])} input / {len(d['outputs'])} output devices found", "Audio")
        if d["default_input"]:
            log(f"input: {d['default_input']}", "Audio")
    return d
