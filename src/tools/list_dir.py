import os
import concurrent.futures
from typing import Any
from src.registry import registry
from src.core.security import resolve_safe_path

MAX_RESULTS = 1000

@registry.register
def list_directory(paths: list[str] | str = ".", _: bool = False) -> dict[str, Any]:
    """Fast parallel directory lister (results limited to 1000 to save tokens). If a dir is huge or you need specific files, ALWAYS use search_codebase instead of list_directory."""
    try:
        paths_list = [paths] if isinstance(paths, str) else paths
        if not paths_list:
            paths_list = ["."]

        # Sanitize all paths
        paths_list = [resolve_safe_path(p) for p in paths_list]

        results = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_to_path = {
                executor.submit(_list_single_dir, p): p for p in paths_list
            }
            for future in concurrent.futures.as_completed(future_to_path):
                results.append(future.result())

        return {
            "status": "success",
            "results": results,
            "total_dirs": len(paths_list)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def _list_single_dir(path: str) -> dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {"path": path, "status": "error", "error": "Not found"}

        if not os.path.isdir(path):
            return {"path": path, "status": "error", "error": "Not a directory"}

        entries = []
        count = 0
        has_more = False

        with os.scandir(path) as it:
            for entry in it:
                if count >= MAX_RESULTS:
                    has_more = True
                    break
                
                try:
                    stat = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size
                    })
                    count += 1
                except OSError:
                    pass

        return {
            "path": path,
            "status": "success",
            "entries": entries,
            "count": count,
            "has_more": has_more
        }
    except Exception as e:
        return {"path": path, "status": "error", "error": str(e)}
