import json
import shlex
import subprocess
from typing import Any
from src.registry import registry
from src.config import DEFAULT_ENV, SHELL_BIN
from src.core.auth_store import evaluate_command, add_pending_request
from src.core.security import resolve_safe_path

@registry.register
def request_tool(
    action: str, 
    command_str: str = "",
    cwd: str = ".",
    shell: bool = False
) -> dict[str, Any]:
    """
    Unified command tool. All commands need WebUI approval!
    Actions:
    - 'request': Submit a command. Provide 'command_str' (e.g., "npm run build"). Set shell=True for complex shell pipelines/variables.
    - 'exec': Try to execute it. Will fail if not approved.
    - 'ask': Get text to ask the user.
    """
    try:
        if action == "request":
            if not command_str:
                return {"result": "Error: command_str is required"}
            try:
                cmd_list = [SHELL_BIN, "-c", command_str] if shell else shlex.split(command_str)
            except ValueError as e:
                return {"result": f"Error: Command parsing failed: {e}"}
            req_id = add_pending_request(cmd_list, cwd, "Requested by Agent", "")
            return {"result": f"Success: Request {req_id} submitted. Now use action='ask'."}

        elif action == "ask":
            return {"result": f"Please tell the user: 'I need to run: {command_str}. Please approve it in the WebUI at http://127.0.0.1:8080'"}

        elif action == "exec":
            if not command_str:
                return {"result": "Error: command_str is required"}
            try:
                cmd_list = [SHELL_BIN, "-c", command_str] if shell else shlex.split(command_str)
            except ValueError as e:
                return {"result": f"Error: Command parsing failed: {e}"}
            
            status, rule = evaluate_command(cmd_list)
            if status == "deny":
                return {"result": "Blocked: Command is in the blacklist."}
            if status == "unknown":
                return {"result": "Not Approved: Command is not in whitelist. Use action='request' first."}
                
            # Execute
            safe_cwd = resolve_safe_path(cwd)
            res = subprocess.run(cmd_list, cwd=safe_cwd, env=DEFAULT_ENV, capture_output=True, text=True, timeout=60)
            out = (res.stdout + "\n" + res.stderr).strip()
            if len(out) > 3000: out = out[:3000] + "...[truncated]"
            return {"result": f"Executed (Code {res.returncode}):\n{out}"}

        elif action == "list":
            return {"result": "WebUI is running at http://127.0.0.1:8080"}

        else:
            return {"result": f"Error: Unknown action '{action}'"}
            
    except Exception as e:
        return {"result": f"Fatal Python Error: {str(e)}"}
