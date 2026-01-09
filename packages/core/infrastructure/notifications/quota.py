"""额度控制守卫。"""

from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional, TypedDict, cast

from core.config.models.notifications import NotificationCategoryConfig
from core.infrastructure.cache.cache_manager import CacheManager

from .models import QuotaDecision


class QuotaCachePayload(TypedDict):
    count: int
    expires_at: float
    max_per_window: int
    window_seconds: int


class QuotaSnapshotEntry(TypedDict):
    current: int
    max_per_window: int
    remaining: int
    window_seconds: int
    reset_seconds: int
    expires_at: float


class NotificationQuotaGuard:
    """基于缓存的通知额度限制器。"""

    def __init__(
        self, cache_manager: Optional[CacheManager] = None, key_prefix: str = "notification:quota"
    ) -> None:
        self._cache = cache_manager or CacheManager(l1_max_size=512, l1_ttl=3600)
        self._key_prefix = key_prefix
        self._locks: Dict[str, asyncio.Lock] = {}
        self._active_keys: set[str] = set()

    def _lock_for(self, channel: str, category: str) -> asyncio.Lock:
        key = f"{channel}:{category}"
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _build_cache_key(self, channel: str, category: str, window_index: int) -> str:
        return f"{self._key_prefix}:{channel}:{category}:{window_index}"

    async def check_and_consume(
        self, channel: str, category: str, category_config: Optional[NotificationCategoryConfig]
    ) -> QuotaDecision:
        """检查额度并消耗一次推送机会。"""
        channel = channel.lower()
        category = category.lower()

        if (
            not category_config
            or not category_config.enabled
            or category_config.max_per_window == 0
        ):
            # 无限制的类别
            return QuotaDecision(
                channel=channel,
                category=category,
                allowed=True,
                max_per_window=None if not category_config else category_config.max_per_window,
                current_count=0,
                remaining=None,
                window_seconds=0 if not category_config else category_config.window_seconds,
                reset_seconds=0,
                expires_at=0.0,
            )

        async with self._lock_for(channel, category):
            now = time.time()
            window_seconds = category_config.window_seconds
            window_index = int(now // window_seconds)
            window_start = window_index * window_seconds
            expires_at = float(window_start + window_seconds)
            cache_key = self._build_cache_key(channel, category, window_index)

            cache_raw = await self._cache.get(cache_key)
            cache_value: Optional[QuotaCachePayload]
            if isinstance(cache_raw, dict):
                cache_value = cast(QuotaCachePayload, cache_raw)
            else:
                cache_value = None

            if cache_value is not None:
                count = int(cache_value.get("count", 0))
                expires_at = float(cache_value.get("expires_at", expires_at))
            else:
                count = 0

            if count >= category_config.max_per_window:
                reset_seconds = max(0, int(expires_at - now))
                decision = QuotaDecision(
                    channel=channel,
                    category=category,
                    allowed=False,
                    max_per_window=category_config.max_per_window,
                    current_count=count,
                    remaining=0,
                    window_seconds=window_seconds,
                    reset_seconds=reset_seconds,
                    expires_at=expires_at,
                )
                self._active_keys.add(cache_key)
                return decision

            count += 1
            remaining = max(0, category_config.max_per_window - count)
            reset_seconds = max(1, int(expires_at - now))
            payload: QuotaCachePayload = {
                "count": count,
                "expires_at": expires_at,
                "max_per_window": category_config.max_per_window,
                "window_seconds": window_seconds,
            }
            await self._cache.set(cache_key, payload, ttl=reset_seconds, skip_l2=True)
            self._active_keys.add(cache_key)

            return QuotaDecision(
                channel=channel,
                category=category,
                allowed=True,
                max_per_window=category_config.max_per_window,
                current_count=count,
                remaining=remaining,
                window_seconds=window_seconds,
                reset_seconds=reset_seconds,
                expires_at=expires_at,
            )

    async def snapshot(self) -> Dict[str, Dict[str, QuotaSnapshotEntry]]:
        """获取当前配额状态快照。"""
        now = time.time()
        summary: Dict[str, Dict[str, QuotaSnapshotEntry]] = {}
        expired_keys: set[str] = set()

        for key in list(self._active_keys):
            raw_value = await self._cache.get(key)
            if not isinstance(raw_value, dict):
                expired_keys.add(key)
                continue

            try:
                _, channel, category, _ = key.split(":", 3)
            except ValueError:
                expired_keys.add(key)
                continue

            payload = cast(QuotaCachePayload, raw_value)
            count = int(payload.get("count", 0))
            max_per_window = int(payload.get("max_per_window", 0))
            window_seconds = int(payload.get("window_seconds", 0))
            expires_at = float(payload.get("expires_at", now))
            remaining = max(0, max_per_window - count)
            reset_seconds = max(0, int(expires_at - now))

            category_entry = summary.setdefault(category, {})
            category_entry[channel] = {
                "current": count,
                "max_per_window": max_per_window,
                "remaining": remaining,
                "window_seconds": window_seconds,
                "reset_seconds": reset_seconds,
                "expires_at": expires_at,
            }

            if reset_seconds == 0:
                expired_keys.add(key)

        for key in expired_keys:
            self._active_keys.discard(key)

        return summary

    async def reset(self) -> None:
        """清除所有额度计数。"""
        self._active_keys.clear()
        await self._cache.clear("l1")
