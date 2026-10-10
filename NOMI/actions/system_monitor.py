"""The time, and how this computer is doing (CPU, memory, disk, battery, uptime)."""
from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime

try:
    import psutil
except Exception:
    psutil = None

_START = time.time()


def get_time():
    d = datetime.now().astimezone()
    return {"iso": d.isoformat(timespec="minutes"), "weekday": d.strftime("%A"), "timezone": str(d.tzinfo)}


def get_system_status():
    disk = shutil.disk_usage(os.path.expanduser("~"))
    up = int(time.time() - _START)
    info = {
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "cpus": os.cpu_count(),
        "disk_free_gb": round(disk.free / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "nomi_uptime": f"{up // 3600}h {up // 60 % 60}m",
    }
    if psutil:
        info["cpu_percent"] = psutil.cpu_percent(interval=0.3)
        vm = psutil.virtual_memory()
        info["memory_used_percent"] = vm.percent
        info["memory_total_gb"] = round(vm.total / 1e9, 1)
        try:
            b = psutil.sensors_battery()
            if b:
                info["battery_percent"] = round(b.percent)
                info["charging"] = bool(b.power_plugged)
        except Exception:
            pass
    else:
        try:
            info["load_avg_1m"] = round(os.getloadavg()[0], 2)
        except (AttributeError, OSError):
            pass
    return info


TOOLS = [
    {"name": "get_time", "description": "Current local date, weekday, time and time zone.",
     "parameters": {"type": "object", "properties": {}}, "handler": get_time},
    {"name": "get_system_status", "description": "This computer's OS, CPU and memory use, disk space, battery and NOMI's uptime.",
     "parameters": {"type": "object", "properties": {}}, "handler": get_system_status},
]
