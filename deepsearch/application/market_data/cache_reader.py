"""Cache reader utilities for market data realtime snapshots."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Mapping, MutableMapping, Sequence

from loguru import logger

from .cache_writer import MarketDataCacheWriter


def _decode_json(raw: Any) -> Mapping[str, Any] | None:
    """Best-effort JSON decoder that accepts bytes/str/mapping."""

    if raw is None:
        return None

    if isinstance(raw, Mapping):
        return raw

    payload: str | None = None
    if isinstance(raw, bytes):
        try:
            payload = raw.decode("utf-8")
        except Exception:
            payload = raw.decode("utf-8", errors="ignore")
    elif isinstance(raw, str):
        payload = raw

    if not payload:
        return None

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        logger.debug("无法解析缓存 JSON：{}", payload)
        return None


@dataclass(slots=True)
class MarketDataCacheReader:
    """Read realtime market data aggregates from Redis or in-memory fallback."""

    writer: MarketDataCacheWriter

    async def fetch_strength(
            self,
            windows: Sequence[str],
            *,
            boards: Sequence[str] | None = None,
            limit: int | None = None,
    ) -> list[Mapping[str, Any]]:
        """Load capital strength aggregations for specified windows."""

        board_set = {board for board in (boards or ()) if board}
        items: list[Mapping[str, Any]] = []
        for window in windows:
            key = f"market:strength:{window}"
            payload = await self._get_payload(key)
            if not payload:
                continue
            entries = list(payload.get("entries", []))
            if board_set:
                entries = [entry for entry in entries if entry.get("board") in board_set]
            if limit and limit > 0:
                entries = entries[:limit]
            items.extend(entries)
        return items

    async def fetch_order_imbalance(
            self,
            window: str,
            *,
            limit: int | None = None,
    ) -> list[Mapping[str, Any]]:
        """Load order imbalance rankings for a window."""

        payload = await self._get_payload(f"market:order-imbalance:{window}")
        if not payload:
            return []

        entries = list(payload.get("entries", []))
        if limit and limit > 0:
            entries = entries[:limit]
        return entries

    async def fetch_auction_quality(
            self,
            boards: Sequence[str],
    ) -> list[Mapping[str, Any]]:
        """Load auction quality snapshot per board."""

        results: list[Mapping[str, Any]] = []
        for board in boards:
            if not board:
                continue
            payload = await self._get_payload(f"market:auction:{board}")
            if payload:
                results.append(payload)
        return results

    async def _get_payload(self, key: str) -> Mapping[str, Any] | None:
        """Retrieve cached payload from Redis with in-memory fallback."""

        redis_client = getattr(self.writer, "redis", None)
        if redis_client is not None:
            try:
                raw_value = redis_client.get(key)
                if asyncio.iscoroutine(raw_value):
                    raw_value = await raw_value
                payload = _decode_json(raw_value)
                if payload is not None:
                    return payload
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("读取 Redis key %s 失败: %s", key, exc)

        fallback = self._get_memory_entry(key)
        if fallback is not None:
            return fallback

        return None

    def _get_memory_entry(self, key: str) -> Mapping[str, Any] | None:
        """Read entry from writer in-memory cache."""

        cache: MutableMapping[str, Any] = dict(self.writer.dump_memory_cache())
        if not cache:
            return None

        entry = cache.get(key)
        if entry is None:
            return None

        if isinstance(entry, Mapping):
            # writer keeps {"value": ..., "expires_in": ttl}
            value = entry.get("value")
            if isinstance(value, Mapping):
                return value
            decoded = _decode_json(value)
            if decoded is not None:
                return decoded
        else:
            decoded = _decode_json(entry)
            if decoded is not None:
                return decoded

        return None
