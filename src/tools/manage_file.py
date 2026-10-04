import os
import shutil
import glob
from typing import Any
from src.registry import registry
from src.core.security import resolve_safe_path

@registry.register
def move_or_delete_file(
    action: str,
    source: str,
    destination: str | None = None,
    recursive: bool = False,
) -> dict[str, Any]:
    """Safely move, copy, or remove files/dirs. action MUST be 'move', 'copy', or 'remove'."""
    try:
        norm_src = resolve_safe_path(source)
        norm_dst = resolve_safe_path(destination) if destination else None

        if not os.path.exists(norm_src):
            return {"status": "error", "error": f"Source '{source}' not found"}

        if action == "remove":
            if os.path.isdir(norm_src):
                if not recursive:
                    return {"status": "error", "error": f"'{source}' is a directory. Set recursive=true"}
                shutil.rmtree(norm_src)
            else:
                os.remove(norm_src)
            return {"status": "success", "action": action, "source": source}

        if action in ["copy", "move"]:
            if not norm_dst:
                return {"status": "error", "error": f"Destination required for {action}"}
            
            if os.path.isdir(norm_src):
                if not recursive:
                    return {"status": "error", "error": f"'{source}' is a directory. Set recursive=true"}
                if action == "copy":
                    shutil.copytree(norm_src, norm_dst, dirs_exist_ok=True)
                else:
                    shutil.move(norm_src, norm_dst)
            else:
                if action == "copy":
                    shutil.copy2(norm_src, norm_dst)
                else:
                    shutil.move(norm_src, norm_dst)
            return {"status": "success", "action": action, "source": source, "destination": destination}

        return {"status": "error", "error": f"Unknown action: {action}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
