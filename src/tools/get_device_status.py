"""获取设备硬件与运行状态感知工具。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any

from src.config import TERMUX_HOME
from src.core import logging as structured_logging
from src.registry import mcp


def _get_storage_info() -> dict[str, Any]:
    try:
        stat = os.statvfs(TERMUX_HOME)
        total_bytes = stat.f_blocks * stat.f_frsize
        free_bytes = stat.f_bavail * stat.f_frsize
        used_bytes = total_bytes - free_bytes
        total_gb = round(total_bytes / (1024**3), 2)
        free_gb = round(free_bytes / (1024**3), 2)
        used_gb = round(used_bytes / (1024**3), 2)
        percent = round((used_bytes / total_bytes) * 100, 1) if total_bytes > 0 else 0.0
        return {
            "total_gb": total_gb,
            "free_gb": free_gb,
            "used_gb": used_gb,
            "used_percent": percent,
        }
    except Exception as e:
        return {"error": str(e)}


def _get_memory_info() -> dict[str, Any]:
    try:
        meminfo: dict[str, int] = {}
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        if val.isdigit():
                            meminfo[key] = int(val)

        total_kb = meminfo.get("MemTotal", 0)
        avail_kb = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
        used_kb = total_kb - avail_kb if total_kb >= avail_kb else 0

        total_mb = round(total_kb / 1024, 1)
        avail_mb = round(avail_kb / 1024, 1)
        used_mb = round(used_kb / 1024, 1)
        used_percent = round((used_kb / total_kb) * 100, 1) if total_kb > 0 else 0.0

        return {
            "total_mb": total_mb,
            "available_mb": avail_mb,
            "used_mb": used_mb,
            "used_percent": used_percent,
        }
    except Exception as e:
        return {"error": str(e)}


def _get_battery_info() -> dict[str, Any] | None:
    battery_bin = shutil.which("termux-battery-status")
    if not battery_bin:
        return None
    try:
        res = subprocess.run(
            [battery_bin],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout)
            return {
                "percentage": data.get("percentage"),
                "status": data.get("status"),  # e.g. "CHARGING", "DISCHARGING"
                "health": data.get("health"),
                "temperature": data.get("temperature"),
                "plugged": data.get("plugged"),  # e.g. "PLUGGED_AC", "PLUGGED_USB"
            }
    except Exception:
        pass
    return None


@mcp.tool(
    name="get_device_status",
    description=(
        "Query current Android/Termux device health and hardware metrics before dispatching resource-heavy operations.\n"
        "- Storage: Termux partition total, free, and used capacity in GB and usage percentage.\n"
        "- Memory (RAM): Total, available, and used memory in MB and utilization percentage.\n"
        "- CPU: Available CPU core count and system load average.\n"
        "- Battery: Real-time battery percentage, charging status, and plug type (via termux-battery-status if available).\n"
        "Usage guideline: Call this tool when planning memory-intensive tasks (compilation, heavy test suites) or long-running tasks to prevent Out-Of-Memory (OOM) kills or device shutdown."
    ),
    annotations={"readOnlyHint": True},
)
def get_device_status() -> dict[str, Any]:
    start = time.time()
    storage = _get_storage_info()
    memory = _get_memory_info()
    battery = _get_battery_info()

    cpu_count = os.cpu_count() or 1
    try:
        load_avg = list(os.getloadavg())
    except (AttributeError, OSError):
        load_avg = []

    duration = round(time.time() - start, 4)

    res = {
        "status": "success",
        "storage": storage,
        "memory": memory,
        "cpu": {
            "cores": cpu_count,
            "load_avg": load_avg,
        },
        "battery": battery,
        "duration": duration,
    }

    structured_logging.structured("get_device_status_called", duration=duration)
    return res
