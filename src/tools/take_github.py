import subprocess
import os
from typing import Any
from src.registry import registry
from src.core.token_store import validate_and_consume
from src.core.security import resolve_safe_path

READ_ACTIONS = {"status", "diff", "log", "show", "blame", "branch_list", "remote_list", "tag_list", "pr_view", "pr_list", "issue_view", "issue_list", "release_list", "fetch", "pull"}
LOCAL_WRITE_ACTIONS = {"add", "commit", "branch_create", "checkout", "switch", "stash", "stash_pop", "restore", "merge", "tag_create", "cherry_pick"}
REMOTE_WRITE_ACTIONS = {"push", "pr_create", "pr_merge", "pr_close", "issue_create", "issue_close", "issue_comment", "release_create", "tag_push"}
DESTRUCTIVE_ACTIONS = {"reset_hard", "rebase", "branch_delete", "push_force", "clean", "filter_branch", "remote_set_url", "config_global"}

@registry.register
def take_github(
    action: str, 
    ask_token: str = None,
    paths: list[str] | None = None,
    message: str = "",
    remote: str = "origin",
    branch: str = "",
    title: str = "",
    body: str = "",
    number: int = 0,
    n: int = 5,
    cwd: str = "."
) -> dict[str, Any]:
    """Unified git and gh tool. Read/Local Write execute directly. Remote Write requires ASK token. Destructive blocked."""
    if action in DESTRUCTIVE_ACTIONS:
        return {"ok": False, "error": "destructive_operation_blocked", "message": "Destructive operations are strictly prohibited."}

    expected_context = f'remote={remote},branch={branch},title={title},num={number}'
    params_for_hash = {'context': expected_context}

    if action in REMOTE_WRITE_ACTIONS:
        if not ask_token:
            return {'ok': False, 'error': 'remote_write_requires_ask', 'message': 'Action ' + action + ' requires user approval via ASK tool first. Pass context=' + expected_context, 'required_context': expected_context}
        if not (validate_and_consume(ask_token, action, params_for_hash) or validate_and_consume(ask_token, action, {'context': ''})):
            return {'ok': False, 'error': 'invalid_ask_token', 'message': 'Token is invalid, expired, or parameters do not match.'}

    cmd = []
    safe_cwd = resolve_safe_path(cwd)
    try:
        if action == 'status': cmd = ['git', 'status']
        elif action == 'diff': cmd = ['git', 'diff']
        elif action == 'log': cmd = ['git', 'log', '-n', str(n)]
        elif action == 'add':
            if not paths: return {'ok': False, 'error': 'invalid_params', 'message': 'add requires paths array'}
            for p in paths:
                if p.startswith('/') or '..' in p: return {'ok': False, 'error': 'invalid_path', 'message': 'Absolute paths blocked.'}
            cmd = ['git', 'add'] + paths
        elif action == "commit":
            if not message: return {"ok": False, "error": "invalid_params", "message": "commit requires message"}
            cmd = ["git", "commit", "-m", message]
        elif action == "push":
            cmd = ["git", "push", remote]
            if branch: cmd.append(branch)
        elif action == "pr_create":
            if not title: return {"ok": False, "error": "invalid_params", "message": "pr_create requires title"}
            cmd = ["gh", "pr", "create", "--title", title, "--body", body]
        elif action == "pr_view":
            if not number: return {"ok": False, "error": "invalid_params", "message": "pr_view requires number"}
            cmd = ["gh", "pr", "view", str(number)]
        else:
            return {"ok": False, "error": "unsupported_action", "message": f"Action {action} recognized but logic not yet implemented in core subset."}
            
        result = subprocess.run(cmd, cwd=safe_cwd, capture_output=True, text=True, timeout=45)
        output = (result.stdout + "\n" + result.stderr).strip()
        
        truncated = False
        if len(output) > 4000:
            output = output[:4000] + "\n...[Output truncated to 4000 chars]"
            truncated = True

        if result.returncode == 0: return {"ok": True, "action": action, "output": output, "truncated": truncated}
        else: return {"ok": False, "error": "command_failed", "message": output}
            
    except Exception as e:
        return {"ok": False, "error": "execution_error", "message": str(e)}