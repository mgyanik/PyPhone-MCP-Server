"""查询异步后台任务状态工具。"""

from __future__ import annotations

from typing import Any

from src.core import logging as structured_logging
from src.core.task_store import task_store
from src.registry import mcp


@mcp.tool(
    name="get_task_status",
    description=(
        "Query status, runtime duration, exit code, and terminal stdout/stderr of an asynchronous background task.\n"
        "Parameters:\n"
        "- task_id (str): The task ID returned by run_background_command.\n"
        "Returns:\n"
        "- status: 'running', 'done', 'failed', 'canceled', 'denied', or 'not_found'.\n"
        "- duration: Total execution time in seconds.\n"
        "- exit_code: Process returncode (0 for success, non-zero for error, None while running).\n"
        "- output: Full captured stdout and stderr (None while running, captured upon completion).\n"
        "Usage guideline: Poll this tool every 1~3 seconds after starting a background command until status becomes 'done' or 'failed'."
    ),
    annotations={"readOnlyHint": True},
)
def get_task_status(task_id: str) -> dict[str, Any]:
    task = task_store.get(task_id)
    if not task:
        return {
            "status": "not_found",
            "task_id": task_id,
            "output": None,
            "exit_code": None,
            "duration": 0.0,
        }

    status = task.status
    duration = task.duration
    exit_code = task.exit_code

    if status == "running":
        output = None
    elif status == "done":
        output = task.output
    elif status == "failed":
        output = task.output or task.error
    elif status == "canceled":
        output = task.output or "canceled"
    else:
        output = task.output

    res = {
        "status": status,
        "task_id": task_id,
        "output": output,
        "exit_code": exit_code,
        "duration": duration,
    }

    structured_logging.structured(
        "query_task_status",
        task_id=task_id,
        status=status,
        duration=duration,
        exit_code=exit_code,
    )
    return res
