"""精准编辑或创建文件工具，支持行号范围替换、全量覆写或精准匹配。"""

from __future__ import annotations

import os
import tempfile
import time
from typing import Any

from src.core import logging as structured_logging
from src.registry import mcp


def _atomic_write(file_path: str, content: str) -> None:
    """原子化写入文件，避免并发读取时出现中间不完整状态。"""
    dir_name = os.path.dirname(file_path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_mcp_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, file_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


@mcp.tool(
    name="edit_file",
    description=(
        "Edit files with high efficiency by line range replacement, whole-file write, or exact text match (replaces shell 'sed -i', 'echo >', 'tee').\n"
        "Parameters:\n"
        "- path (str): Target file path.\n"
        "- new_text (str): Replacement text or full file content.\n"
        "- start_line (int, optional): 1-based starting line number (inclusive) for line-range replacement.\n"
        "- end_line (int, optional): 1-based ending line number (inclusive). Defaults to start_line (single line replacement). If end_line < start_line, acts as line insertion before start_line.\n"
        "- create_if_missing (bool, default: False): Set True when creating a new file (automatically creates missing parent directories).\n"
        "- old_text (str, optional): Legacy fallback for unique exact string replacement when line numbers are omitted.\n"
        "Modes of operation:\n"
        "1. Line Range Replacement (RECOMMENDED): Specify start_line (and optionally end_line) with new_text. Pairs perfectly with read_file_lines.\n"
        "2. Whole-file Overwrite / Create: Omit start_line and old_text; writes new_text directly.\n"
        "3. Exact Text Replacement (Legacy): Provide old_text when line numbers are unknown.\n"
        "Usage guideline: ALWAYS prefer using start_line/end_line after inspecting code via read_file_lines to minimize token transmission and guarantee 100% precision."
    ),
    annotations={"destructiveHint": True},
)
def edit_file(
    path: str,
    new_text: str = "",
    start_line: int | None = None,
    end_line: int | None = None,
    create_if_missing: bool = False,
    old_text: str | None = None,
) -> dict[str, Any]:
    start = time.time()
    norm_path = os.path.expanduser(path)

    try:
        if not os.path.exists(norm_path):
            if create_if_missing:
                parent_dir = os.path.dirname(norm_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                _atomic_write(norm_path, new_text)
                duration = round(time.time() - start, 4)
                structured_logging.structured(
                    "file_created", path=norm_path, size=len(new_text), duration=duration
                )
                return {
                    "status": "success",
                    "path": norm_path,
                    "action": "created",
                    "duration": duration,
                }
            return {
                "status": "error",
                "path": norm_path,
                "error": "File not found",
                "duration": round(time.time() - start, 4),
            }

        if os.path.isdir(norm_path):
            return {
                "status": "error",
                "path": norm_path,
                "error": "Target is a directory",
                "duration": round(time.time() - start, 4),
            }

        with open(norm_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # 模式 1: 按行号范围精准替换/插入 (核心推荐模式)
        if start_line is not None:
            lines = content.splitlines(keepends=True)
            total_lines = len(lines)
            s_line = int(start_line)

            if s_line < 1:
                return {
                    "status": "error",
                    "path": norm_path,
                    "error": f"start_line ({s_line}) must be >= 1",
                    "duration": round(time.time() - start, 4),
                }

            if total_lines == 0:
                if s_line == 1:
                    _atomic_write(norm_path, new_text)
                    duration = round(time.time() - start, 4)
                    return {
                        "status": "success",
                        "path": norm_path,
                        "action": "line_replaced",
                        "start_line": 1,
                        "end_line": 1,
                        "lines_replaced": 0,
                        "total_lines": len(new_text.splitlines()),
                        "duration": duration,
                    }
                return {
                    "status": "error",
                    "path": norm_path,
                    "error": f"start_line ({s_line}) exceeds empty file",
                    "duration": round(time.time() - start, 4),
                }

            if s_line > total_lines + 1:
                return {
                    "status": "error",
                    "path": norm_path,
                    "error": f"start_line ({s_line}) exceeds file line count ({total_lines})",
                    "duration": round(time.time() - start, 4),
                }

            e_line = int(end_line) if end_line is not None else s_line
            if e_line < s_line - 1:
                return {
                    "status": "error",
                    "path": norm_path,
                    "error": f"end_line ({e_line}) cannot be less than start_line - 1 ({s_line - 1})",
                    "duration": round(time.time() - start, 4),
                }

            prefix = "".join(lines[: s_line - 1])
            suffix = "".join(lines[e_line:]) if e_line >= s_line else "".join(lines[s_line - 1 :])

            replacement = new_text
            if suffix and replacement and not replacement.endswith(("\n", "\r\n")):
                replacement += "\n"

            updated_content = prefix + replacement + suffix
            _atomic_write(norm_path, updated_content)

            duration = round(time.time() - start, 4)
            is_insertion = e_line < s_line
            action = "inserted" if is_insertion else "line_replaced"
            lines_replaced = 0 if is_insertion else (min(e_line, total_lines) - s_line + 1)
            new_total = len(updated_content.splitlines())

            structured_logging.structured(
                "file_line_edited",
                path=norm_path,
                action=action,
                start_line=s_line,
                end_line=e_line,
                lines_replaced=lines_replaced,
                duration=duration,
            )

            return {
                "status": "success",
                "path": norm_path,
                "action": action,
                "start_line": s_line,
                "end_line": e_line,
                "lines_replaced": lines_replaced,
                "total_lines": new_total,
                "duration": duration,
            }

        # 模式 2: 传统 old_text 文本唯一替换
        if old_text is not None and old_text != "":
            occurrences = content.count(old_text)
            if occurrences == 0:
                return {
                    "status": "error",
                    "path": norm_path,
                    "error": "old_text not found in file",
                    "duration": round(time.time() - start, 4),
                }
            if occurrences > 1:
                return {
                    "status": "error",
                    "path": norm_path,
                    "error": f"old_text found {occurrences} times; must be unique to replace",
                    "duration": round(time.time() - start, 4),
                }

            updated_content = content.replace(old_text, new_text, 1)
            _atomic_write(norm_path, updated_content)

            duration = round(time.time() - start, 4)
            structured_logging.structured(
                "file_edited",
                path=norm_path,
                replacements=1,
                duration=duration,
            )
            return {
                "status": "success",
                "path": norm_path,
                "action": "edited",
                "replacements": 1,
                "duration": duration,
            }

        # 模式 3: 全量覆写
        _atomic_write(norm_path, new_text)
        duration = round(time.time() - start, 4)
        structured_logging.structured(
            "file_overwritten", path=norm_path, size=len(new_text), duration=duration
        )
        return {
            "status": "success",
            "path": norm_path,
            "action": "overwritten",
            "replacements": 0,
            "duration": duration,
        }

    except Exception as e:
        return {
            "status": "error",
            "path": norm_path,
            "error": str(e),
            "duration": round(time.time() - start, 4),
        }
