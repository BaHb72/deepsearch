"""通知推送服务使用的数据模型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class QuotaDecision:
    """额度判定结果。"""

    channel: str
    category: str
    allowed: bool
    max_per_window: Optional[int]
    current_count: int
    remaining: Optional[int]
    window_seconds: int
    reset_seconds: int
    expires_at: float


@dataclass(slots=True)
class NotificationResult:
    """通知发送结果描述。"""

    success: bool
    channel: str
    category: str
    status_code: Optional[int] = None
    response_data: Optional[Any] = None
    quota: Optional[QuotaDecision] = None
    error: Optional[str] = None
