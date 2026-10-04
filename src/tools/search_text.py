import os
from collections.abc import Iterator
from typing import Any
from src.registry import registry
from src.core.security import resolve_safe_path

MAX_MATCHES = 200
EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist"}

@registry.register
def search_codebase(
    path: str,
    query: str | None = None,
    queries: list[str] | None = None,
    _: bool = False,
) -> dict[str, Any]:
    """Fast parallel keyword search. Supply 'query' string or 'queries' list. Auto-ignores .git/node_modules. Replaces grep/rg."""
    try:
        norm_path = resolve_safe_path(path)
        qs = [query] if query else []
        if queries:
            qs.extend(queries)
        qs = [q for q in qs if q]

        if not qs:
            return {"status": "error", "error": "Must provide 'query' or 'queries'"}

        matches = []
        count = 0
        def _walk(p: str) -> Iterator[str]:
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
                for f in files:
                    yield os.path.join(root, f)

        for file_path in _walk(norm_path):
            if count >= MAX_MATCHES:
                break
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line_idx, line_content in enumerate(lines):
                    for q in qs:
                        if q in line_content:
                            matches.append({"file": file_path, "line": line_idx + 1, "content": line_content.strip()})
                            count += 1
                            break
                    if count >= MAX_MATCHES:
                        break
            except Exception:
                pass

        return {"status": "success", "results": [{"query": qs, "status": "success", "matches": matches, "count": count}], "total_queries": len(qs), "total_matches": count}
    except Exception as e:
        return {"status": "error", "error": str(e)}
