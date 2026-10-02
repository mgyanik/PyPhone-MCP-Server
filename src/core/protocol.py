"""MCP JSON-RPC 2.0 协议层：标准化封装响应、错误及内容转换。"""

from __future__ import annotations

import json
from typing import Any

# JSON-RPC 2.0 标准错误码
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
INVALID_SESSION = -32001


def make_response(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    """构造成功的 JSON-RPC 2.0 响应。"""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "result": result,
    }


def make_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    """构造失败的 JSON-RPC 2.0 响应。"""
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def wrap_tool_result(req_id: Any, data: Any, is_error: bool = False) -> dict[str, Any]:
    """遵循 MCP 规范封装 tools/call 响应。"""
    if isinstance(data, str):
        text_content = data
    else:
        text_content = json.dumps(data, ensure_ascii=False)

    return make_response(
        req_id,
        {
            "content": [
                {
                    "type": "text",
                    "text": text_content,
                }
            ],
            "isError": is_error,
        },
    )
