"""按指定行号范围分页读取文本文件工具。"""

from __future__ import annotations

import os
import time
from typing import Any

from src.core import logging as structured_logging
from src.registry import mcp


@mcp.tool(
    name="read_file_lines",
    description=(
        "Read a specific window of lines from a text file with 1-based line numbering (replaces shell 'head', 'tail', 'sed -n').\n"
        "Parameters:\n"
        "- path (str): Target file path.\n"
        "- start_line (int, default: 1): 1-based starting line number.\n"
        "- line_count (int, default: 100, max: 500): Number of lines to retrieve.\n"
        "Returns:\n"
        "- content: Line-numbered formatted text (e.g. ' 42 | def foo():') for easy context referencing.\n"
        "- total_lines: Total line count of the file.\n"
        "- has_more: Boolean indicating if there are further lines beyond this window.\n"
        "Usage guideline: ALWAYS use this tool instead of read_files when examining large files (> 300 lines), viewing logs, or inspecting specific functions to dramatically reduce context Token usage."
    ),
    annotations={"readOnlyHint": True},
)
def read_file_lines(
    path: str,
    start_line: int = 1,
    line_count: int = 100,
) -> dict[str, Any]:
    start_time = time.time()
    norm_path = os.path.expanduser(path)

    if not os.path.exists(norm_path):
        return {
            "status": "error",
            "path": path,
            "error": "File not found",
            "duration": round(time.time() - start_time, 4),
        }

    if os.path.isdir(norm_path):
        return {
            "status": "error",
            "path": path,
            "error": "Target is a directory",
            "duration": round(time.time() - start_time, 4),
        }

    start_idx = max(1, int(start_line))
    count = max(1, min(500, int(line_count)))
    end_idx = start_idx + count - 1

    selected_lines: list[tuple[int, str]] = []
    total_lines = 0

    try:
        with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
            for current_line_num, line in enumerate(f, 1):
                total_lines = current_line_num
                clean_line = line.rstrip("\r\n")
                if start_idx <= current_line_num <= end_idx:
                    selected_lines.append((current_line_num, clean_line))

        has_more = total_lines > end_idx
        # 格式化输出带对齐行号的文本
        padding = len(str(min(end_idx, total_lines)))
        formatted_content = "\n".join(
            f"{line_num:>{padding}} | {text}" for line_num, text in selected_lines
        )

        duration = round(time.time() - start_time, 4)
        structured_logging.structured(
            "read_file_lines_called",
            path=norm_path,
            start_line=start_idx,
            line_count=count,
            total_lines=total_lines,
            duration=duration,
        )

        return {
            "status": "success",
            "path": norm_path,
            "start_line": start_idx,
            "lines_retrieved": len(selected_lines),
            "total_lines": total_lines,
            "has_more": has_more,
            "content": formatted_content,
            "lines": [text for _, text in selected_lines],
            "duration": duration,
        }

    except Exception as e:
        return {
            "status": "error",
            "path": norm_path,
            "error": str(e),
            "duration": round(time.time() - start_time, 4),
        }
