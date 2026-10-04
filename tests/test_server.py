from email.message import Message
from io import BytesIO
import json
from src.server import MCPRequestHandler
from src import server as server_module

class DummyServer:
    server_address = ("127.0.0.1", 3000)

def _call_handler(method: str, path: str = "/mcp", body: bytes = b"", headers: dict[str, str] | None = None):
    server_module.load_tools()
    
    rfile = BytesIO(body)
    wfile = BytesIO()
    
    handler = MCPRequestHandler.__new__(MCPRequestHandler)
    handler.server = DummyServer()
    handler.client_address = ("127.0.0.1", 12345)
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.command = method
    handler.path = path
    handler.request_version = "HTTP/1.1"
    handler.rfile = rfile
    handler.wfile = wfile
    handler._no_sse_loop = True
    
    msg = Message()
    if headers:
        for k, v in headers.items():
            msg[k] = v
    if body and not msg.get("Content-Length"):
        msg["Content-Length"] = str(len(body))
    
    handler.headers = msg
    
    if method == "GET":
        handler.do_GET()
    elif method == "POST":
        handler.do_POST()
    elif method == "OPTIONS":
        handler.do_OPTIONS()
        
    return wfile.getvalue().decode("utf-8")

def test_get_sse_stream_works():
    server_module._active_sessions.clear()
    raw_resp = _call_handler("GET", "/mcp")
    assert "200 OK" in raw_resp
    assert "text/event-stream" in raw_resp
    assert ": keepalive" in raw_resp

def test_post_still_works():
    server_module._active_sessions.clear()
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }).encode("utf-8")
    
    raw_resp = _call_handler("POST", "/mcp", body=body, headers={"Content-Type": "application/json"})
    assert "200 OK" in raw_resp
    assert "Mcp-Session-Id:" in raw_resp

def test_session_auto_recovered_after_restart():
    # 模拟服务重启导致内存会话清空
    server_module._active_sessions.clear()
    assert len(server_module._active_sessions) == 0

    # 客户端使用原 session 发送 ping 请求
    old_session = "test_session_recovered_123"
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "ping",
    }).encode("utf-8")

    raw_resp = _call_handler("POST", "/mcp", body=body, headers={
        "Content-Type": "application/json",
        "Mcp-Session-Id": old_session,
    })
    assert "200 OK" in raw_resp
    assert old_session in server_module._active_sessions

def test_options_cors():
    raw_resp = _call_handler("OPTIONS", "/mcp")
    assert "204 No Content" in raw_resp
    assert "Access-Control-Allow-Origin: *" in raw_resp

def test_tools_list_all_renamed_tools():
    session_id = "test_tools_list_session"
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/list",
    }).encode("utf-8")
    raw_resp = _call_handler("POST", "/mcp", body=body, headers={
        "Content-Type": "application/json",
        "Mcp-Session-Id": session_id,
    })
    assert "200 OK" in raw_resp
    body_part = raw_resp.split("\r\n\r\n", 1)[1]
    data = json.loads(body_part)
    names = {tool["name"] for tool in data["result"]["tools"]}
    expected = {
        "read_file",
        "read_file_lines",
        "edit__file",
        "manage_file",
        "get_file_info",
        "list_dir",
        "search_text",
        "run_command",
        "run_background_command",
        "get_task_status",
        "list_tasks",
        "cancel_task",
        "fetch_url",
        "find_process",
        "kill_process",
        "get_device_status",
    }
    assert expected == names
