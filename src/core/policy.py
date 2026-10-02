"""策略引擎模块：对命令执行进行安全审查（ALLOW / ASK / DENY），预编译正则以提升高并发性能。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    ASK = "ASK"
    DENY = "DENY"


@dataclass(slots=True)
class PolicyResult:
    decision: PolicyDecision
    reason: str = ""

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW

    @property
    def requires_confirmation(self) -> bool:
        return self.decision == PolicyDecision.ASK

    @property
    def is_denied(self) -> bool:
        return self.decision == PolicyDecision.DENY


# 默认危险规则黑名单 (DENY)
_RAW_DENY_PATTERNS = [
    r"\brm\s+-(?:r|f|rf|fr)\s+/(?:\s|$)",
    r"\bmkfs\b",
    r"\b:\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:",  # fork bomb
    r"\bdd\s+if=/dev/(?:zero|urandom)\s+of=/dev/[a-z]+",
]

# 默认敏感/需要用户把关的规则 (ASK)
_RAW_ASK_PATTERNS = [
    r"\brm\s+-(?:r|f|rf|fr)\b",
    r"\bsudo\b",
    r"\bchmod\s+-R\s+777\b",
    r"\bkill\s+-9\b",
]

# 默认长任务与安全命令白名单 (ALLOW)
_RAW_ALLOW_PATTERNS = [
    r"^sleep\s+\d+",
    r"^pytest\b",
    r"^make\b",
    r"^npm\s+(?:run|test|build|install)\b",
    r"^git\s+(?:status|log|diff|branch)\b",
    r"^ls\b",
    r"^cat\b",
    r"^head\b",
    r"^tail\b",
    r"^grep\b",
    r"^find\b",
    r"^wc\b",
    r"^echo\b",
    r"^pwd\b",
    r"^which\b",
    r"^whoami\b",
    r"^date\b",
    r"^ps\b",
    r"^df\b",
    r"^free\b",
    r"^uname\b",
]

# 预编译正则，提升匹配速度
_DENY_COMPILED = [re.compile(p) for p in _RAW_DENY_PATTERNS]
_ASK_COMPILED = [re.compile(p) for p in _RAW_ASK_PATTERNS]
_ALLOW_COMPILED = [re.compile(p) for p in _RAW_ALLOW_PATTERNS]

_custom_evaluators: list[Callable[[str], PolicyResult | None]] = []


def register_evaluator(evaluator: Callable[[str], PolicyResult | None]) -> None:
    """注册自定义策略评估器。"""
    _custom_evaluators.append(evaluator)


def clear_custom_evaluators() -> None:
    """清理自定义策略评估器。"""
    _custom_evaluators.clear()


def evaluate(command: str) -> PolicyResult:
    """评估命令执行策略。"""
    cmd = command.strip()

    # 1. 优先走自定义评估器
    for evaluator in _custom_evaluators:
        res = evaluator(cmd)
        if res is not None:
            return res

    # 2. 检查 DENY 规则
    for pattern in _DENY_COMPILED:
        if pattern.search(cmd):
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"命令匹配高危禁止规则: {pattern.pattern}",
            )

    # 3. 检查 ASK 规则
    for pattern in _ASK_COMPILED:
        if pattern.search(cmd):
            return PolicyResult(
                decision=PolicyDecision.ASK,
                reason=f"命令涉及高危操作，需客户端确认: {pattern.pattern}",
            )

    # 4. 检查 ALLOW 白名单规则
    for pattern in _ALLOW_COMPILED:
        if pattern.search(cmd):
            return PolicyResult(
                decision=PolicyDecision.ALLOW,
                reason="命令在安全白名单中",
            )

    # 5. 默认未知命令为 ASK
    return PolicyResult(
        decision=PolicyDecision.ASK,
        reason="未知命令，需客户端确认",
    )
