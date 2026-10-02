"""启动长时间异步任务工具。"""

from __future__ import annotations

from typing import Any

from src import logging as structured_logging
from src import policy
from src.registry import mcp
from src.task_store import task_store


@mcp.tool(
    name="start_task",
    annotations={"destructiveHint": True},
)
def start_task(command: str, cwd: str = ".") -> dict[str, Any]:
    """启动长时间任务（编译/测试/构建/安装依赖）。
    立即返回 task_id，不等待完成。
    返回后若存在不依赖此任务的操作，先执行它们；
    若无，结束回合并提醒用户完成后回复。"""
    cmd = command.strip()

    # 1. 策略引擎检查，不允许绕过
    policy_res = policy.evaluate(cmd)
    
    if policy_res.requires_confirmation:
        structured_logging.structured(
            "task_policy_requires_manual",
            command=cmd,
            reason=policy_res.reason,
        )
        return {
            "status": "denied",
            "task_id": None,
            "summary": f"需用户手动执行: {cmd}",
            "hint": "服务端不会自动执行此命令，请让用户手动运行",
        }

    if policy_res.is_denied:
        structured_logging.structured(
            "task_policy_deny",
            command=cmd,
            reason=policy_res.reason,
        )
        return {
            "status": "denied",
            "task_id": None,
            "summary": f"命令被拒绝: {cmd}",
            "hint": f"安全策略禁止执行: {policy_res.reason}",
        }

    # 2. 异步启动子进程，非阻塞立即返回
    task = task_store.spawn(cmd, cwd=cwd)

    summary = f"已后台启动: {cmd}"
    hint = "返回后若存在不依赖此任务的操作，先执行它们；若无，结束回合并提醒用户完成后回复。"

    structured_logging.structured(
        "start_task_dispatched",
        task_id=task.task_id,
        command=cmd,
        cwd=cwd,
        status="running",
    )

    return {
        "status": "running",
        "task_id": task.task_id,
        "summary": summary,
        "hint": hint,
    }
