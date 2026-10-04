import os
import difflib
import re
from typing import Any
from src.registry import registry
from src.core.security import resolve_safe_path

def _find_symbol_block(lines: list[str], symbol: str) -> tuple[int, int] | None:
    pattern = re.compile(r'^\s*(def|class|function|const|let|var|interface|type)\s+' + re.escape(symbol) + r'\b')
    start_idx = -1
    indent = ""
    for i, line in enumerate(lines):
        if pattern.search(line):
            start_idx = i
            indent_match = re.match(r'^(\s*)', line)
            indent = indent_match.group(1) if indent_match else ""
            break
    if start_idx == -1: return None
    end_idx = start_idx
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if not line.strip() or line.strip().startswith(('#', '//')):
            end_idx = i
            continue
        curr_indent_match = re.match(r'^(\s*)', line)
        curr_indent = curr_indent_match.group(1) if curr_indent_match else ""
        if len(curr_indent) <= len(indent): break
        end_idx = i
    return (start_idx + 1, end_idx + 1)

@registry.register
def patch_file(
    path: str,
    edits: list[dict[str, Any]] = None,
    dry_run: bool = False,
    return_diff: str = "summary",
    create_if_missing: bool = False,
    new_text: str | None = None,
    old_text: str | None = None,
    start_line: int | None = None,
    end_line: int | None = None,
) -> dict[str, Any]:
    """Structured file editor (Patch Tool). NEVER rewrite the whole file! Workflow: 1. read_file_or_outline(outline) -> 2. patch_file(edits) -> 3. read_file_or_outline(verify) Provide an array of edits. Supported ops: search_replace, replace_range, replace_symbol. Set dry_run: true to preview diffs safely."""
    try:
        norm_path = resolve_safe_path(path)
        if not os.path.exists(norm_path):
            if create_if_missing: open(norm_path, 'a').close()
            else: return {"ok": False, "error": f"File {os.path.basename(norm_path)} not found. Set create_if_missing=true."}

        with open(norm_path, "r", encoding="utf-8") as f: original_text = f.read()
        current_text = original_text
        applied = 0
        warnings = []
        if edits is None:
            edits = []
            if old_text is not None and new_text is not None:
                edits.append({'op': 'search_replace', 'search': old_text, 'replace': new_text})
            elif start_line is not None and end_line is not None and new_text is not None:
                edits.append({'op': 'replace_range', 'start_line': start_line, 'end_line': end_line, 'new_text': new_text})
            elif new_text is not None:
                edits.append({'op': 'replace_range', 'start_line': 1, 'end_line': max(1, len(original_text.splitlines())), 'new_text': new_text})

        for edit in edits:
            op = edit.get("op")
            if op == "search_replace":
                search = edit.get("search", "")
                replace = edit.get("replace", "")
                occurrence = edit.get("occurrence")
                if search not in current_text: return {"ok": False, "error": "search_not_unique", "suggestion": f"Could not find exact text block.", "edit": edit}
                count = current_text.count(search)
                if count > 1 and occurrence is None: return {"ok": False, "error": "search_not_unique", "suggestion": "Multiple matches found. Specify 'occurrence'."}
                if occurrence:
                    parts = current_text.split(search)
                    if occurrence > len(parts) - 1: return {"ok": False, "error": f"occurrence {occurrence} out of bounds (only {count} found)."}
                    current_text = search.join(parts[:occurrence]) + replace + search.join(parts[occurrence:])
                else: current_text = current_text.replace(search, replace)
            elif op == "replace_range":
                sl = max(0, edit.get("start_line", 1) - 1)
                el = edit.get("end_line", len(current_text.splitlines()))
                lines_cur = current_text.splitlines()
                lines_cur[sl:el] = edit.get("new_text", "").splitlines()
                current_text = "\n".join(lines_cur) + ("\n" if current_text.endswith("\n") else "")
            elif op == "replace_symbol":
                symbol = edit.get("symbol")
                if not symbol: return {"ok": False, "error": "replace_symbol requires 'symbol'"}
                lines_cur = current_text.splitlines()
                bounds = _find_symbol_block(lines_cur, symbol)
                if bounds:
                    sl, el = bounds
                    lines_cur[sl-1:el] = edit.get("new_text", "").splitlines()
                    current_text = "\n".join(lines_cur) + ("\n" if current_text.endswith("\n") else "")
                else: return {"ok": False, "error": f"Symbol '{symbol}' not found."}
            applied += 1

        orig_lines = original_text.splitlines(keepends=True)
        curr_lines = current_text.splitlines(keepends=True)
        diff_gen = list(difflib.unified_diff(orig_lines, curr_lines, fromfile=path, tofile=path))
        diff_text = "".join(diff_gen)

        if not dry_run and original_text != current_text:
            temp_path = f"{norm_path}.tmp.{os.getpid()}"
            with open(temp_path, "w", encoding="utf-8") as f: f.write(current_text)
            os.replace(temp_path, norm_path)

        diff_out = diff_text if return_diff == "full" else (diff_text[:2000] + "\n...[Diff truncated]..." if len(diff_text) > 2000 else diff_text)
        return {"ok": True, "applied": applied, "files": [{"path": norm_path, "lines_added": sum(1 for l in diff_gen if l.startswith('+') and not l.startswith('+++')), "lines_removed": sum(1 for l in diff_gen if l.startswith('-') and not l.startswith('---'))}], "diff": diff_out, "dry_run": dry_run, "warnings": warnings}
    except Exception as e:
        return {"ok": False, "error": str(e)}
