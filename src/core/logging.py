"""结构化日志模块，遵循项目 logging.structured 格式约定。"""

from __future__ import annotations

import json
import logging as _std_logging
import sys
import time
from typing import Any

_logger = _std_logging.getLogger("phone_mcp")
if not _logger.handlers:
    _handler = _std_logging.StreamHandler(sys.stderr)
    _formatter = _std_logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    _logger.setLevel(_std_logging.INFO)


def structured(event: str, **kwargs: Any) -> dict[str, Any]:
    """输出 JSON 格式结构化审计日志。"""
    payload = {
        "timestamp": time.time(),
        "event": event,
        **kwargs,
    }
    try:
        _logger.info(json.dumps(payload, ensure_ascii=False))
    except (ValueError, OSError):
        # 解释器关闭或输出流已关闭时静默忽略
        pass
    return payload


if not hasattr(_std_logging, "structured"):
    setattr(_std_logging, "structured", structured)
