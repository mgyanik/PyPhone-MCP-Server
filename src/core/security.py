import os
from src.config import TERMUX_HOME

def resolve_safe_path(requested_path: str) -> str:
    """
    Resolve a path and ensure it stays within the TERMUX_HOME sandbox.
    Handles absolute paths and relative paths (including ../ escapes).
    """
    if os.path.isabs(requested_path):
        abs_path = os.path.normpath(requested_path)
    else:
        abs_path = os.path.normpath(os.path.join(TERMUX_HOME, requested_path))
        
    if not abs_path.startswith(TERMUX_HOME):
        raise ValueError(
            f"Security Error: Path '{requested_path}' escapes the sandbox. "
            f"All operations are restricted to {TERMUX_HOME}."
        )
    return abs_path