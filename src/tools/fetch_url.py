"""基于 Python 标准库实现的轻量可靠 HTTP/HTTPS 请求工具。"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from src.config import MAX_OUTPUT_BYTES
from src.core import logging as structured_logging
from src.registry import mcp


@mcp.tool(
    name="fetch_url",
    description=(
        "Send an HTTP or HTTPS request using Python's standard library (replaces shell 'curl' to eliminate shell quoting and escaping issues).\n"
        "Parameters:\n"
        "- url (str): Fully-qualified URL (e.g. 'http://127.0.0.1:8000/api' or 'https://api.github.com/...').\n"
        "- method (str, default: 'GET'): HTTP verb ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD').\n"
        "- headers (dict, optional): Custom HTTP headers (e.g. {'Content-Type': 'application/json', 'Authorization': 'Bearer ...'}).\n"
        "- body (str, optional): String payload for POST/PUT/PATCH requests (pass a JSON-serialized string when sending JSON).\n"
        "- timeout (float, default: 10.0, max: 30.0): Request timeout in seconds.\n"
        "Returns:\n"
        "- status_code: HTTP response status code (e.g. 200, 404, 500).\n"
        "- headers: Normalized dictionary of response headers.\n"
        "- text: String response body (automatically truncated if exceeding 50KB).\n"
        "- json: Parsed JSON object if response Content-Type is JSON or text is valid JSON.\n"
        "Usage guideline: Use this for querying local APIs, validating web servers, or communicating with external web services without invoking curl in shell."
    ),
    annotations={"destructiveHint": False},
)
def fetch_url(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    start = time.time()
    verb = method.strip().upper()
    req_timeout = max(0.5, min(30.0, float(timeout)))

    data_bytes: bytes | None = None
    if body is not None:
        data_bytes = body.encode("utf-8")

    req_headers = headers.copy() if headers else {}
    # 如果没有设置 User-Agent，给一个默认标识
    if "User-Agent" not in req_headers and "user-agent" not in req_headers:
        req_headers["User-Agent"] = "phone-mcp-py/0.2.0"

    try:
        req = urllib.request.Request(
            url=url.strip(),
            data=data_bytes,
            headers=req_headers,
            method=verb,
        )

        with urllib.request.urlopen(req, timeout=req_timeout) as resp:
            resp_code = resp.status
            resp_headers = dict(resp.headers.items())
            raw_body = resp.read(MAX_OUTPUT_BYTES + 1024)

    except urllib.error.HTTPError as e:
        resp_code = e.code
        resp_headers = dict(e.headers.items()) if e.headers else {}
        try:
            raw_body = e.read(MAX_OUTPUT_BYTES + 1024)
        except Exception:
            raw_body = b""
    except Exception as e:
        duration = round(time.time() - start, 4)
        return {
            "status": "error",
            "url": url,
            "method": verb,
            "error": str(e),
            "status_code": None,
            "duration": duration,
        }

    duration = round(time.time() - start, 4)
    text_content = raw_body.decode("utf-8", errors="replace")
    truncated = len(raw_body) > MAX_OUTPUT_BYTES
    if truncated:
        text_content = text_content[:MAX_OUTPUT_BYTES] + "\n... [body truncated: exceeded 50KB] ..."

    # 尝试解析 JSON
    parsed_json = None
    try:
        if text_content.strip().startswith(("{", "[")):
            parsed_json = json.loads(raw_body.decode("utf-8", errors="ignore"))
    except Exception:
        pass

    structured_logging.structured(
        "fetch_url_completed",
        url=url,
        method=verb,
        status_code=resp_code,
        duration=duration,
    )

    return {
        "status": "success",
        "url": url,
        "method": verb,
        "status_code": resp_code,
        "headers": resp_headers,
        "text": text_content,
        "json": parsed_json,
        "truncated": truncated,
        "duration": duration,
    }
