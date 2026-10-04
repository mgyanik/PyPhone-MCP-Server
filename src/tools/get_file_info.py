import hashlib
import os
import stat
from typing import Any
from src.registry import registry
from src.core.security import resolve_safe_path

@registry.register
def inspect_file_meta(path: str, compute_hash: bool = False) -> dict[str, Any]:
    """Inspect detailed file or directory metadata."""
    try:
        norm_path = resolve_safe_path(path)

        if not os.path.exists(norm_path):
            return {"status": "error", "error": "File not found"}

        file_stat = os.stat(norm_path)
        is_dir = stat.S_ISDIR(file_stat.st_mode)

        result = {
            "status": "success",
            "path": norm_path,
            "type": "directory" if is_dir else "file",
            "size": file_stat.st_size,
            "permissions": stat.filemode(file_stat.st_mode),
            "modified_time": file_stat.st_mtime,
        }

        if not is_dir and compute_hash:
            try:
                sha256 = hashlib.sha256()
                with open(norm_path, "rb") as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        sha256.update(chunk)
                result["sha256"] = sha256.hexdigest()
            except Exception as hash_e:
                result["hash_error"] = str(hash_e)

        return result
    except Exception as e:
        return {"status": "error", "error": str(e)}
