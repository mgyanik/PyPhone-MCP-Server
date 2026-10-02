"""安全的文件与目录移动、复制与删除工具。"""

from __future__ import annotations

import os
import shutil
import time
from typing import Any

from src.config import TERMUX_HOME, TERMUX_PREFIX
from src.core import logging as structured_logging
from src.registry import mcp

# 严格受保护禁止删除或移动的敏感目录清单
_FORBIDDEN_ROOTS = {
    "/",
    "/system",
    "/vendor",
    "/apex",
    "/data",
    "/data/data/com.termux",
    os.path.realpath(TERMUX_PREFIX),
    os.path.realpath(TERMUX_HOME),
}


def _is_forbidden_path(target_path: str) -> bool:
    real_path = os.path.realpath(target_path)
    if real_path in _FORBIDDEN_ROOTS:
        return True
    # 禁止父级或根级通配删除
    if real_path in ("/", "/data", "/data/data"):
        return True
    return False


@mcp.tool(
    name="manage_file",
    description=(
        "Safely move, copy, or delete files and directories without shell invocation (replaces shell 'mv', 'cp', and 'rm').\n"
        "Parameters:\n"
        "- action (str): Must be one of 'move', 'copy', or 'remove'.\n"
        "- source (str): Path to the source file or directory.\n"
        "- destination (str, optional): Target destination path (REQUIRED for 'move' and 'copy'; ignored for 'remove').\n"
        "- recursive (bool, default: False): For 'remove' on a non-empty directory, must be explicitly set to True.\n"
        "Safety guardrails: Strictly refuses operations targeting Android/Termux system roots or the home directory root itself.\n"
        "Usage guideline: ALWAYS use this tool instead of shell rm/mv/cp. It completely eliminates shell wildcard disasters and policy denials."
    ),
    annotations={"destructiveHint": True},
)
def manage_file(
    action: str,
    source: str,
    destination: str | None = None,
    recursive: bool = False,
) -> dict[str, Any]:
    start = time.time()
    act = action.strip().lower()
    norm_src = os.path.realpath(os.path.expanduser(source))

    if act not in ("move", "copy", "remove"):
        return {
            "status": "error",
            "action": action,
            "error": f"Invalid action '{action}'. Must be 'move', 'copy', or 'remove'.",
            "duration": 0.0,
        }

    if not os.path.exists(norm_src):
        return {
            "status": "error",
            "action": act,
            "source": norm_src,
            "error": f"Source path does not exist: {source}",
            "duration": round(time.time() - start, 4),
        }

    # 1. 删除操作 (remove)
    if act == "remove":
        if _is_forbidden_path(norm_src):
            return {
                "status": "error",
                "action": "remove",
                "source": norm_src,
                "error": "Safety guardrail blocked removal of protected system or root directory.",
                "duration": round(time.time() - start, 4),
            }

        try:
            if os.path.isdir(norm_src) and not os.path.islink(norm_src):
                if not recursive:
                    # 尝试 rmdir（若非空会抛出 OSError）
                    os.rmdir(norm_src)
                else:
                    shutil.rmtree(norm_src)
                item_type = "directory"
            else:
                os.remove(norm_src)
                item_type = "file"

            duration = round(time.time() - start, 4)
            structured_logging.structured(
                "manage_file_removed",
                source=norm_src,
                item_type=item_type,
                recursive=recursive,
                duration=duration,
            )
            return {
                "status": "success",
                "action": "remove",
                "source": norm_src,
                "item_type": item_type,
                "duration": duration,
            }
        except OSError as e:
            return {
                "status": "error",
                "action": "remove",
                "source": norm_src,
                "error": f"{e} (Note: set recursive=True if removing a non-empty directory)",
                "duration": round(time.time() - start, 4),
            }

    # 2. 移动或复制必须有目标路径
    if not destination or not destination.strip():
        return {
            "status": "error",
            "action": act,
            "error": f"Destination path is required for '{act}' action.",
            "duration": round(time.time() - start, 4),
        }

    norm_dst = os.path.realpath(os.path.expanduser(destination.strip()))

    if _is_forbidden_path(norm_dst):
        return {
            "status": "error",
            "action": act,
            "destination": norm_dst,
            "error": "Safety guardrail blocked overwriting protected system or root directory.",
            "duration": round(time.time() - start, 4),
        }

    # 确保目标的父级目录存在
    dst_parent = os.path.dirname(norm_dst)
    if dst_parent and not os.path.exists(dst_parent):
        os.makedirs(dst_parent, exist_ok=True)

    try:
        if act == "move":
            if _is_forbidden_path(norm_src):
                return {
                    "status": "error",
                    "action": "move",
                    "source": norm_src,
                    "error": "Safety guardrail blocked moving protected system or root directory.",
                    "duration": round(time.time() - start, 4),
                }
            shutil.move(norm_src, norm_dst)
            action_done = "moved"
        else:  # copy
            if os.path.isdir(norm_src) and not os.path.islink(norm_src):
                if os.path.exists(norm_dst):
                    norm_dst = os.path.join(norm_dst, os.path.basename(norm_src))
                shutil.copytree(norm_src, norm_dst, dirs_exist_ok=True)
            else:
                shutil.copy2(norm_src, norm_dst)
            action_done = "copied"

        duration = round(time.time() - start, 4)
        structured_logging.structured(
            f"manage_file_{action_done}",
            source=norm_src,
            destination=norm_dst,
            duration=duration,
        )
        return {
            "status": "success",
            "action": act,
            "source": norm_src,
            "destination": norm_dst,
            "duration": duration,
        }
    except Exception as e:
        return {
            "status": "error",
            "action": act,
            "source": norm_src,
            "destination": norm_dst,
            "error": str(e),
            "duration": round(time.time() - start, 4),
        }
