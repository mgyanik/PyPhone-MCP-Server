"""列出所有任务工具。"""

from __future__ import annotations

from typing import Any

from src import logging as structured_logging
from src.registry import mcp
from src.task_store import task_store


@mcp.tool(
    name="list_tasks",
    description="List all background tasks with status filter.",
    annotations={"readOnlyHint": True},
)
def list_tasks(status: str | None = None) -> dict[str, Any]:
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

    structured_logging.structured(
        "list_tasks_called",
        total_tasks=len(items),
        filter_status=status,
    )

    return {
        "status": "success",
        "tasks": items,
        "count": len(items),
    }
