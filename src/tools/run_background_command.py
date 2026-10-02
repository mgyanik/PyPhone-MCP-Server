"""异步后台执行长命令工具。"""

from __future__ import annotations

import os
from typing import Any

from src import logging as structured_logging
from src import policy
from src.registry import mcp
from src.task_store import task_store


@mcp.tool(
    name="run_background_command",
    description="Spawn long-running background command asynchronously. Returns task_id immediately.",
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


# 保持向后兼容别名
start_task_for_backend = run_background_command
