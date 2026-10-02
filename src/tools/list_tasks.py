"""列出所有异步后台任务工具。"""

from __future__ import annotations

from typing import Any

from src.core import logging as structured_logging
from src.core.task_store import task_store
from src.registry import mcp


@mcp.tool(
    name="list_tasks",
    description=(
        "List all registered background tasks with optional status filtering.\n"
        "Parameters:\n"
        "- status (str, optional): Filter tasks by status ('running', 'done', 'failed', 'canceled', 'denied'). If omitted, returns all recent tasks.\n"
        "Returns:\n"
        "- tasks: Array of task summaries including task_id, command, cwd, status, duration, and exit_code.\n"
        "- count: Total number of matching tasks.\n"
        "Usage guideline: Use this to discover active background jobs or audit recently completed asynchronous commands."
    ),
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
