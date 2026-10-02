"""列出所有任务工具。"""

from __future__ import annotations

from typing import Any

from src import logging as structured_logging
from src.registry import mcp
from src.task_store import task_store


@mcp.tool(
    name="list_tasks",
    annotations={"readOnlyHint": True},
)
def list_tasks(status: str | None = None) -> dict[str, Any]:
    """列出进行中和已完成的任务。只读。"""
    tasks = task_store.list(status=status)
    items = []
    for t in tasks:
        items.append({
            "task_id": t.task_id,
            "command": t.command,
            "cwd": t.cwd,
            "status": t.status,
            "duration": t.duration,
            "exit_code": t.exit_code,
        })

    summary = f"当前共 {len(items)} 个任务"
    if status:
        summary += f" (筛选状态: {status})"

    structured_logging.structured(
        "list_tasks_called",
        total_tasks=len(items),
        filter_status=status,
    )

    return {
        "status": "success",
        "tasks": items,
        "count": len(items),
        "summary": summary,
    }
