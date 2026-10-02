"""实时前台同步执行命令工具。"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any

from src.config import DEFAULT_ENV, MAX_OUTPUT_BYTES, SHELL_BIN, TERMUX_HOME
from src.core import logging as structured_logging
from src.core import policy
from src.registry import mcp


def _truncate_output(text: str, max_bytes: int = MAX_OUTPUT_BYTES) -> str:
    raw_bytes = text.encode("utf-8", errors="replace")
    if len(raw_bytes) <= max_bytes:
        return text

    head_bytes = raw_bytes[: max_bytes // 2]
    tail_bytes = raw_bytes[-max_bytes // 2 :]

    head_str = head_bytes.decode("utf-8", errors="ignore")
    tail_str = tail_bytes.decode("utf-8", errors="ignore")

    omitted_bytes = len(raw_bytes) - len(head_bytes) - len(tail_bytes)
    return f"{head_str}\n\n... [output truncated: omitted {omitted_bytes} bytes] ...\n\n{tail_str}"


@mcp.tool(
    name="run_command",
    description=(
        "⚠️ CRITICAL: 仅供用于工具做不到的时候使用！(ONLY use this tool when dedicated tools CANNOT accomplish the task).\n"
        "专职工具替代清单（严禁使用 shell 命令替代）：\n"
        "- 读取文件：必须使用 read_file 或 read_file_lines（切勿使用 cat, head, tail, sed）\n"
        "- 编辑/创建文件：必须使用 edit_file（切勿使用 echo >, tee, sed -i）\n"
        "- 移动/复制/删除文件：必须使用 manage_file（切勿使用 mv, cp, rm）\n"
        "- 查看文件属性/哈希：必须使用 get_file_info（切勿使用 stat, ls -l, md5sum, sha256sum）\n"
        "- 浏览目录内容：必须使用 list_dir（切勿使用 ls, find -maxdepth）\n"
        "- 搜索文本关键字：必须使用 search_text（切勿使用 grep, rg, ack）\n"
        "- 发送网络请求：必须使用 fetch_url（切勿使用 curl, wget 拼接命令，易发生转义失败）\n"
        "- 查杀系统进程：必须使用 find_process / kill_process（切勿使用 ps | grep, lsof, pkill -9）\n"
        "- 查询设备状态：必须使用 get_device_status（切勿使用 df, free, top）\n"
        "适用场景：仅用于专用工具无法覆盖的必要操作（如 git commit/push、编译前后的特定 CLI 交互）。\n"
        "硬性执行约束：默认硬执行超时仅为 5 秒 (timeout=5.0)。若预估耗时可能超过 5 秒（如编译构建、下载大文件、启动长服务、批量跑测），必须改用 run_background_command 派发后台任务，否则会被 5 秒强制中断！"
    ),
    annotations={"destructiveHint": True},
)
def run_command(command: str, cwd: str = ".", timeout: float = 5.0) -> dict[str, Any]:
    cmd = command.strip()
    start_time = time.time()

    policy_res = policy.evaluate(cmd)
    if policy_res.is_denied:
        structured_logging.structured(
            "run_command_denied",
            command=cmd,
            reason=policy_res.reason,
        )
        return {
            "status": "denied",
            "output": "",
            "error": f"Blocked by policy: {policy_res.reason}",
            "exit_code": -1,
            "duration": 0.0,
        }

    if policy_res.requires_confirmation:
        structured_logging.structured(
            "run_command_ask_executed",
            command=cmd,
            reason=policy_res.reason,
        )

    target_cwd = cwd if os.path.isabs(cwd) else os.path.join(TERMUX_HOME, cwd)
    if not os.path.exists(target_cwd):
        target_cwd = TERMUX_HOME

    try:
        proc = subprocess.Popen(
            [SHELL_BIN, "-c", cmd],
            cwd=target_cwd,
            env=DEFAULT_ENV,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception as e:
        duration = round(time.time() - start_time, 3)
        structured_logging.structured(
            "run_command_spawn_error",
            command=cmd,
            error=str(e),
            duration=duration,
        )
        return {
            "status": "error",
            "output": "",
            "error": str(e),
            "exit_code": -1,
            "duration": duration,
        }

    timed_out = False
    try:
        stdout_data, stderr_data = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        try:
            stdout_data, stderr_data = proc.communicate(timeout=2.0)
        except Exception:
            stdout_data, stderr_data = "", ""

    duration = round(time.time() - start_time, 3)
    exit_code = -1 if timed_out else proc.returncode

    output = stdout_data.strip() if stdout_data else ""
    stderr_clean = stderr_data.strip() if stderr_data else ""
    if stderr_clean:
        if output:
            output += "\n---stderr---\n" + stderr_clean
        else:
            output = stderr_clean

    output = _truncate_output(output)
    status = "timeout" if timed_out else ("success" if exit_code == 0 else "error")

    structured_logging.structured(
        "run_command_finished",
        command=cmd,
        status=status,
        exit_code=exit_code,
        duration=duration,
        timed_out=timed_out,
    )

    return {
        "status": status,
        "output": output,
        "exit_code": exit_code,
        "duration": duration,
    }


# 向后兼容别名与映射
start_task = run_command
from src.registry import registry
registry.register_alias("start_task", "run_command")

