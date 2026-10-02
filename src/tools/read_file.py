"""批量与单文件高并发读取工具。"""

from __future__ import annotations

import os
import time
from typing import Any

from src.core import logging as structured_logging
from src.core.pool import map_concurrent
from src.registry import mcp, registry


def _read_single_file(path: str) -> dict[str, Any]:
    start = time.time()
    try:
        norm_path = os.path.expanduser(path)
        if not os.path.exists(norm_path):
            return {
                "path": path,
                "status": "error",
                "error": "File not found",
                "content": None,
                "duration": round(time.time() - start, 4),
            }
        if os.path.isdir(norm_path):
            return {
                "path": path,
                "status": "error",
                "error": "Target is a directory",
                "content": None,
                "duration": round(time.time() - start, 4),
            }
        with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {
            "path": path,
            "status": "success",
            "content": content,
            "size": len(content),
            "duration": round(time.time() - start, 4),
        }
    except Exception as e:
        return {
            "path": path,
            "status": "error",
            "error": str(e),
            "content": None,
            "duration": round(time.time() - start, 4),
        }


@mcp.tool(
    name="read_file",
    description=(
        "Read file contents using high-concurrency worker pool (replaces shell 'cat').\n"
        "Parameters:\n"
        "- paths (list[str] | str, optional): Single file path or a list of file paths.\n"
        "- path (str, optional): Alternative single file path argument.\n"
        "Usage guideline:\n"
        "1. PREFER passing multiple file paths in a single array [paths] to read them concurrently in parallel, which minimizes network roundtrips and token latency.\n"
        "2. For large files (> 300 lines) or inspecting specific code blocks/logs, ALWAYS prefer 'read_file_lines' instead of reading full content into context."
    ),
    annotations={"readOnlyHint": True},
)
def read_file(
    paths: list[str] | str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    target = paths if paths is not None else path
    if target is None:
        target_paths = ["."]
    elif isinstance(target, str):
        target_paths = [target]
    else:
        target_paths = list(target)

    start_total = time.time()

    # 使用全局长驻线程池并发读取
    results = map_concurrent(_read_single_file, target_paths)
    total_duration = round(time.time() - start_total, 4)
    success_count = sum(1 for r in results if r["status"] == "success")

    output = {
        "status": "success" if success_count == len(results) else "partial_success",
        "results": results,
        "total_files": len(results),
        "duration": total_duration,
    }

    structured_logging.structured(
        "read_file_batch",
        total_files=len(results),
        success_count=success_count,
        duration=total_duration,
    )
    return output


# 向后兼容别名与注册映射
read_files = read_file
get_files = read_file
get_file = read_file
registry.register_alias("read_files", "read_file")
registry.register_alias("get_files", "read_file")
registry.register_alias("get_file", "read_file")
