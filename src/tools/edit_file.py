"""精准编辑或创建文件工具，支持原子写入。"""

from __future__ import annotations

import os
import tempfile
import time
from typing import Any

from src.core import logging as structured_logging
from src.registry import mcp


def _atomic_write(file_path: str, content: str) -> None:
    """原子化写入文件，避免并发读取时出现中间不完整状态。"""
    dir_name = os.path.dirname(file_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_mcp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, file_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


@mcp.tool(
    name="edit_file",
    description="Edit file by unique string replacement or create a new file.",
    annotations={"destructiveHint": True},
)
def edit_file(
    path: str,
    old_text: str | None = None,
    new_text: str = "",
    create_if_missing: bool = False,
) -> dict[str, Any]:
    start = time.time()
    norm_path = os.path.expanduser(path)

    try:
        if not os.path.exists(norm_path):
            if create_if_missing:
                parent_dir = os.path.dirname(norm_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                _atomic_write(norm_path, new_text)
                duration = round(time.time() - start, 4)
                structured_logging.structured("file_created", path=norm_path, size=len(new_text), duration=duration)
                return {
                    "status": "success",
                    "path": norm_path,
                    "action": "created",
                    "replacements": 0,
                    "duration": duration,
                }
            return {
                "status": "error",
                "path": norm_path,
                "error": "File not found",
                "duration": round(time.time() - start, 4),
            }

        if os.path.isdir(norm_path):
            return {
                "status": "error",
                "path": norm_path,
                "error": "Target is a directory",
                "duration": round(time.time() - start, 4),
            }

        with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # old_text 为空表示全量覆盖
        if old_text is None or old_text == "":
            _atomic_write(norm_path, new_text)
            duration = round(time.time() - start, 4)
            structured_logging.structured("file_overwritten", path=norm_path, size=len(new_text), duration=duration)
            return {
                "status": "success",
                "path": norm_path,
                "action": "overwritten",
                "replacements": 0,
                "duration": duration,
            }

        occurrences = content.count(old_text)
        if occurrences == 0:
            return {
                "status": "error",
                "path": norm_path,
                "error": "old_text not found in file",
                "duration": round(time.time() - start, 4),
            }
        if occurrences > 1:
            return {
                "status": "error",
                "path": norm_path,
                "error": f"old_text found {occurrences} times; must be unique to replace",
                "duration": round(time.time() - start, 4),
            }

        updated_content = content.replace(old_text, new_text, 1)
        _atomic_write(norm_path, updated_content)

        duration = round(time.time() - start, 4)
        structured_logging.structured(
            "file_edited",
            path=norm_path,
            replacements=1,
            duration=duration,
        )
        return {
            "status": "success",
            "path": norm_path,
            "action": "edited",
            "replacements": 1,
            "duration": duration,
        }

    except Exception as e:
        return {
            "status": "error",
            "path": norm_path,
            "error": str(e),
            "duration": round(time.time() - start, 4),
        }
