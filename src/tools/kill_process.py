"""根据 PID 安全终止进程工具。"""

from __future__ import annotations

import os
import signal
import time
from typing import Any

from src.core import logging as structured_logging
from src.registry import mcp


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@mcp.tool(
    name="kill_process",
    description=(
        "Terminate a process by PID with safety checks (replaces shell 'kill' and 'pkill -9').\n"
        "Parameters:\n"
        "- pid (int): The target process ID to terminate.\n"
        "- force (bool, default: False): If False, sends SIGTERM first and waits up to timeout before falling back to SIGKILL; if True, immediately sends SIGKILL.\n"
        "- timeout (float, default: 3.0): Seconds to wait for graceful exit before forceful kill.\n"
        "Safety guardrails: Strictly prevents killing the MCP server process itself, its parent daemon, or system PID 1/0.\n"
        "Usage guideline: Use this after find_process to cleanly free stuck ports or terminate unresponsive background tasks."
    ),
    annotations={"destructiveHint": True},
)
def kill_process(
    pid: int,
    force: bool = False,
    timeout: float = 3.0,
) -> dict[str, Any]:
    start = time.time()
    target_pid = int(pid)
    self_pid = os.getpid()

    # 1. 安全保护检查
    if target_pid in (0, 1):
        return {
            "status": "error",
            "pid": target_pid,
            "error": "Safety guardrail: cannot kill init/system root processes (PID 0 or 1).",
            "duration": 0.0,
        }

    if target_pid == self_pid:
        return {
            "status": "error",
            "pid": target_pid,
            "error": "Safety guardrail: cannot kill the MCP server process itself.",
            "duration": 0.0,
        }

    # 检查进程是否存在
    if not _is_pid_alive(target_pid):
        return {
            "status": "error",
            "pid": target_pid,
            "error": f"Process PID {target_pid} does not exist or has already exited.",
            "duration": round(time.time() - start, 4),
        }

    try:
        if force:
            os.kill(target_pid, signal.SIGKILL)
            method_used = "SIGKILL"
        else:
            # 优雅发送 SIGTERM
            os.kill(target_pid, signal.SIGTERM)
            method_used = "SIGTERM"

            # 轮询等待进程优雅退出
            deadline = time.time() + max(0.5, float(timeout))
            killed = False
            while time.time() < deadline:
                if not _is_pid_alive(target_pid):
                    killed = True
                    break
                time.sleep(0.1)

            if not killed and _is_pid_alive(target_pid):
                # 超时强杀
                os.kill(target_pid, signal.SIGKILL)
                method_used = "SIGTERM_then_SIGKILL"

        duration = round(time.time() - start, 4)
        structured_logging.structured(
            "kill_process_success",
            pid=target_pid,
            signal=method_used,
            duration=duration,
        )

        return {
            "status": "success",
            "pid": target_pid,
            "signal": method_used,
            "duration": duration,
        }

    except ProcessLookupError:
        return {
            "status": "success",
            "pid": target_pid,
            "signal": "already_exited",
            "duration": round(time.time() - start, 4),
        }
    except PermissionError as e:
        return {
            "status": "error",
            "pid": target_pid,
            "error": f"Permission denied: {e}",
            "duration": round(time.time() - start, 4),
        }
    except Exception as e:
        return {
            "status": "error",
            "pid": target_pid,
            "error": str(e),
            "duration": round(time.time() - start, 4),
        }
