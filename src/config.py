"""全局配置与运行环境定义。"""

from __future__ import annotations

import os

# 服务监听配置
HOST: str = os.environ.get("HOST", "0.0.0.0")
PORT: int = int(os.environ.get("PORT", 3000))

# 可选访问令牌：设置后 MCP 端点要求 Authorization: Bearer <token>
AUTH_TOKEN: str = os.environ.get("MCP_AUTH_TOKEN", "").strip()

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
