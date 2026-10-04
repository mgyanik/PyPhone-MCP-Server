import os
import json
import time
import uuid
from typing import Literal
from src.config import TERMUX_HOME

AUTH_DIR = os.path.join(TERMUX_HOME, ".mcp_auth")
os.makedirs(AUTH_DIR, exist_ok=True)

PENDING_FILE = os.path.join(AUTH_DIR, "pending.json")
WHITELIST_FILE = os.path.join(AUTH_DIR, "whitelist.json")
BLACKLIST_FILE = os.path.join(AUTH_DIR, "blacklist.json")
LOG_FILE = os.path.join(AUTH_DIR, "exec_log.jsonl")

def _atomic_write(filepath: str, data: dict | list) -> None:
    tmp = f"{filepath}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, filepath)

def _read_json(filepath: str, default: Any = None) -> Any:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default if default is not None else {}

def _match_rule(command_tokens: list[str], rule: dict) -> bool:
    rule_tokens = rule.get("tokens", [])
    match_type = rule.get("match", "prefix") # exact, prefix
    
    if not rule_tokens:
        return False
        
    if match_type == "exact":
        return command_tokens == rule_tokens
    else: # prefix
        if len(command_tokens) < len(rule_tokens):
            return False
        return command_tokens[:len(rule_tokens)] == rule_tokens

def _find_longest_match(command_tokens: list[str], entries: list[dict]) -> dict | None:
    best_match = None
    max_len = -1
    for rule in entries:
        if _match_rule(command_tokens, rule):
            rule_len = len(rule.get("tokens", []))
            if rule_len > max_len:
                max_len = rule_len
                best_match = rule
    return best_match

def evaluate_command(command_tokens: list[str]) -> tuple[Literal["allow", "deny", "unknown"], dict | None]:
    """Check command against blacklist, then whitelist. Returns (status, matching_rule)."""
    if not command_tokens:
        return "deny", {"reason": "empty_command"}

    # 1. Check blacklist first
    blacklist = _read_json(BLACKLIST_FILE, {"entries": []})
    bl_match = _find_longest_match(command_tokens, blacklist.get("entries", []))
    if bl_match:
        return "deny", bl_match
        
    # 2. Check whitelist
    whitelist = _read_json(WHITELIST_FILE, {"entries": []})
    wl_match = _find_longest_match(command_tokens, whitelist.get("entries", []))
    if wl_match:
        return "allow", wl_match
        
    return "unknown", None

def add_pending_request(command_tokens: list[str], cwd: str, reason: str, context: str) -> str:
    pending = _read_json(PENDING_FILE, [])
    req_id = f"req-{uuid.uuid4().hex[:8]}"
    
    # Check if exactly same request is already pending
    for p in pending:
        if p.get("command") == command_tokens and p.get("cwd") == cwd:
            return p.get("request_id")
            
    pending.append({
        "request_id": req_id,
        "command": command_tokens,
        "cwd": cwd,
        "reason": reason,
        "agent_context": context,
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    })
    _atomic_write(PENDING_FILE, pending)
    return req_id

def log_execution(command_tokens: list[str], rule_hit: dict, exit_code: int, result_status: str) -> None:
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "command": command_tokens,
        "rule": rule_hit,
        "exit_code": exit_code,
        "result": result_status
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
