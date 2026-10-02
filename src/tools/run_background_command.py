"""异步后台执行长命令工具。"""

from __future__ import annotations

from typing import Any

from src.core import logging as structured_logging
from src.core import policy
from src.core.task_store import task_store
from src.registry import mcp


@mcp.tool(
    name="run_background_command",
    description="Spawn long-running background command asynchronously (for tasks > 8s like compiling, downloading, verifying hashes, or long services). Returns task_id immediately. Use get_task_status to query status/output, and cancel_task to terminate the task.",
    annotations={"destructiveHint": True},
)
def run_background_command(command: str, cwd: str = ".") -> dict[str, Any]:
    cmd = command.strip()

    policy_res = policy.evaluate(cmd)
    if policy_res.is_denied:
        structured_logging.structured(
            "run_background_command_deny",
            command=cmd,
            reason=policy_res.reason,
        )
        return {
            "status": "denied",
            "task_id": None,
            "error": f"Blocked by policy: {policy_res.reason}",
        }

    if policy_res.requires_confirmation:
        structured_logging.structured(
            "run_background_command_ask_executed",
            command=cmd,
            reason=policy_res.reason,
        )

    task = task_store.spawn(cmd, cwd=cwd)

    structured_logging.structured(
        "run_background_command_dispatched",
        task_id=task.task_id,
        command=cmd,
        cwd=cwd,
        status="running",
    )

    return {
        "status": "running",
        "task_id": task.task_id,
    }


# 向后兼容别名
start_task_for_backend = run_background_command
