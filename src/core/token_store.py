import os
import json
import uuid
import hashlib
from src.config import TERMUX_HOME

TOKEN_FILE = os.path.join(TERMUX_HOME, ".mcp_ask_tokens.json")

def generate_token(action: str, params: dict) -> str:
    """Generate a one-time token bound to a specific action and parameter signature."""
    token = str(uuid.uuid4())
    params_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    data = _load()
    data[token] = {"action": action, "params_hash": params_hash}
    _save(data)
    return token

def validate_and_consume(token: str, action: str, params: dict) -> bool:
    """Validate token matches the action and params, then consume it."""
    data = _load()
    if token not in data:
        return False
    record = data[token]
    params_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    
    if record["action"] == action and record["params_hash"] == params_hash:
        del data[token]
        _save(data)
        return True
    return False

def _load() -> dict:
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save(data: dict) -> None:
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)
