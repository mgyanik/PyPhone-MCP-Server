"""批量与单文件读取工具，支持高并发读取。"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src import logging as structured_logging
from src.registry import mcp


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
    name="read_files",
    description="Read file contents. Supports batch paths.",
    annotations={"readOnlyHint": True},
)
def read_files(paths: list[str] | str) -> dict[str, Any]:
    if isinstance(paths, str):
        target_paths = [paths]
    else:
        target_paths = list(paths)

    start_total = time.time()
    max_workers = min(max(1, len(target_paths)), 16)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_read_single_file, p) for p in target_paths]
        results = [f.result() for f in futures]

    total_duration = round(time.time() - start_total, 4)
    success_count = sum(1 for r in results if r["status"] == "success")

    output = {
        "status": "success" if success_count == len(results) else "partial_success",
        "results": results,
        "total_files": len(results),
        "duration": total_duration,
    }

    structured_logging.structured(
        "batch_read_files",
        total_files=len(results),
        success_count=success_count,
        duration=total_duration,
    )
    return output


def read_file(path: str) -> dict[str, Any]:
    res = read_files([path])
    single = res["results"][0]
    return {
        "status": single["status"],
        "path": single["path"],
        "content": single.get("content"),
        "error": single.get("error"),
        "duration": single["duration"],
    }


# 保持向后兼容别名
get_files = read_files
get_file = read_file
