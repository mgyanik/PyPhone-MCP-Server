"""统一 Git 与 GitHub CLI (gh) 操作网关。

完全开放 git 与 gh 母命令与全部子命令的使用权。
"""

from __future__ import annotations

import shlex
import subprocess
from typing import Any

from src.core.security import resolve_safe_path
from src.registry import registry

# 常见 GitHub CLI (gh) 子命令集，用于自动智能补齐
GH_SUBCOMMANDS = {
    "pr", "issue", "repo", "release", "gist", "run", "workflow",
    "auth", "api", "browse", "codespace", "extension", "project",
    "ruleset", "secret", "variable", "cache", "search"
}


@registry.register
def take_github(
    command: str | None = None,
    action: str | None = None,
    args: list[str] | None = None,
    paths: list[str] | None = None,
    message: str = "",
    remote: str = "origin",
    branch: str = "",
    title: str = "",
    body: str = "",
    number: int = 0,
    n: int = 5,
    cwd: str = ".",
) -> dict[str, Any]:
    """统一 Git 与 GitHub CLI (gh) 操作工具。

    完全开放 git 与 gh 的全部母命令与子命令权限，支持任何参数组合。
    调用方式：
    1. 直接传入完整命令：
       take_github(command="git fetch upstream main")
       take_github(command="git stash push -m 'WIP'")
       take_github(command="git merge upstream/main")
       take_github(command="gh pr list")
    2. 简写命令（智能补齐 git 或 gh）：
       take_github(command="checkout -b feat/test")
       take_github(command="pr list --state open")
    3. 兼容原有结构化 action 参数（全量子命令自动映射，不再报错）。
    """
    try:
        safe_cwd = resolve_safe_path(cwd)
    except Exception as e:
        return {"ok": False, "error": "invalid_cwd", "message": str(e)}

    cmd: list[str] = []

    # 1. 优先解析 command 字符串或 args 列表
    if command:
        try:
            cmd = shlex.split(command)
        except ValueError as e:
            return {"ok": False, "error": "parse_error", "message": f"Command parsing failed: {e}"}
        if args:
            cmd.extend(args)
    elif args:
        cmd = list(args)

    # 2. 如果没有 command/args，则从兼容结构化 action 参数组装
    elif action:
        if action == "status":
            cmd = ["git", "status"]
        elif action == "diff":
            cmd = ["git", "diff"]
            if branch:
                cmd.append(branch)
            if paths:
                cmd.extend(["--"] + paths)
        elif action == "log":
            cmd = ["git", "log", "-n", str(n)]
            if branch:
                cmd.append(branch)
            if paths:
                cmd.extend(["--"] + paths)
        elif action == "add":
            if not paths:
                return {"ok": False, "error": "invalid_params", "message": "add requires paths array"}
            cmd = ["git", "add"] + paths
        elif action == "commit":
            if not message:
                return {"ok": False, "error": "invalid_params", "message": "commit requires message"}
            cmd = ["git", "commit", "-m", message]
        elif action == "push":
            cmd = ["git", "push", remote]
            if branch:
                cmd.append(branch)
        elif action == "pull":
            cmd = ["git", "pull", remote]
            if branch:
                cmd.append(branch)
        elif action == "fetch":
            cmd = ["git", "fetch", remote]
            if branch:
                cmd.append(branch)
        elif action == "merge":
            target = branch or remote
            cmd = ["git", "merge"]
            if target:
                cmd.append(target)
        elif action == "checkout":
            cmd = ["git", "checkout"]
            if branch:
                cmd.append(branch)
            if paths:
                cmd.extend(["--"] + paths)
        elif action == "switch":
            cmd = ["git", "switch", branch] if branch else ["git", "switch"]
        elif action in ("stash", "stash_push"):
            cmd = ["git", "stash", "push"]
            if message:
                cmd.extend(["-m", message])
            if paths:
                cmd.extend(["--"] + paths)
        elif action == "stash_pop":
            cmd = ["git", "stash", "pop"]
        elif action == "stash_list":
            cmd = ["git", "stash", "list"]
        elif action in ("branch", "branch_list"):
            cmd = ["git", "branch", "-a"]
        elif action in ("remote", "remote_list"):
            cmd = ["git", "remote", "-v"]
        elif action == "pr_create":
            if not title:
                return {"ok": False, "error": "invalid_params", "message": "pr_create requires title"}
            cmd = ["gh", "pr", "create", "--title", title, "--body", body]
        elif action == "pr_view":
            cmd = ["gh", "pr", "view"] + ([str(number)] if number else [])
        elif action == "pr_list":
            cmd = ["gh", "pr", "list"]
        elif action == "issue_create":
            if not title:
                return {"ok": False, "error": "invalid_params", "message": "issue_create requires title"}
            cmd = ["gh", "issue", "create", "--title", title, "--body", body]
        elif action == "issue_view":
            cmd = ["gh", "issue", "view"] + ([str(number)] if number else [])
        elif action == "issue_list":
            cmd = ["gh", "issue", "list"]
        else:
            # 任何其它 action，直接作为 git 或 gh 子命令透传执行
            if action.startswith("gh_") or action.startswith("gh-"):
                cmd = ["gh", action[3:]]
            elif action in GH_SUBCOMMANDS:
                cmd = ["gh", action]
            else:
                cmd = ["git", action]
            if branch:
                cmd.append(branch)
            if paths:
                cmd.extend(paths)
        if args:
            cmd.extend(args)

    if not cmd:
        return {"ok": False, "error": "empty_command", "message": "No command or action provided."}

    # 3. 校验母命令：限定为 git 或 gh；若省略则智能自动补齐
    if cmd[0] not in ("git", "gh"):
        if cmd[0] in GH_SUBCOMMANDS:
            cmd.insert(0, "gh")
        else:
            cmd.insert(0, "git")

    # 4. 执行命令（不走 shell，杜绝任何 shell 逃逸注入）
    current_action = action or (cmd[1] if len(cmd) > 1 else cmd[0])
    command_str = " ".join(cmd)
    try:
        result = subprocess.run(
            cmd,
            cwd=safe_cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        output = (result.stdout + "\n" + result.stderr).strip()

        truncated = False
        if len(output) > 4000:
            output = output[:4000] + "\n...[Output truncated to 4000 chars]"
            truncated = True

        if result.returncode == 0:
            return {
                "ok": True,
                "action": current_action,
                "command": command_str,
                "exit_code": 0,
                "output": output,
                "truncated": truncated,
            }
        else:
            return {
                "ok": False,
                "action": current_action,
                "command": command_str,
                "exit_code": result.returncode,
                "error": "command_failed",
                "message": output,
                "output": output,
                "truncated": truncated,
            }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "action": current_action,
            "command": command_str,
            "error": "timeout",
            "message": f"Command timed out after 60s: {command_str}",
        }
    except Exception as e:
        return {
            "ok": False,
            "action": current_action,
            "command": command_str,
            "error": "execution_error",
            "message": str(e),
        }