"""进程发现与监听端口排查工具。"""

from __future__ import annotations

import os
import time
from typing import Any

from src.core import logging as structured_logging
from src.registry import mcp


def _get_listening_inodes_for_port(target_port: int) -> set[str]:
    """从 /proc/net/tcp 与 /proc/net/tcp6 解析监听该端口的 socket inode。"""
    matching_inodes = set()
    hex_port = f"{target_port:04X}"

    for proc_net_file in ("/proc/net/tcp", "/proc/net/tcp6"):
        if not os.path.exists(proc_net_file):
            continue
        try:
            with open(proc_net_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            for line in lines[1:]:
                fields = line.strip().split()
                if len(fields) >= 10:
                    local_addr = fields[1]
                    state = fields[3]
                    inode = fields[9]
                    # state "0A" 表示 TCP_LISTEN
                    if state == "0A" and local_addr.endswith(f":{hex_port}"):
                        matching_inodes.add(inode)
        except Exception:
            pass

    return matching_inodes


def _find_pids_by_socket_inodes(target_inodes: set[str]) -> set[int]:
    """通过扫描 /proc/{pid}/fd 找到持有对应 socket inode 的进程 PID。"""
    matched_pids = set()
    if not target_inodes:
        return matched_pids

    target_patterns = {f"socket:[{inode}]" for inode in target_inodes}

    proc_entries = [d for d in os.listdir("/proc") if d.isdigit()]
    for pid_str in proc_entries:
        fd_dir = f"/proc/{pid_str}/fd"
        if not os.path.exists(fd_dir):
            continue
        try:
            for fd in os.listdir(fd_dir):
                fd_path = os.path.join(fd_dir, fd)
                try:
                    target = os.readlink(fd_path)
                    if target in target_patterns:
                        matched_pids.add(int(pid_str))
                        break
                except (OSError, PermissionError):
                    continue
        except (OSError, PermissionError):
            continue

    return matched_pids


@mcp.tool(
    name="find_process",
    description=(
        "Find running processes by listening network port or command name keyword (replaces shell 'lsof -i', 'netstat', and 'ps aux | grep').\n"
        "Parameters:\n"
        "- port (int, optional): Port number to check (e.g. 3000, 8080) to discover which process is occupying it.\n"
        "- name (str, optional): Case-insensitive keyword to match against process name or full cmdline arguments (e.g. 'node', 'python', 'server').\n"
        "Returns a list of matching processes with:\n"
        "- pid: Integer process ID.\n"
        "- name: Process executable name.\n"
        "- cmdline: Full command line string.\n"
        "Usage guideline: ALWAYS use this tool before starting network services to check for port conflicts, or when verifying whether a background service is running."
    ),
    annotations={"readOnlyHint": True},
)
def find_process(port: int | None = None, name: str | None = None) -> dict[str, Any]:
    start = time.time()

    target_pids_from_port: set[int] | None = None
    if port is not None:
        inodes = _get_listening_inodes_for_port(int(port))
        target_pids_from_port = _find_pids_by_socket_inodes(inodes)

    matched_processes: list[dict[str, Any]] = []
    name_needle = name.strip().lower() if name else None

    proc_entries = [d for d in os.listdir("/proc") if d.isdigit()]

    for pid_str in proc_entries:
        pid = int(pid_str)

        # 端口过滤
        if target_pids_from_port is not None and pid not in target_pids_from_port:
            continue

        pid_dir = f"/proc/{pid_str}"
        comm_file = os.path.join(pid_dir, "comm")
        cmdline_file = os.path.join(pid_dir, "cmdline")

        proc_name = ""
        if os.path.exists(comm_file):
            try:
                with open(comm_file, "r", encoding="utf-8", errors="ignore") as f:
                    proc_name = f.read().strip()
            except Exception:
                pass

        full_cmdline = ""
        if os.path.exists(cmdline_file):
            try:
                with open(cmdline_file, "r", encoding="utf-8", errors="ignore") as f:
                    raw_cmd = f.read()
                    full_cmdline = " ".join(raw_cmd.split("\x00")).strip()
            except Exception:
                pass

        display_cmd = full_cmdline if full_cmdline else proc_name

        # 名称/命令行关键字过滤
        if name_needle:
            if (
                name_needle not in proc_name.lower()
                and name_needle not in display_cmd.lower()
            ):
                continue

        # 避免返回自身或空行
        matched_processes.append({
            "pid": pid,
            "name": proc_name,
            "cmdline": display_cmd,
        })

    matched_processes.sort(key=lambda x: x["pid"])
    duration = round(time.time() - start, 4)

    structured_logging.structured(
        "find_process_called",
        port=port,
        name=name,
        matches_found=len(matched_processes),
        duration=duration,
    )

    return {
        "status": "success",
        "port": port,
        "name_filter": name,
        "count": len(matched_processes),
        "processes": matched_processes,
        "duration": duration,
    }
