"""查询异步任务状态工具。"""

from __future__ import annotations

from typing import Any

from src import logging as structured_logging
from src.registry import mcp
from src.task_store import task_store


@mcp.tool(
    name="get_task_status",
    annotations={"readOnlyHint": True},
)
def get_task_status(task_id: str) -> dict[str, Any]:
    """查询任务状态。返回 running / done / failed 及输出。
    只读，可与其他只读操作并发调用。"""
    task = task_store.get(task_id)
    if not task:
        return {
            "status": "not_found",
            "task_id": task_id,
            "output": None,
            "exit_code": None,
            "duration": 0.0,
            "summary": f"未找到任务: {task_id}",
        }

    status = task.status
    duration = task.duration
    exit_code = task.exit_code

    if status == "running":
        output = "结果不可用（任务执行中）"
        summary = f"任务正在运行中，耗时 {duration:.1f}s"
    elif status == "done":
        output = task.output
        summary = f"任务执行完成，退出码 {exit_code}"
    elif status == "failed":
        output = task.output or task.error
        summary = f"任务执行失败，退出码 {exit_code}"
    elif status == "canceled":
        output = task.output or "任务已被取消"
        summary = f"任务已被取消，耗时 {duration:.1f}s"
    else:
        output = task.output
        summary = f"任务状态: {status}"

    res = {
        "status": status,
        "task_id": task_id,
        "output": output,
        "exit_code": exit_code,
        "duration": duration,
        "summary": summary,
    }

    structured_logging.structured(
        "query_task_status",
        task_id=task_id,
        status=status,
        duration=duration,
        exit_code=exit_code,
    )
    return res
