from email.message import Message
from io import BytesIO
import json
from src.server import MCPRequestHandler
from src import server as server_module

class DummyServer:
    server_address = ("127.0.0.1", 3001)

def _call_handler(method: str, path: str = "/mcp", body: bytes = b"", headers: dict[str, str] | None = None):
    server_module._active_sessions.clear()
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
        
    return wfile.getvalue().decode("utf-8")

def test_get_returns_405():
    raw_resp = _call_handler("GET", "/mcp")
    assert "405 Method Not Allowed" in raw_resp
    assert "Allow: POST" in raw_resp

def test_post_still_works():
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
