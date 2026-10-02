"""取消后台进行中任务工具。"""

from __future__ import annotations

from typing import Any

from src.core import logging as structured_logging
from src.core.task_store import task_store
from src.registry import mcp


@mcp.tool(
    name="cancel_task",
    description="Gracefully terminate a running background task by task_id (uses terminate -> wait -> kill process lifecycle). Fails if task is already finished or nonexistent.",
    annotations={"destructiveHint": True},
)
def cancel_task(task_id: str) -> dict[str, Any]:
    success = task_store.cancel(task_id)
    if success:
        structured_logging.structured("task_cancel_success", task_id=task_id)
        return {
            "status": "success",
            "task_id": task_id,
        }
    else:
        task = task_store.get(task_id)
        structured_logging.structured(
            "task_cancel_failed",
            task_id=task_id,
            current_status=task.status if task else None,
        )
        return {
            "status": "error",
            "task_id": task_id,
            "error": "not found" if not task else f"status is {task.status}",
        }
