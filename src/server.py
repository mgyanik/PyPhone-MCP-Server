"""标准库实现的轻量 MCP Streamable HTTP 服务端。"""

from __future__ import annotations

import json
import sys
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from src import logging as structured_logging
from src.registry import load_tools, registry

# 活跃的 Session 集合
_active_sessions: set[str] = set()

HOST = "127.0.0.1"
PORT = 3001


class MCPRequestHandler(BaseHTTPRequestHandler):
    """处理 MCP JSON-RPC 2.0 协议请求。"""

    protocol_version = "HTTP/1.1"
    server_version = "phone-mcp-py/0.1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # 重定向请求访问日志到 stderr 或结构化日志，不污染标准输出
        sys.stderr.write(f"[HTTP] {self.address_string()} - {format % args}\n")

    def _send_json_rpc(self, data: dict[str, Any], status: int = 200, session_id: str | None = None) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if session_id:
            self.send_header("Mcp-Session-Id", session_id)
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str, req_id: Any = None, status: int = 400) -> None:
        self._send_json_rpc(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": code,
                    "message": message,
                },
            },
            status=status,
        )

    def do_GET(self) -> None:
        """GET /mcp 返回 405，明确告知客户端不支持 SSE 长连接。
        选 405 而非 501：Kelivo 把 >=500 当可重试，会死循环；
        405 属于不可重试的 4xx，客户端会立即退出后台轮询。"""
        self.send_response(405)
        self.send_header("Allow", "POST")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/mcp":
            self.send_response(404)
            self.end_headers()
            return

        content_length_hdr = self.headers.get("Content-Length")
        if not content_length_hdr:
            self._send_error(-32600, "Missing Content-Length header", status=400)
            return

        try:
            length = int(content_length_hdr)
            raw_body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw_body)
        except Exception as e:
            self._send_error(-32700, f"Parse error: {e}", status=400)
            return

        req_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params", {})

        # 处理通知类请求（以 notifications/ 开头，根据规范返回 202 空体）
        if method and method.startswith("notifications/"):
            self.send_response(202)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        # 1. 初始化握手 (initialize)
        if method == "initialize":
            session_id = uuid.uuid4().hex
            _active_sessions.add(session_id)
            structured_logging.structured("mcp_session_initialized", session_id=session_id)
            
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": "phone-mcp-py",
                        "version": "0.1.0",
                    },
                },
            }
            self._send_json_rpc(resp, status=200, session_id=session_id)
            return

        # 2. 校验 Mcp-Session-Id 头
        client_session = self.headers.get("Mcp-Session-Id")
        if not client_session or client_session not in _active_sessions:
            self._send_error(-32001, "Invalid or missing Mcp-Session-Id header", req_id=req_id, status=400)
            return

        # ping 探活
        if method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            self._send_json_rpc(resp, status=200, session_id=client_session)
            return

        # 3. 列出工具 (tools/list)
        if method == "tools/list":
            tools = [tool.to_mcp_format() for tool in registry.list_tools()]
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": tools,
                },
            }
            self._send_json_rpc(resp, status=200, session_id=client_session)
            return

        # 4. 调用工具 (tools/call)
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            try:
                result_data = registry.call_tool(tool_name, arguments)
                # 遵循 MCP 规范封装 content
                text_content = (
                    json.dumps(result_data, ensure_ascii=False)
                    if not isinstance(result_data, str)
                    else result_data
                )
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": text_content,
                            }
                        ],
                        "isError": False,
                    },
                }
                self._send_json_rpc(resp, status=200, session_id=client_session)
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Error executing tool '{tool_name}': {e}",
                            }
                        ],
                        "isError": True,
                    },
                }
                self._send_json_rpc(resp, status=200, session_id=client_session)
            return

        # 未知方法
        self._send_error(-32601, f"Method not found: {method}", req_id=req_id, status=404)


def run_server(host: str = HOST, port: int = PORT) -> None:
    load_tools()
    server_address = (host, port)
    httpd = HTTPServer(server_address, MCPRequestHandler)
    print(f"[phone-mcp-py] listening on {host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    run_server()
