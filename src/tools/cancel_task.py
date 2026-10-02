"""取消任务工具。"""

from __future__ import annotations

from typing import Any

from src import logging as structured_logging
from src.registry import mcp
from src.task_store import task_store


@mcp.tool(
    name="cancel_task",
    annotations={"destructiveHint": True},
)
def cancel_task(task_id: str) -> dict[str, Any]:
    """取消进行中的任务。"""
    success = task_store.cancel(task_id)
    if success:
        summary = f"成功取消任务: {task_id}"
        structured_logging.structured("task_cancel_success", task_id=task_id)
        return {
            "status": "success",
            "task_id": task_id,
            "summary": summary,
        }
    else:
        task = task_store.get(task_id)
        if not task:
            summary = f"取消失败: 任务 {task_id} 不存在"
        else:
            summary = f"取消失败: 任务 {task_id} 当前状态为 {task.status}，非 running 状态"
        structured_logging.structured(
            "task_cancel_failed",
            task_id=task_id,
            current_status=task.status if task else None,
        )
        return {
            "status": "error",
            "task_id": task_id,
            "summary": summary,
        }
