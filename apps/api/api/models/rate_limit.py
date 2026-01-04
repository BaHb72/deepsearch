"""
限流中间件的公共类型定义。
"""

from __future__ import annotations

from typing import TypedDict


class RateLimitStatsPayload(TypedDict):
    """限流统计成功返回结构。"""

    daily_limit: int
    daily_used: int
    daily_remaining: int
    usage_percent: str
    hourly_requests: int
    minute_requests: int
    total_requests: int
    rejected_requests: int
    rejection_rate: str
    cloudflare_requests: int
    priority_rejections: dict[str, int]


class RateLimitStatsError(TypedDict):
    """限流统计失败返回结构。"""

    error: str


RateLimitSnapshot = RateLimitStatsPayload | RateLimitStatsError


__all__ = ["RateLimitSnapshot", "RateLimitStatsError", "RateLimitStatsPayload"]
