"""标准库实现的轻量高并发 MCP Streamable HTTP 服务端。"""

from __future__ import annotations

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from src.config import HOST, PORT
from src.core import protocol
from src.core.session import session_manager
from src.registry import load_tools, registry

# 向后兼容测试用例直接访问的属性
_active_sessions = session_manager._sessions


class MCPRequestHandler(BaseHTTPRequestHandler):
    """处理 MCP JSON-RPC 2.0 协议请求。"""

    protocol_version = "HTTP/1.1"
    server_version = "phone-mcp-py/0.2.0"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"[HTTP] {self.address_string()} - {format % args}\n")

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

            while True:
                time.sleep(15)
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

        content_length_hdr = self.headers.get("Content-Length")
        if not content_length_hdr:
            self._send_error(protocol.INVALID_REQUEST, "Missing Content-Length header", status=400)
            return

        try:
            length = int(content_length_hdr)
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body)
        except Exception as e:
            self._send_error(protocol.PARSE_ERROR, f"Parse error: {e}", status=400)
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


def run_server(host: str = HOST, port: int = PORT) -> None:
    load_tools()
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, MCPRequestHandler)
    httpd.daemon_threads = True
    print(f"[phone-mcp-py] listening on {host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
