"""结构化日志模块，遵循项目 logging.structured 格式约定。"""

from __future__ import annotations

import json
import logging as _std_logging
import sys
import time
from typing import Any

# 配置基础日志记录器
_logger = _std_logging.getLogger("phone_mcp")
if not _logger.handlers:
    _handler = _std_logging.StreamHandler(sys.stderr)
    _formatter = _std_logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    _logger.setLevel(_std_logging.INFO)


def structured(event: str, **kwargs: Any) -> dict[str, Any]:
    """记录结构化日志并返回日志 payload。
    
    格式遵循第 7 节结构化规范：
    {
        "timestamp": float,
        "event": str,
        "data": dict
    }
    """
    payload = {
        "timestamp": time.time(),
        "event": event,
        **kwargs,
    }
    log_line = json.dumps(payload, ensure_ascii=False)
    _logger.info(log_line)
    return payload


# 动态扩展到标准库 logging 模块上，确保已有的 `logging.structured` 调用正常工作
if not hasattr(_std_logging, "structured"):
    setattr(_std_logging, "structured", structured)
