"""客户端会话管理：维护连接会话并支持服务重启后的自适应恢复。"""

from __future__ import annotations

import threading
import uuid
from src.core import logging as structured_logging


class SessionManager:
    """线程安全的会话管理器。"""

    def __init__(self) -> None:
        self._sessions: set[str] = set()
        self._lock = threading.Lock()

    def create(self) -> str:
        """创建并记录新会话。"""
        session_id = uuid.uuid4().hex
        with self._lock:
            self._sessions.add(session_id)
        structured_logging.structured("mcp_session_initialized", session_id=session_id)
        return session_id

    def validate_or_recover(self, session_id: str | None) -> bool:
        """校验会话是否合法；若服务此前重启导致会话丢失，自动容错接纳。"""
        if not session_id or not session_id.strip():
            return False

        sid = session_id.strip()
        with self._lock:
            if sid not in self._sessions:
                self._sessions.add(sid)
                structured_logging.structured("mcp_session_recovered", session_id=sid)
            return True

    def exists(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()


session_manager = SessionManager()
