"""文本搜索工具，支持批量关键词并发匹配。"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src import logging as structured_logging
from src.registry import mcp


def _search_single_query(query: str, root_path: str, max_matches: int = 50) -> dict[str, Any]:
    start = time.time()
    matches = []
    norm_path = os.path.expanduser(root_path)

    try:
        if os.path.isfile(norm_path):
            file_list = [norm_path]
        elif os.path.isdir(norm_path):
            file_list = []
            for root, dirs, files in os.walk(norm_path):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", "target", "bin", "obj")]
                for file in files:
                    if not file.startswith("."):
                        file_list.append(os.path.join(root, file))
        else:
            return {
                "query": query,
                "status": "error",
                "error": f"Path not found: {root_path}",
                "matches": [],
                "count": 0,
                "duration": round(time.time() - start, 4),
            }

        for file_path in file_list:
            if len(matches) >= max_matches:
                break
            try:
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
            except Exception:
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
    if isinstance(queries, str):
        target_queries = [queries]
    else:
        target_queries = list(queries)

    start_total = time.time()
    max_workers = min(max(1, len(target_queries)), 8)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_search_single_query, q, path) for q in target_queries]
        results = [f.result() for f in futures]

    total_duration = round(time.time() - start_total, 4)
    total_matches = sum(r["count"] for r in results)

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
