"""异步后台执行长命令工具。"""

from __future__ import annotations

from typing import Any

from src.core import logging as structured_logging
from src.core import policy
from src.core.task_store import task_store
from src.registry import mcp


@mcp.tool(
    name="run_background_command",
    description=(
        "Dispatch long-running commands asynchronously in the background without blocking MCP connection.\n"
        "Parameters:\n"
        "- command (str): Shell command to execute asynchronously.\n"
        "- cwd (str, default: '.'): Working directory relative to Termux home or absolute.\n"
        "When to use:\n"
        "- ALWAYS use this for tasks expected to take > 5 seconds (e.g. 'npm install', 'cargo build', test suites, background servers, git clone/pull of large repos).\n"
        "Workflow:\n"
        "1. Call run_background_command -> receive a 'task_id' immediately.\n"
        "2. Call get_task_status(task_id) to poll execution progress, exit code, and terminal logs.\n"
        "3. Call cancel_task(task_id) if you need to gracefully terminate the running job."
    ),
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


# 向后兼容别名与映射
start_task_for_backend = run_background_command
from src.registry import registry
registry.register_alias("start_task_for_backend", "run_background_command")

