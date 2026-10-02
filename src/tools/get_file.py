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
    name="get_files",
    description="读取文件内容。可一次传入多个目标，比逐个调用更快",
    annotations={"readOnlyHint": True},
)
def get_files(paths: list[str] | str) -> dict[str, Any]:
    """批量读取文件内容。内部并发执行，每个子结果独立。"""
    if isinstance(paths, str):
        target_paths = [paths]
    else:
        target_paths = list(paths)

    start_total = time.time()
    
    # 使用线程池并发执行，禁止串行 for 循环
    max_workers = min(max(1, len(target_paths)), 16)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # submit 保证与 paths 原顺序一一对应
        futures = [executor.submit(_read_single_file, p) for p in target_paths]
        results = [f.result() for f in futures]

    total_duration = round(time.time() - start_total, 4)
    success_count = sum(1 for r in results if r["status"] == "success")
    summary = f"成功读取 {success_count}/{len(results)} 个文件，耗时 {total_duration:.3f}s"

    output = {
        "status": "success" if success_count == len(results) else "partial_success",
        "results": results,
        "summary": summary,
        "total_files": len(results),
        "duration": total_duration,
    }

    structured_logging.structured(
        "batch_get_files",
        total_files=len(results),
        success_count=success_count,
        duration=total_duration,
    )
    return output


# 保持内部兼容函数，不注册为 MCP tool
def get_file(path: str) -> dict[str, Any]:
    """单文件读取兼容函数。"""
    res = get_files([path])
    single = res["results"][0]
    return {
        "status": single["status"],
        "path": single["path"],
        "content": single.get("content"),
        "error": single.get("error"),
        "summary": f"读取文件: {path} ({single['status']})",
        "duration": single["duration"],
    }
