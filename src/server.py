"""标准库实现的轻量高并发 MCP Streamable HTTP 服务端。"""

from __future__ import annotations

import json
import select
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from src.config import HOST, PORT, AUTH_TOKEN
from src.core import protocol
from src.core.session import session_manager
from src.registry import load_tools, registry

# 向后兼容测试用例直接访问的属性
_active_sessions = session_manager._sessions

# 连接与请求体保护参数
MAX_REQUEST_BYTES = 4 * 1024 * 1024  # 单次 POST 请求体上限 4MB
SSE_KEEPALIVE_INTERVAL = 15.0  # SSE 保活间隔（秒）
SSE_MAX_LIFETIME = 600.0  # SSE 连接最大存活时长（秒）
SSE_MAX_CONNECTIONS = 16  # 并发 SSE 连接上限，防止线程无限累积

_sse_active = 0
_sse_lock = threading.Lock()


def _acquire_sse_slot() -> bool:
    """占用一个 SSE 连接名额；超限返回 False。"""
    global _sse_active
    with _sse_lock:
        if _sse_active >= SSE_MAX_CONNECTIONS:
            return False
        _sse_active += 1
    return True


def _release_sse_slot() -> None:
    """释放 SSE 连接名额。"""
    global _sse_active
    with _sse_lock:
        if _sse_active > 0:
            _sse_active -= 1



class MCPRequestHandler(BaseHTTPRequestHandler):
    """处理 MCP JSON-RPC 2.0 协议请求。"""

    protocol_version = "HTTP/1.1"
    server_version = "phone-mcp-py/0.2.0"
    # 单连接最长静默等待，避免半开连接永久占用工作线程（大于 take_github 的 60s 子进程超时）
    timeout = 75
    _sse_slot = False

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"[HTTP] {self.address_string()} - {format % args}\n")

    def _token_ok(self) -> bool:
        """配置 MCP_AUTH_TOKEN 时校验 Bearer 令牌；未配置时仅放行回环地址。"""
        if AUTH_TOKEN:
            header = self.headers.get("Authorization", "")
            return header.strip() == f"Bearer {AUTH_TOKEN}"
        peer = (self.client_address or ("",))[0]
        return peer in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _send_json(self, data: dict[str, Any], status: int = 200, session_id: str | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        if session_id:
            self.send_header("Mcp-Session-Id", session_id)
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str, req_id: Any = None, status: int = 400) -> None:
        self._send_json(protocol.make_error(req_id, code, message), status=status)

    def finish(self) -> None:
        """请求收尾：确保 SSE 连接名额一定被释放。"""
        try:
            super().finish()
        finally:
            if getattr(self, "_sse_slot", False):
                self._sse_slot = False
                _release_sse_slot()

    def do_OPTIONS(self) -> None:
        """CORS 预检响应。"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Mcp-Session-Id")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        """GET /mcp 支持 SSE 流式长连接握手与周期保活，允许客户端自动重连。"""
        if self.path != "/mcp":
            self.send_response(404)
            self.end_headers()
            return

        client_session = self.headers.get("Mcp-Session-Id")
        if client_session:
            session_manager.validate_or_recover(client_session)

        if not self._token_ok():
            self._send_error(protocol.INVALID_REQUEST, "Unauthorized", status=401)
            return

        if not _acquire_sse_slot():
            self._send_error(
                protocol.INVALID_REQUEST,
                f"Too many concurrent SSE connections (limit {SSE_MAX_CONNECTIONS})",
                status=503,
            )
            return
        self._sse_slot = True

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        if client_session:
            self.send_header("Mcp-Session-Id", client_session)
        self.end_headers()

        try:
            self.wfile.write(b": keepalive\n\n")
            self.wfile.flush()

            # 单元测试环境注入退出开关或无实际套接字时快速返回
            if getattr(self, "_no_sse_loop", False):
                return
            try:
                self.wfile.fileno()
            except Exception:
                return

            deadline = time.monotonic() + SSE_MAX_LIFETIME
            while time.monotonic() < deadline:
                try:
                    readable, _, _ = select.select(
                        [self.connection], [], [], SSE_KEEPALIVE_INTERVAL
                    )
                except (OSError, ValueError):
                    break
                if readable:
                    # 对端已关闭连接，主动退出，释放线程
                    break
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_POST(self) -> None:
        """处理主要 MCP RPC 调用。"""
        if self.path != "/mcp":
            self.send_response(404)
            self.end_headers()
            return

        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            self._send_error(
                protocol.INVALID_REQUEST,
                "Chunked transfer-encoding is not supported; send Content-Length",
                status=400,
            )
            return

        if not self._token_ok():
            self._send_error(protocol.INVALID_REQUEST, "Unauthorized", status=401)
            return

        content_length_hdr = self.headers.get("Content-Length")
        if not content_length_hdr:
            self._send_error(protocol.INVALID_REQUEST, "Missing Content-Length header", status=400)
            return

        try:
            length = int(content_length_hdr)
        except ValueError:
            self._send_error(protocol.INVALID_REQUEST, "Invalid Content-Length header", status=400)
            return

        if length < 0 or length > MAX_REQUEST_BYTES:
            self.close_connection = True
            self._send_error(
                protocol.INVALID_REQUEST,
                f"Request body length {length} exceeds limit {MAX_REQUEST_BYTES} bytes",
                status=413,
            )
            return

        try:
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body)
        except Exception as e:
            self._send_error(protocol.PARSE_ERROR, f"Parse error: {e}", status=400)
            return

        if not isinstance(payload, dict):
            self._send_error(
                protocol.INVALID_REQUEST,
                "Batch or non-object JSON payload is not supported",
                status=400,
            )
            return

        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})

        # 通知类请求返回 202
        if method and method.startswith("notifications/"):
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # 1. 协议握手 (initialize)
        if method == "initialize":
            session_id = session_manager.create()
            resp = protocol.make_response(
                req_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "phone-mcp-py",
                        "version": "0.2.0",
                    },
                },
            )
            self._send_json(resp, status=200, session_id=session_id)
            return

        # 2. 会话鉴权与重启恢复
        client_session = self.headers.get("Mcp-Session-Id")
        if not client_session:
            self._send_error(protocol.INVALID_SESSION, "Missing Mcp-Session-Id header", req_id=req_id, status=400)
            return

        session_manager.validate_or_recover(client_session)

        # 3. 探活 (ping)
        if method == "ping":
            self._send_json(protocol.make_response(req_id, {}), status=200, session_id=client_session)
            return

        # 4. 列出工具 (tools/list)
        if method == "tools/list":
            tools = [tool.to_mcp_format() for tool in registry.list_tools()]
            self._send_json(
                protocol.make_response(req_id, {"tools": tools}),
                status=200,
                session_id=client_session,
            )
            return

        # 5. 调用工具 (tools/call)
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                result_data = registry.call_tool(tool_name, arguments)
                resp = protocol.wrap_tool_result(req_id, result_data, is_error=False)
                self._send_json(resp, status=200, session_id=client_session)
            except Exception as e:
                resp = protocol.wrap_tool_result(req_id, f"Error executing tool '{tool_name}': {e}", is_error=True)
                self._send_json(resp, status=200, session_id=client_session)
            return

        # 未知方法
        self._send_error(protocol.METHOD_NOT_FOUND, f"Method not found: {method}", req_id=req_id, status=404)


class MCPHTTPServer(ThreadingHTTPServer):
    """提高连接排队上限，避免默认 backlog 被半开连接占满后丢弃新连接。"""

    daemon_threads = True
    request_queue_size = 128
    allow_reuse_address = True


def run_server(host: str = HOST, port: int = PORT) -> None:
    load_tools()
    server_address = (host, port)
    httpd = MCPHTTPServer(server_address, MCPRequestHandler)
    print(f"[phone-mcp-py] listening on {host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
