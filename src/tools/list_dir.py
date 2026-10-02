"""目录列举工具，支持传入单个目录或并发列出多个目录。"""

from __future__ import annotations

import os
import time
from typing import Any

from src.core import logging as structured_logging
from src.core.pool import map_concurrent
from src.registry import mcp


def _list_single_dir(path: str) -> dict[str, Any]:
    start = time.time()
    try:
        norm_path = os.path.expanduser(path)
        if not os.path.exists(norm_path):
            return {
                "path": path,
                "status": "error",
                "error": "Directory not found",
                "entries": [],
                "duration": round(time.time() - start, 4),
            }
        if not os.path.isdir(norm_path):
            return {
                "path": path,
                "status": "error",
                "error": "Target is not a directory",
                "entries": [],
                "duration": round(time.time() - start, 4),
            }

        entries = []
        with os.scandir(norm_path) as it:
            for entry in it:
                try:
                    stat = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size,
                    })
                except Exception:
                    entries.append({
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": 0,
                    })

        entries.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
        return {
            "path": path,
            "status": "success",
            "entries": entries,
            "count": len(entries),
            "duration": round(time.time() - start, 4),
        }
    except Exception as e:
        return {
            "path": path,
            "status": "error",
            "error": str(e),
            "entries": [],
            "duration": round(time.time() - start, 4),
        }


@mcp.tool(
    name="list_dir",
    description="List directory contents (sorted directories first, then files with sizes). Supports passing multiple directory paths in [paths] for parallel batch exploration.",
    annotations={"readOnlyHint": True},
)
def list_dir(paths: list[str] | str = ".") -> dict[str, Any]:
    target_paths = [paths] if isinstance(paths, str) else list(paths)
    start_total = time.time()

    results = map_concurrent(_list_single_dir, target_paths)
    total_duration = round(time.time() - start_total, 4)
    success_count = sum(1 for r in results if r["status"] == "success")

    output = {
        "status": "success" if success_count == len(results) else "partial_success",
        "results": results,
        "total_dirs": len(results),
        "duration": total_duration,
    }

    structured_logging.structured(
        "batch_list_dir",
        total_dirs=len(results),
        success_count=success_count,
        duration=total_duration,
    )
    return output


def list_dirs(paths: list[str]) -> dict[str, Any]:
    return list_dir(paths)
