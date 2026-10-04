import os
from typing import Any
from src.registry import registry
from src.core.security import resolve_safe_path
import re

def extract_outline(content: str) -> str:
    lines = content.splitlines()
    outline = []
    for i, line in enumerate(lines, 1):
        if re.match(r'^\s*(def|class|interface|type)\s+', line) or re.match(r'^\s*(export\s+)?(function|class|interface|type|const\s+\w+\s*=)\s+', line):
            outline.append(f"{i}: {line}")
    return "\n".join(outline) if outline else "No structural outline found (may not be a code file)."

@registry.register
def read_file_or_outline(
    path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    outline: bool = False,
    force_full: bool = False,
) -> dict[str, Any]:
    """Advanced file reading tool. CRITICAL PRINCIPLES: Finding a function or checking config? Use outline=true or read a specific snippet (start_line/end_line). Understanding overall architecture or the file is < 2k lines? Use normal full read. If a file is > 500 lines and no specific parameters are provided, it will return an outline and prompt you to specify range or set force_full=true."""
    try:
        norm_path = resolve_safe_path(path)
        if not os.path.exists(norm_path):
            return {"status": "error", "error": "File not found"}
        if not os.path.isfile(norm_path):
            return {"status": "error", "error": "Path is not a file"}

        with open(norm_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()
        total_lines = len(lines)

        if outline:
            return {"status": "success", "path": norm_path, "total_lines": total_lines, "content": extract_outline(content), "is_outline": True}

        if start_line is not None or end_line is not None:
            sl = max(0, (start_line or 1) - 1)
            el = min(total_lines, end_line or total_lines)
            chunk = "\n".join(lines[sl:el])
            return {"status": "success", "path": norm_path, "start_line": sl + 1, "end_line": el, "total_lines": total_lines, "content": chunk}

        if total_lines > 500 and not force_full:
            return {"status": "error", "error": f"File {os.path.basename(norm_path)} is {total_lines} lines long. Exceeds recommended single-read limit. Please use `outline=true`, specify `start_line` and `end_line`, or pass `force_full=true`."}

        return {"status": "success", "path": norm_path, "total_lines": total_lines, "content": content, "is_full_read": True}
    except Exception as e:
        return {"status": "error", "error": str(e)}
