"""文件或目录元数据与完整性校验工具。"""

from __future__ import annotations

import datetime
import hashlib
import os
import stat
import time
from typing import Any

from src.core import logging as structured_logging
from src.registry import mcp, registry


def _format_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}" if unit != "B" else f"{size_bytes} B"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def _format_mode(mode: int) -> str:
    return stat.filemode(mode)


def _compute_sha256(file_path: str) -> str | None:
    try:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


@mcp.tool(
    name="get_file_info",
    description=(
        "Inspect detailed file/directory metadata or verify file integrity (replaces shell 'stat', 'ls -l', 'test -f', and 'sha256sum').\n"
        "Parameters:\n"
        "- path (str): Target file or directory path.\n"
        "- compute_hash (bool, default: False): When True, streams and computes the SHA-256 checksum (useful for validating downloaded assets, binaries, or artifacts).\n"
        "Returns:\n"
        "- exists (bool): Whether path exists.\n"
        "- type (str): 'file', 'directory', 'symlink', or 'not_found'.\n"
        "- size_bytes (int) & size_human (str): Exact and readable file size.\n"
        "- modified_at (str): Human-readable ISO timestamp of last modification.\n"
        "- permissions (str): File permission string (e.g. '-rw-r--r--').\n"
        "- is_binary (bool, for files): Whether the file appears to be binary.\n"
        "- sha256 (str|None): SHA-256 hash if compute_hash was enabled and file is readable.\n"
        "Usage guideline: Use this tool to check existence, timestamps, and sizes without launching shell commands."
    ),
    annotations={"readOnlyHint": True},
)
def get_file_info(path: str, compute_hash: bool = False) -> dict[str, Any]:
    start = time.time()
    norm_path = os.path.expanduser(path)

    if not os.path.exists(norm_path) and not os.path.islink(norm_path):
        return {
            "status": "success",
            "path": norm_path,
            "exists": False,
            "type": "not_found",
            "size_bytes": 0,
            "size_human": "0 B",
            "modified_at": None,
            "permissions": None,
            "sha256": None,
            "duration": round(time.time() - start, 4),
        }

    try:
        is_link = os.path.islink(norm_path)
        file_stat = os.lstat(norm_path) if is_link else os.stat(norm_path)
        mode = file_stat.st_mode

        if is_link:
            item_type = "symlink"
        elif stat.S_ISDIR(mode):
            item_type = "directory"
        else:
            item_type = "file"

        size_bytes = file_stat.st_size
        mtime = datetime.datetime.fromtimestamp(
            file_stat.st_mtime, tz=datetime.timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")

        sha256_hash = None
        is_binary = False

        if item_type == "file":
            # 探测是否二进制
            try:
                with open(norm_path, "rb") as f:
                    chunk = f.read(1024)
                    if b"\x00" in chunk:
                        is_binary = True
            except Exception:
                pass

            if compute_hash:
                sha256_hash = _compute_sha256(norm_path)

        duration = round(time.time() - start, 4)
        structured_logging.structured(
            "get_file_info_queried",
            path=norm_path,
            item_type=item_type,
            size_bytes=size_bytes,
            duration=duration,
        )

        return {
            "status": "success",
            "path": norm_path,
            "exists": True,
            "type": item_type,
            "size_bytes": size_bytes,
            "size_human": _format_size(size_bytes),
            "modified_at": mtime,
            "permissions": _format_mode(mode),
            "is_binary": is_binary if item_type == "file" else None,
            "sha256": sha256_hash,
            "duration": duration,
        }

    except Exception as e:
        return {
            "status": "error",
            "path": norm_path,
            "error": str(e),
            "duration": round(time.time() - start, 4),
        }


# 向后兼容别名与映射
file_info = get_file_info
registry.register_alias("file_info", "get_file_info")
