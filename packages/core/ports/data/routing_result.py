"""
数据路由结果模型。

用于统一表达数据源回退轨迹，避免各层拼装字符串。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class FallbackReasonCode(StrEnum):
    """降级原因代码。"""

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CAPABILITY_NOT_SUPPORTED = "capability_not_supported"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_ERROR = "provider_error"
    NO_PROVIDER_FOR_CAPABILITY = "no_provider_for_capability"


@dataclass(frozen=True, slots=True)
class RouteAttempt:
    """单次数据源尝试记录。"""

    provider: str
    success: bool
    reason_code: FallbackReasonCode | None = None
    reason_detail: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True, slots=True)
class RoutedResponseMeta:
    """路由元信息。"""

    source: str
    fallback_reason: FallbackReasonCode | None = None
    attempts: tuple[RouteAttempt, ...] = field(default_factory=tuple)
    routed_at: datetime = field(default_factory=datetime.utcnow)


__all__ = [
    "FallbackReasonCode",
    "RouteAttempt",
    "RoutedResponseMeta",
]
