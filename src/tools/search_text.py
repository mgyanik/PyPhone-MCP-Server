"""文本搜索工具，流式早停并支持批量关键词并发匹配。"""

from __future__ import annotations

import os
import time
from typing import Any

from src.core import logging as structured_logging
from src.core.pool import map_concurrent
from src.registry import mcp

# 检索时应忽略的目录集合
_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "target",
    "bin",
    "obj",
    "build",
    "dist",
}


def _search_single_query(query: str, root_path: str, max_matches: int = 50) -> dict[str, Any]:
    start = time.time()
    matches = []
    norm_path = os.path.expanduser(root_path)

    if not os.path.exists(norm_path):
        return {
            "query": query,
            "status": "error",
            "error": f"Path not found: {root_path}",
            "matches": [],
            "count": 0,
            "duration": round(time.time() - start, 4),
        }

    try:
        if os.path.isfile(norm_path):
            file_generator = [norm_path]
        else:
            def _walk_files():
                for root, dirs, files in os.walk(norm_path):
                    # 预剪枝忽略目录
                    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in _EXCLUDED_DIRS]
                    for f in files:
                        if not f.startswith("."):
                            yield os.path.join(root, f)

            file_generator = _walk_files()

        for file_path in file_generator:
            if len(matches) >= max_matches:
                break
            try:
                # 检查文件大小，大于 5MB 的跳过以避免内存耗尽
                if os.path.getsize(file_path) > 5 * 1024 * 1024:
                    continue
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if query in line:
                            matches.append({
                                "file": file_path,
                                "line": line_num,
                                "content": line.strip()[:200],
                            })
                            if len(matches) >= max_matches:
                                break
            except (OSError, PermissionError):
                continue

        return {
            "query": query,
            "status": "success",
            "matches": matches,
            "count": len(matches),
            "duration": round(time.time() - start, 4),
        }
    except Exception as e:
        return {
            "query": query,
            "status": "error",
            "error": str(e),
            "matches": [],
            "count": 0,
            "duration": round(time.time() - start, 4),
        }


@mcp.tool(
    name="search_texts",
    description="Search text patterns. Supports batch queries.",
    annotations={"readOnlyHint": True},
)
def search_texts(queries: list[str] | str, path: str = ".") -> dict[str, Any]:
    target_queries = [queries] if isinstance(queries, str) else list(queries)
    start_total = time.time()

    def _worker(q: str) -> dict[str, Any]:
        return _search_single_query(q, path)

    results = map_concurrent(_worker, target_queries)
    total_duration = round(time.time() - start_total, 4)
    total_matches = sum(r["count"] for r in results if r["status"] == "success")

    output = {
        "status": "success",
        "results": results,
        "total_queries": len(results),
        "total_matches": total_matches,
        "duration": total_duration,
    }

    structured_logging.structured(
        "batch_search_texts",
        queries_count=len(results),
        total_matches=total_matches,
        duration=total_duration,
    )
    return output


def search_text(query: str, path: str = ".") -> dict[str, Any]:
    res = search_texts([query], path=path)
    single = res["results"][0]
    return {
        "status": single["status"],
        "query": single["query"],
        "matches": single.get("matches", []),
        "count": single.get("count", 0),
        "error": single.get("error"),
        "duration": single["duration"],
    }
