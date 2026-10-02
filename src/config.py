"""全局配置与运行环境定义。"""

from __future__ import annotations

import os

# 服务监听配置
HOST: str = os.environ.get("HOST", "0.0.0.0")
PORT: int = int(os.environ.get("PORT", 3000))

# Termux 运行环境
TERMUX_PREFIX: str = "/data/data/com.termux/files/usr"
TERMUX_HOME: str = "/data/data/com.termux/files/home"

DEFAULT_ENV: dict[str, str] = {
    **os.environ,
    "HOME": TERMUX_HOME,
    "PREFIX": TERMUX_PREFIX,
    "PATH": f"{TERMUX_PREFIX}/bin:{TERMUX_PREFIX}/bin/applets:{os.environ.get('PATH', '')}:/system/bin:/system/xbin",
    "TMPDIR": f"{TERMUX_PREFIX}/tmp",
    "LANG": "C.UTF-8",
    "TERM": "xterm-256color",
}

SHELL_BIN: str = (
    f"{TERMUX_PREFIX}/bin/bash"
    if os.path.exists(f"{TERMUX_PREFIX}/bin/bash")
    else (
        f"{TERMUX_PREFIX}/bin/sh"
        if os.path.exists(f"{TERMUX_PREFIX}/bin/sh")
        else "/system/bin/sh"
    )
)

# 高并发工作池配置
MAX_WORKERS: int = min(32, max(4, (os.cpu_count() or 2) * 4))

# 任务与输出限制
MAX_OUTPUT_BYTES: int = 50 * 1024  # 50KB 截断
TASK_COMPLETED_TTL: float = 3600.0  # 已完成任务保留 1 小时
